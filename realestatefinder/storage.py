"""Persistência das URLs em arquivo .properties (chave=valor)."""
import re
import unicodedata
from pathlib import Path


def city_key(cidade: str) -> str:
    text = unicodedata.normalize("NFKD", cidade).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load(path: Path) -> dict[str, list[str]]:
    """Retorna {grupo: [urls]}, onde grupo é 'nacional' ou 'local.<cidade>'."""
    groups: dict[str, list[str]] = {}
    if not path.exists():
        return groups
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        group = key.strip().rsplit(".", 1)[0]
        groups.setdefault(group, []).append(value.strip())
    return groups


def save(path: Path, groups: dict[str, list[str]]) -> None:
    lines = ["# Sites de imobiliárias (gerado por RealEstateFinder)"]
    for group in sorted(groups, key=lambda g: (g != "nacional", g)):
        lines.append("")
        lines.append(f"# {group}")
        for i, url in enumerate(groups[group], start=1):
            lines.append(f"{group}.{i}={url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge(existing: list[str], new: list[str]) -> list[str]:
    return existing + [u for u in new if u not in existing]
