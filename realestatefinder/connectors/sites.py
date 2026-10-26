"""Busca por filtros observados em portais e imobiliárias externas."""
import re
import unicodedata
from collections.abc import Callable, Mapping
from urllib.parse import urlencode

from ..models import SearchCriteria

_STATE_CODES = {
    "acre": "ac",
    "alagoas": "al",
    "amapa": "ap",
    "amazonas": "am",
    "bahia": "ba",
    "ceara": "ce",
    "distrito federal": "df",
    "espirito santo": "es",
    "goias": "go",
    "maranhao": "ma",
    "mato grosso": "mt",
    "mato grosso do sul": "ms",
    "minas gerais": "mg",
    "para": "pa",
    "paraiba": "pb",
    "parana": "pr",
    "pernambuco": "pe",
    "piaui": "pi",
    "rio de janeiro": "rj",
    "rio grande do norte": "rn",
    "rio grande do sul": "rs",
    "rondonia": "ro",
    "roraima": "rr",
    "santa catarina": "sc",
    "sao paulo": "sp",
    "sergipe": "se",
    "tocantins": "to",
}
_LUIZAPARIZI_TYPES = {
    "apartamento": "apartamento",
    "casa": "casa",
    "studio": "studio",
    "terreno": "terreno",
    "cobertura": "cobertura",
}
_ANCORA_TYPES = {
    "apartamento": "apartamento",
    "casa": "casa",
    "fazenda": "fazenda",
    "flat": "flat",
    "terreno": "terreno",
    "casa comercial": "casa-comercial",
    "galpao": "galpao",
    "loja": "loja",
    "predio edificio": "predio_edificio",
    "sala": "sala",
}
_NEWVILLE_TYPES = {
    "casa": "casa",
    "flat": "flat",
    "cobertura": "cobertura",
    "galpao": "galpao",
    "loja": "loja",
    "predio": "predio",
    "sala": "sala",
    "studio": "studio",
}

_ZAP_TYPES = {
    "apartamento": "apartamentos",
    "casa": "casas",
    "terreno": "terrenos",
}
_IMOVELGUIDE_TYPES = {
    "apartamento": "apartamento",
    "casa": "casa",
}
_IMOVELWEB_TYPES = {
    "apartamento": "apartamentos",
    "casa": "casas",
    "terreno": "terrenos",
}
_KENLO_TYPES = {
    "apartamento": "apartamento",
    "casa": "casa",
    "flat": "flat",
    "terreno": "terreno",
    "cobertura": "cobertura",
    "studio": "studio",
}
_CTI_TYPES = {
    "apartamento": "apartamento",
    "casa": "casa",
    "cobertura": "cobertura",
    "flat": "flat",
    "studio": "studio",
}
_LOPES_TYPES = {
    "apartamento": "apartamento",
    "casa": "casa",
    "terreno": "terreno",
}

SITE_BASE_URLS = {
    "zap": "https://www.zapimoveis.com.br",
    "imovelguide": "https://imovelguide.com.br",
    "imovelweb": "https://www.imovelweb.com.br",
    "wimoveis": "https://www.wimoveis.com.br",
    "lopes": "https://www.lopes.com.br",
    "cti": "https://www.ctiimobiliaria.com.br",
    "luizaparizi": "https://www.luizapariziimoveis.com.br",
    "ancora": "https://ancoraimobiliaria.com.br",
    "newville": "https://newville.com.br",
    "djm": "https://www.djmimoveis.com.br",
    "gvi": "https://www.gviimoveis.com.br",
    "bci": "https://bciimobiliaria.com.br",
    "bellolar": "https://www.bellolarimoveis.com.br",
    "trueimoveis": "https://www.trueimoveis.com.br",
    "moradasol": "https://www.moradasol.com.br",
    "redeimoveispe": "https://www.redeimoveispe.com.br",
    "fleischman": "https://www.fleischman.com.br",
}

SITE_LABELS = {
    "zap": "ZAP Imóveis",
    "imovelguide": "Imóvel Guide",
    "imovelweb": "Imovelweb",
    "wimoveis": "Wimóveis",
    "lopes": "Lopes",
    "cti": "CTI Imobiliária",
    "luizaparizi": "Luiza Parizi Imóveis",
    "ancora": "Âncora Imobiliária",
    "newville": "Newville",
    "djm": "DJM Imóveis",
    "gvi": "GVI Imóveis",
    "bci": "BCI Imobiliária",
    "bellolar": "Bellolar Imóveis",
    "trueimoveis": "True Imóveis",
    "moradasol": "Morada Sol",
    "redeimoveispe": "Rede Imóveis PE",
    "fleischman": "Fleischman",
}

_ALL_SITE_IDS = tuple(SITE_BASE_URLS)


def available_sites() -> tuple[str, ...]:
    """Retorna os identificadores de sites com busca pública mapeada."""
    return _ALL_SITE_IDS


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


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


def _selected_type(
    criteria: SearchCriteria,
    mapping: dict[str, str],
    *,
    default: str | None,
) -> str | None:
    if not criteria.property_types:
        return default
    if len(criteria.property_types) != 1:
        return default
    return mapping.get(
        _slug(criteria.property_types[0]).replace("-", " "),
        default,
    )


def _transaction(criteria: SearchCriteria) -> str:
    return "venda" if criteria.transaction.value == "comprar" else "aluguel"


def _query_url(base: str, params: Mapping[str, str | int | float]) -> str:
    return f"{base}?{urlencode({key: _number(value) for key, value in params.items()})}"


def _number(value: str | int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _zap(criteria: SearchCriteria) -> str:
    base = SITE_BASE_URLS["zap"]
    transaction = _transaction(criteria)
    property_type = _selected_type(criteria, _ZAP_TYPES, default="imoveis")
    assert property_type is not None
    path = f"{base}/{transaction}/{property_type}/"
    if criteria.city is not None or criteria.location is not None:
        path += f"{_state_code(criteria.state)}+{_city(criteria)}/"
    elif criteria.state is not None:
        path += f"{_state_code(criteria.state)}/"

    params: dict[str, str | int | float] = {}
    for field, key in (
        ("bedrooms", "quartos"),
        ("suites", "suites"),
        ("bathrooms", "banheiros"),
        ("parking_spaces", "vagas"),
        ("min_price", "precoMinimo"),
        ("max_price", "precoMaximo"),
        ("min_area", "areaMinima"),
        ("max_area", "areaMaxima"),
    ):
        value = getattr(criteria, field)
        if value is not None:
            params[key] = value
    return f"{path}?{urlencode({key: _number(value) for key, value in params.items()})}" if params else path


def _imovelguide(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _IMOVELGUIDE_TYPES, default="todos")
    assert property_type is not None
    base = (
        f"{SITE_BASE_URLS['imovelguide']}/{_transaction(criteria)}/"
        f"{property_type}/{_state_code(criteria.state)}/{_city(criteria)}"
    )
    params: dict[str, str | int | float] = {}
    for field, key in (
        ("bedrooms", "quarto"),
        ("bathrooms", "banheiro"),
        ("parking_spaces", "vagas"),
        ("min_price", "precominimo"),
        ("max_price", "precomaximo"),
        ("min_area", "areaminima"),
        ("max_area", "areamaxima"),
    ):
        value = getattr(criteria, field)
        if value is not None:
            params[key] = value
    return _query_url(base, params) if params else base


def _imovelweb(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _IMOVELWEB_TYPES, default="imoveis")
    assert property_type is not None
    path = (
        f"{SITE_BASE_URLS['imovelweb']}/{property_type}-{_transaction(criteria)}-"
        f"{_city(criteria)}-{_state_code(criteria.state)}"
    )
    suffixes = []
    for field, label in (
        ("bathrooms", "banheiro"),
        ("parking_spaces", "vaga"),
        ("bedrooms", "quarto"),
    ):
        value = getattr(criteria, field)
        if value is not None:
            suffixes.append(f"mais-de-{value}-{label}{'s' if value != 1 else ''}")
    if suffixes:
        path += "-" + "-".join(suffixes)
    return f"{path}.html"


def _wimoveis(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _IMOVELWEB_TYPES, default="imoveis")
    assert property_type is not None
    singular = {
        "apartamentos": "apartamentos",
        "casas": "casas",
        "terrenos": "terrenos",
        "imoveis": "imoveis",
    }.get(property_type, "imoveis")
    return (
        f"{SITE_BASE_URLS['wimoveis']}/{_transaction(criteria)}/{singular}/"
        f"{_state_code(criteria.state)}/{_city(criteria)}"
    )


def _kenlo(site: str, criteria: SearchCriteria) -> str:
    transaction = "a-venda" if criteria.transaction.value == "comprar" else "para-alugar"
    property_type = _selected_type(criteria, _KENLO_TYPES, default=None)
    base = f"{SITE_BASE_URLS[site]}/imoveis/{transaction}"
    if property_type is not None:
        base += f"/{property_type}/{_city(criteria)}"
    elif criteria.city is not None or criteria.location is not None:
        raise ValueError(
            "Escolha um tipo de imóvel para este site (por exemplo, --tipo-imovel Apartamento)."
        )
    params = {"quartos": criteria.bedrooms} if criteria.bedrooms is not None else {}
    return _query_url(base, params) if params else base


def _lopes(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _LOPES_TYPES, default=None)
    path = (
        f"{SITE_BASE_URLS['lopes']}/busca/{_transaction(criteria)}/br/"
        f"{_state_code(criteria.state)}/{_city(criteria)}"
    )
    if property_type is not None:
        path += f"/tipo/{property_type}"
    return path


def _cti(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _CTI_TYPES, default=None)
    path = f"{SITE_BASE_URLS['cti']}/{_transaction(criteria)}"
    if property_type is not None:
        path += f"/{property_type}/{_city(criteria)}"
    return path


def _luizaparizi(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _LUIZAPARIZI_TYPES, default=None)
    if property_type is None:
        raise ValueError(
            "Escolha um tipo de imóvel para Luiza Parizi "
            "(por exemplo, --tipo-imovel Apartamento)."
        )
    return (
        f"{SITE_BASE_URLS['luizaparizi']}/{_transaction(criteria)}/{property_type}/"
        f"{_state_code(criteria.state)}/{_city(criteria)}"
    )


def _ancora(criteria: SearchCriteria) -> str:
    property_type = _selected_type(criteria, _ANCORA_TYPES, default="residencial_comercial")
    assert property_type is not None
    return (
        f"{SITE_BASE_URLS['ancora']}/{_transaction(criteria)}/"
        f"{property_type}/{_city(criteria)}/"
    )


def _newville(criteria: SearchCriteria) -> str:
    base = f"{SITE_BASE_URLS['newville']}/imoveis"
    params: dict[str, str | int | float] = {
        "negociacao": (
            "venda" if criteria.transaction.value == "comprar" else "locacao"
        )
    }
    if criteria.city is not None or criteria.location is not None:
        if criteria.state is not None:
            params["cidade"] = f"{_city(criteria).replace('-', '+')}--{_state_code(criteria.state)}"
    for field, key in (
        ("min_price", "preco_min"),
        ("max_price", "preco_max"),
        ("suites", "suites"),
        ("parking_spaces", "vagas"),
    ):
        value = getattr(criteria, field)
        if value is not None:
            params[key] = value
    property_type = _selected_type(criteria, _NEWVILLE_TYPES, default=None)
    if property_type is not None:
        params["tipo"] = property_type
    return _query_url(base, params) if params else base


def _djm(criteria: SearchCriteria) -> str:
    if criteria.transaction.value != "comprar":
        raise ValueError("A rota pública de aluguel da DJM não foi confirmada.")
    return f"{SITE_BASE_URLS['djm']}/comprar"


def _gvi(criteria: SearchCriteria) -> str:
    return f"{SITE_BASE_URLS['gvi']}/{_transaction(criteria)}"


def _bci(criteria: SearchCriteria) -> str:
    transaction = "a-venda" if criteria.transaction.value == "comprar" else "para-alugar"
    return f"{SITE_BASE_URLS['bci']}/imoveis/{transaction}"


def _bellolar(site: str, criteria: SearchCriteria) -> str:
    return _kenlo(site, criteria)


_BUILDERS: dict[str, Callable[[SearchCriteria], str]] = {
    "zap": _zap,
    "imovelguide": _imovelguide,
    "imovelweb": _imovelweb,
    "wimoveis": _wimoveis,
    "lopes": _lopes,
    "cti": _cti,
    "luizaparizi": _luizaparizi,
    "ancora": _ancora,
    "newville": _newville,
    "djm": _djm,
    "gvi": _gvi,
    "bci": _bci,
    "bellolar": lambda criteria: _bellolar("bellolar", criteria),
    "trueimoveis": lambda criteria: _bellolar("trueimoveis", criteria),
    "moradasol": lambda criteria: _bellolar("moradasol", criteria),
    "redeimoveispe": lambda criteria: _bellolar("redeimoveispe", criteria),
    "fleischman": lambda criteria: _bellolar("fleischman", criteria),
}

_SUPPORTED_FILTERS = {
    "zap": {
        "state", "city", "property_types", "bedrooms", "suites", "bathrooms",
        "parking_spaces", "min_price", "max_price", "min_area", "max_area",
    },
    "imovelguide": {
        "state", "city", "property_types", "bedrooms", "bathrooms",
        "parking_spaces", "min_price", "max_price", "min_area", "max_area",
    },
    "imovelweb": {
        "state", "city", "property_types", "bedrooms", "bathrooms", "parking_spaces",
    },
    "wimoveis": {"state", "city", "property_types"},
    "lopes": {"state", "city", "property_types"},
    "cti": {"city", "property_types"},
    "luizaparizi": {"state", "city", "property_types"},
    "ancora": {"city", "property_types"},
    "newville": {
        "transaction", "state", "city", "min_price", "max_price", "suites",
        "parking_spaces", "property_types",
    },
    "djm": set(),
    "gvi": set(),
    "bci": set(),
    "bellolar": {"city", "property_types", "bedrooms"},
    "trueimoveis": {"city", "property_types", "bedrooms"},
    "moradasol": {"city", "property_types", "bedrooms"},
    "redeimoveispe": {"city", "property_types", "bedrooms"},
    "fleischman": {"city", "property_types", "bedrooms"},
}

_SUPPORTED_TYPES = {
    "zap": _ZAP_TYPES,
    "imovelguide": _IMOVELGUIDE_TYPES,
    "imovelweb": _IMOVELWEB_TYPES,
    "wimoveis": _IMOVELWEB_TYPES,
    "lopes": _LOPES_TYPES,
    "cti": _CTI_TYPES,
    "luizaparizi": _LUIZAPARIZI_TYPES,
    "ancora": _ANCORA_TYPES,
    "newville": _NEWVILLE_TYPES,
    "djm": {},
    "gvi": {},
    "bci": {},
    "bellolar": _KENLO_TYPES,
    "trueimoveis": _KENLO_TYPES,
    "moradasol": _KENLO_TYPES,
    "redeimoveispe": _KENLO_TYPES,
    "fleischman": _KENLO_TYPES,
}


def unsupported_filters(criteria: SearchCriteria, site: str) -> tuple[str, ...]:
    """Retorna filtros informados que não fazem parte do mapeamento desse site."""
    supported = _SUPPORTED_FILTERS[site]
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
    if site == "newville":
        has_city = criteria.city is not None or criteria.location is not None
        if has_city and criteria.state is None:
            unsupported.append("city")
        elif criteria.state is not None and not has_city:
            unsupported.append("state")
    if criteria.property_types and "property_types" in supported:
        mapped = _SUPPORTED_TYPES[site]
        if (
            len(criteria.property_types) != 1
            or _slug(criteria.property_types[0]).replace("-", " ") not in mapped
        ):
            unsupported.append("property_types")
    return tuple(unsupported)


def build_site_search_url(criteria: SearchCriteria, site: str) -> str:
    """Gera URL de pesquisa para um dos sites com mapeamento confirmado."""
    if site not in _BUILDERS:
        raise ValueError(f"Site sem mapeamento de busca: '{site}'.")
    return _BUILDERS[site](criteria)
