"""Persistência das URLs em arquivo .properties (chave=valor)."""
import logging
import re
import unicodedata
from pathlib import Path

from .observability import timed

logger = logging.getLogger(__name__)


def city_key(cidade: str) -> str:
    text = unicodedata.normalize("NFKD", cidade).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load(path: Path) -> dict[str, list[str]]:
    """Retorna {grupo: [urls]}, onde grupo é 'nacional' ou 'local.<cidade>'."""
    groups: dict[str, list[str]] = {}
    if not path.exists():
        logger.info("arquivo %s inexistente; iniciando sem URLs", path)
        return groups
    with timed("storage.carregar", logger, arquivo=path):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            group = key.strip().rsplit(".", 1)[0]
            groups.setdefault(group, []).append(value.strip())
    logger.info("carregados %d grupos e %d URLs de %s",
                len(groups), sum(map(len, groups.values())), path)
    return groups


def save(path: Path, groups: dict[str, list[str]]) -> None:
    lines = ["# Sites de imobiliárias (gerado por RealEstateFinder)"]
    for group in sorted(groups, key=lambda g: (g != "nacional", g)):
        lines.append("")
        lines.append(f"# {group}")
        for i, url in enumerate(groups[group], start=1):
            lines.append(f"{group}.{i}={url}")
    with timed("storage.salvar", logger, arquivo=path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("salvos %d grupos e %d URLs em %s",
                len(groups), sum(map(len, groups.values())), path)


def merge(existing: list[str], new: list[str]) -> list[str]:
    return existing + [u for u in new if u not in existing]
