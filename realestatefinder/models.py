"""Modelos comuns para buscas de imóveis."""
from dataclasses import dataclass
from enum import Enum


class TransactionType(str, Enum):
    BUY = "comprar"
    RENT = "alugar"


@dataclass(frozen=True)
class SearchCriteria:
    location: str
    transaction: TransactionType = TransactionType.BUY

    def __post_init__(self) -> None:
        if not isinstance(self.location, str) or not self.location.strip():
            raise ValueError("A localidade da busca não pode estar vazia.")
        if not isinstance(self.transaction, TransactionType):
            raise ValueError("A finalidade deve ser comprar ou alugar.")
        object.__setattr__(self, "location", self.location.strip())
