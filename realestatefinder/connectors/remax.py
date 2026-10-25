"""Geração de buscas públicas para o site brasileiro da RE/MAX."""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from ..models import SearchCriteria

DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "imobiliarias"
    / "remax.json"
)


@dataclass(frozen=True)
class ReMaxConfig:
    base_url: str
    search_path: str
    location_parameter: str
    transaction_parameter: str
    transactions: dict[str, str]
    fixed_parameters: dict[str, str]
    optional_parameters: dict[str, str]
    property_types: dict[str, str]
    property_features: dict[str, str]


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Configuração inválida: '{field}' deve ser texto não vazio.")
    return value


def _string_mapping(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"Configuração inválida: '{field}' deve ser um objeto não vazio.")
    if any(not isinstance(key, str) or not isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"Configuração inválida: '{field}' deve conter apenas textos.")
    return value


def _optional_string_mapping(value: Any, field: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Configuração inválida: '{field}' deve ser um objeto.")
    if any(
        not isinstance(key, str)
        or not key
        or not isinstance(item, str)
        or not item
        for key, item in value.items()
    ):
        raise ValueError(f"Configuração inválida: '{field}' deve conter textos não vazios.")
    return value


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> ReMaxConfig:
    """Carrega e valida a configuração declarativa do conector."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or isinstance(data.get("schema_version"), bool)
        or data.get("schema_version") != 1
    ):
        raise ValueError("Configuração RE/MAX inválida: schema_version deve ser 1.")

    base_url = _string(data.get("base_url"), "base_url")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.path not in ("", "/"):
        raise ValueError("Configuração RE/MAX inválida: base_url deve ser uma origem HTTPS.")

    search_path = _string(data.get("search_path"), "search_path")
    if not search_path.startswith("/") or search_path.startswith("//"):
        raise ValueError("Configuração RE/MAX inválida: search_path deve ser um caminho local.")

    parameters = data.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("Configuração RE/MAX inválida: 'parameters' deve ser um objeto.")

    location_parameter = _string(parameters.get("location"), "parameters.location")
    transaction_parameter = _string(parameters.get("transaction"), "parameters.transaction")
    transactions = _string_mapping(data.get("transactions"), "transactions")
    fixed_parameters = _string_mapping(data.get("fixed_parameters"), "fixed_parameters")
    optional_parameters = _optional_string_mapping(
        data.get("optional_parameters"), "optional_parameters"
    )
    property_types = _optional_string_mapping(data.get("property_types"), "property_types")
    property_features = _optional_string_mapping(
        data.get("property_features"), "property_features"
    )
    reserved = {location_parameter, transaction_parameter}
    mapped_parameters = set(optional_parameters.values())
    if (
        len(reserved) != 2
        or reserved.intersection(fixed_parameters)
        or reserved.intersection(mapped_parameters)
        or fixed_parameters.keys() & mapped_parameters
        or len(mapped_parameters) != len(optional_parameters)
    ):
        raise ValueError("Configuração RE/MAX inválida: parâmetros de busca duplicados.")
    if not {"comprar", "alugar"}.issubset(transactions):
        raise ValueError("Configuração RE/MAX inválida: faltam finalidades suportadas.")

    return ReMaxConfig(
        base_url=base_url.rstrip("/"),
        search_path=search_path,
        location_parameter=location_parameter,
        transaction_parameter=transaction_parameter,
        transactions=transactions,
        fixed_parameters=fixed_parameters,
        optional_parameters=optional_parameters,
        property_types=property_types,
        property_features=property_features,
    )


def _mapped_values(
    values: tuple[str, ...],
    mapping: dict[str, str],
    field: str,
) -> str:
    unsupported = [value for value in values if value not in mapping]
    if unsupported:
        raise ValueError(
            f"Filtro(s) não suportado(s) pela RE/MAX em '{field}': "
            f"{', '.join(unsupported)}."
        )
    return ",".join(mapping[value] for value in values)


def build_search_url(
    criteria: SearchCriteria,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> str:
    """Monta uma URL para abrir os resultados no mecanismo público da RE/MAX."""
    config = load_config(config_path)
    if criteria.transaction.value not in config.transactions:
        raise ValueError(
            f"A finalidade '{criteria.transaction.value}' não está configurada para a RE/MAX."
        )

    query: dict[str, str] = {}
    if criteria.location is not None:
        query[config.location_parameter] = criteria.location
    query.update(config.fixed_parameters)
    query[config.transaction_parameter] = config.transactions[criteria.transaction.value]

    optional_values: dict[str, str | int | float | None] = {
        "state": criteria.state,
        "city": criteria.city,
        "min_price": criteria.min_price,
        "max_price": criteria.max_price,
        "min_area": criteria.min_area,
        "max_area": criteria.max_area,
        "bedrooms": criteria.bedrooms,
        "bathrooms": criteria.bathrooms,
        "parking_spaces": criteria.parking_spaces,
    }
    for field, value in optional_values.items():
        if value is not None:
            parameter = config.optional_parameters.get(field)
            if parameter is None:
                raise ValueError(f"O filtro '{field}' não está configurado para a RE/MAX.")
            query[parameter] = str(value)

    for field, values, mapping in (
        ("property_types", criteria.property_types, config.property_types),
        ("property_features", criteria.property_features, config.property_features),
    ):
        if values:
            parameter = config.optional_parameters.get(field)
            if parameter is None:
                raise ValueError(f"O filtro '{field}' não está configurado para a RE/MAX.")
            query[parameter] = _mapped_values(values, mapping, field)

    return f"{config.base_url}{config.search_path}?{urlencode(query)}"
