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
    reserved = {location_parameter, transaction_parameter}
    if len(reserved) != 2 or reserved.intersection(fixed_parameters):
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
    )


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

    query = {
        config.location_parameter: criteria.location,
        **config.fixed_parameters,
        config.transaction_parameter: config.transactions[criteria.transaction.value],
    }
    return f"{config.base_url}{config.search_path}?{urlencode(query)}"
