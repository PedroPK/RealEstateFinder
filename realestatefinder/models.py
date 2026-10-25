"""Modelos comuns para buscas de imóveis."""
from dataclasses import dataclass
from enum import Enum
import math
from typing import Any


class TransactionType(str, Enum):
    BUY = "comprar"
    RENT = "alugar"


@dataclass(frozen=True)
class SearchCriteria:
    location: str | None = None
    transaction: TransactionType = TransactionType.BUY
    state: str | None = None
    city: str | None = None
    min_price: int | float | None = None
    max_price: int | float | None = None
    min_area: int | float | None = None
    max_area: int | float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    parking_spaces: int | None = None
    property_types: tuple[str, ...] = ()
    property_features: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.transaction, TransactionType):
            raise ValueError("A finalidade deve ser comprar ou alugar.")

        for field in ("location", "state", "city"):
            value = getattr(self, field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"'{field}' deve ser texto.")
            cleaned = value.strip() if value is not None else None
            object.__setattr__(self, field, cleaned or None)

        if not any((self.location, self.state, self.city)):
            raise ValueError("Informe uma localidade, estado ou cidade para a busca.")

        for field in ("min_price", "max_price", "min_area", "max_area"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"'{field}' deve ser um número finito não negativo.")

        for minimum, maximum in (
            ("min_price", "max_price"),
            ("min_area", "max_area"),
        ):
            lower = getattr(self, minimum)
            upper = getattr(self, maximum)
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"'{minimum}' não pode ser maior que '{maximum}'.")

        for field in ("bedrooms", "bathrooms", "parking_spaces"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"'{field}' deve ser um inteiro não negativo.")

        for field in ("property_types", "property_features"):
            values: Any = getattr(self, field)
            if not isinstance(values, (tuple, list)):
                raise ValueError(f"'{field}' deve ser uma lista de textos.")
            cleaned_values = []
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"'{field}' deve conter apenas textos não vazios.")
                cleaned_values.append(value.strip())
            object.__setattr__(self, field, tuple(dict.fromkeys(cleaned_values)))
