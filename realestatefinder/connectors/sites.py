"""Busca por filtros observados em portais e imobiliárias externas.

O mapeamento de cada site fica em config/imobiliarias/sites.json; este módulo
é apenas o motor genérico que o interpreta.
"""
import json
import os
import re
import unicodedata
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ..models import SearchCriteria

DEFAULT_SITES_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "imobiliarias" / "sites.json"
)
CONFIG_ENV_VAR = "REALESTATEFINDER_SITES_CONFIG"

KNOWN_FILTERS = frozenset({
    "transaction", "state", "city", "min_price", "max_price", "min_area",
    "max_area", "bedrooms", "suites", "bathrooms", "parking_spaces",
    "property_types", "property_features",
})
_PLACEHOLDER = re.compile(r"\{(\w+)\}")

_STATE_CODES = {
    "acre": "ac", "alagoas": "al", "amapa": "ap", "amazonas": "am",
    "bahia": "ba", "ceara": "ce", "distrito federal": "df",
    "espirito santo": "es", "goias": "go", "maranhao": "ma",
    "mato grosso": "mt", "mato grosso do sul": "ms", "minas gerais": "mg",
    "para": "pa", "paraiba": "pb", "parana": "pr", "pernambuco": "pe",
    "piaui": "pi", "rio de janeiro": "rj", "rio grande do norte": "rn",
    "rio grande do sul": "rs", "rondonia": "ro", "roraima": "rr",
    "santa catarina": "sc", "sao paulo": "sp", "sergipe": "se",
    "tocantins": "to",
}


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _fail(message: str) -> ValueError:
    return ValueError(f"Configuração de sites inválida: {message}")


def _load_raw(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("sites"), dict) or not data["sites"]:
        raise _fail("'sites' deve ser um objeto não vazio.")
    return data


def _resolve_site(site_id: str, raw: Mapping[str, Any], data: Mapping[str, Any]) -> dict[str, Any]:
    site = dict(data.get("templates", {}).get(raw.get("template"), {}))
    site.update({key: value for key, value in raw.items() if key != "template"})
    for key in ("label", "base_url", "transactions", "path", "supported_filters"):
        if key not in site:
            raise _fail(f"site '{site_id}' sem o campo '{key}'.")
    transactions = site["transactions"]
    if isinstance(transactions, str):
        transactions = data.get("transaction_sets", {}).get(transactions)
    if not isinstance(transactions, dict) or not transactions:
        raise _fail(f"site '{site_id}' com 'transactions' inválido.")
    site["transactions"] = transactions
    types = site.get("types", {})
    if isinstance(types, str):
        types = data.get("type_sets", {}).get(types)
    if not isinstance(types, dict):
        raise _fail(f"site '{site_id}' com 'types' inválido.")
    site["types"] = types
    site["feature_sets"] = {
        name: data.get("feature_sets", {}).get(name, {})
        for name in {item["features"] for item in site.get("query", []) if "features" in item}
    }
    if any(name not in data.get("feature_sets", {}) for name in site["feature_sets"]):
        raise _fail(f"site '{site_id}' usa 'feature_sets' inexistente.")
    if not site["base_url"].startswith("https://"):
        raise _fail(f"site '{site_id}' deve usar uma URL base HTTPS.")
    unknown = set(site["supported_filters"]) - KNOWN_FILTERS
    if unknown:
        raise _fail(f"site '{site_id}' usa filtros desconhecidos: {sorted(unknown)}.")
    return site


@cache
def _load_sites(path: str) -> dict[str, dict[str, Any]]:
    data = _load_raw(Path(path))
    return {
        site_id: _resolve_site(site_id, raw, data)
        for site_id, raw in data["sites"].items()
    }


def load_sites() -> dict[str, dict[str, Any]]:
    """Carrega (com cache) o mapeamento de sites do arquivo de parâmetros."""
    return _load_sites(os.environ.get(CONFIG_ENV_VAR, str(DEFAULT_SITES_CONFIG_PATH)))


_SITES = load_sites()
SITE_BASE_URLS = {site_id: site["base_url"] for site_id, site in _SITES.items()}
SITE_LABELS = {site_id: site["label"] for site_id, site in _SITES.items()}


def available_sites() -> tuple[str, ...]:
    """Retorna os identificadores de sites com busca pública mapeada."""
    return tuple(_SITES)


def _state_code(state: str | None) -> str:
    if state is None:
        raise ValueError("Este site precisa do estado (UF), por exemplo --estado PE.")
    normalized = _slug(state).replace("-", " ")
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    if normalized not in _STATE_CODES:
        raise ValueError(f"Estado/UF não reconhecido: '{state}'.")
    return _STATE_CODES[normalized]


def _city(criteria: SearchCriteria) -> str:
    value = criteria.city or criteria.location
    if value is None:
        raise ValueError("Este site precisa da cidade (use --cidade-imovel).")
    if criteria.city is None and "," in value:
        value = value.rsplit(",", 1)[-1]
    return _slug(value)


def _selected_type(criteria: SearchCriteria, site: Mapping[str, Any]) -> str | None:
    default = site.get("type_default")
    if len(criteria.property_types) != 1:
        return default
    return site["types"].get(_slug(criteria.property_types[0]).replace("-", " "), default)


def _transaction(criteria: SearchCriteria, site: Mapping[str, Any]) -> str:
    value = site["transactions"].get(criteria.transaction.value)
    if value is None:
        raise ValueError(
            site.get("transaction_unsupported_message")
            or f"Finalidade '{criteria.transaction.value}' não mapeada para este site."
        )
    return value


def _placeholder(name: str, criteria: SearchCriteria, site: Mapping[str, Any]) -> str:
    if name == "transaction":
        return _transaction(criteria, site)
    if name == "uf":
        return _state_code(criteria.state)
    if name == "city":
        return _city(criteria)
    if name == "city_plus":
        return _city(criteria).replace("-", "+")
    if name == "type":
        value = _selected_type(criteria, site)
        if value is None:
            raise ValueError(
                site.get("type_required_message") or "Informe o tipo de imóvel (--tipo-imovel)."
            )
        return value
    raise _fail(f"marcador desconhecido '{{{name}}}'.")


def _render(template: str, criteria: SearchCriteria, site: Mapping[str, Any]) -> str:
    return _PLACEHOLDER.sub(lambda m: _placeholder(m.group(1), criteria, site), template)


def _segment(segment: Any, criteria: SearchCriteria, site: Mapping[str, Any]) -> str | None:
    if isinstance(segment, str):
        return _render(segment, criteria, site)
    if segment.get("when") == "type" and _selected_type(criteria, site) is None:
        return None
    error: ValueError | None = None
    for alternative in segment["any"]:
        try:
            return _render(alternative, criteria, site)
        except ValueError as exc:
            error = error or exc
    if error is not None and segment.get("strict"):
        raise error
    return None


def _slug_key(value: str) -> str:
    return _slug(value).replace("-", " ")


def _mapped_values(values: tuple[str, ...], mapping: Mapping[str, str]) -> list[str]:
    return [mapping[key] for key in map(_slug_key, values) if key in mapping]


def _query(criteria: SearchCriteria, site: Mapping[str, Any]) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in site.get("query", []):
        key = item["param"]
        if "transaction" in item:
            params[key] = item["transaction"][criteria.transaction.value]
        elif "template" in item:
            if all(_provided(criteria, name) for name in item["requires"]):
                params[key] = _render(item["template"], criteria, site)
        elif "value" in item:
            params[key] = item["value"]
        elif item.get("free_text"):
            if criteria.location is not None:
                params[key] = criteria.location
        elif item.get("types_multi"):
            mapped = _mapped_values(criteria.property_types, site["types"])
            if mapped:
                params[key] = ",".join(mapped)
        elif "features" in item:
            mapped = _mapped_values(criteria.property_features, site["feature_sets"][item["features"]])
            if mapped:
                params[key] = ",".join(mapped)
        elif item.get("type"):
            value = _selected_type(criteria, site)
            if value is not None:
                params[key] = value
        else:
            value = getattr(criteria, item["field"])
            if value is not None:
                params[key] = _number(value)
    return params


def _number(value: str | int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _provided(criteria: SearchCriteria, name: str) -> bool:
    if name == "city":
        return criteria.city is not None or criteria.location is not None
    return getattr(criteria, name) is not None


def build_site_search_url(criteria: SearchCriteria, site: str) -> str:
    """Gera URL de pesquisa para um dos sites com mapeamento confirmado."""
    if site not in _SITES:
        raise ValueError(f"Site sem mapeamento de busca: '{site}'.")
    config = _SITES[site]
    if config.get("type_required_with_city") and _provided(criteria, "city"):
        if _selected_type(criteria, config) is None:
            _placeholder("type", criteria, config)

    segments = [
        value
        for value in (_segment(item, criteria, config) for item in config["path"])
        if value is not None
    ]
    path = "/".join([config["base_url"].rstrip("/"), *segments])
    suffixes = []
    for rule in config.get("path_suffixes", []):
        value = getattr(criteria, rule["field"])
        if value is not None:
            template = rule["singular"] if value == 1 else rule["plural"]
            suffixes.append(template.format(value=value))
    if suffixes:
        path += "-" + "-".join(suffixes)
    if config.get("trailing_slash"):
        path += "/"
    path += config.get("extension", "")
    params = _query(criteria, config)
    return f"{path}?{urlencode(params)}" if params else path


def unsupported_filters(criteria: SearchCriteria, site: str) -> tuple[str, ...]:
    """Retorna filtros informados que não fazem parte do mapeamento desse site."""
    config = _SITES[site]
    supported = set(config["supported_filters"])
    filters = {
        "transaction": None,
        "state": criteria.state,
        "city": criteria.city or criteria.location,
        "min_price": criteria.min_price,
        "max_price": criteria.max_price,
        "min_area": criteria.min_area,
        "max_area": criteria.max_area,
        "bedrooms": criteria.bedrooms,
        "suites": criteria.suites,
        "bathrooms": criteria.bathrooms,
        "parking_spaces": criteria.parking_spaces,
        "property_types": criteria.property_types,
        "property_features": criteria.property_features,
    }
    unsupported = [
        field for field, value in filters.items()
        if value not in (None, (), []) and field not in supported
    ]
    for group in config.get("together", []):
        present = [name for name in group if _provided(criteria, name)]
        if len(present) == 1:
            unsupported.append(present[0])
    if criteria.property_types and "property_types" in supported:
        unmapped = any(_slug_key(value) not in config["types"] for value in criteria.property_types)
        if unmapped or (len(criteria.property_types) != 1 and not config.get("multi_types")):
            unsupported.append("property_types")
    if criteria.property_features and "property_features" in supported:
        mapping = next(iter(config["feature_sets"].values()), {})
        if any(_slug_key(value) not in mapping for value in criteria.property_features):
            unsupported.append("property_features")
    return tuple(unsupported)
