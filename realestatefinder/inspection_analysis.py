"""Análise de relatórios de inspeção: sugere parâmetros candidatos por filtro."""
import json
from pathlib import Path
from typing import Any

Endpoint = tuple[str, str, str]


def _fields(request: dict[str, Any]) -> dict[str, str]:
    fields = {f"query:{item['name']}": item["value"] for item in request.get("query", [])}
    fields.update({f"body:{item['name']}": item["value"] for item in request.get("body_fields", [])})
    return fields


def _endpoint(request: dict[str, Any]) -> Endpoint:
    return request["method"], request["host"], request["path"]


def _split_label(label: str) -> tuple[str, str]:
    if "=" in label:
        name, value = label.split("=", 1)
        return name.strip().lower(), value.strip().lower()
    return "", label.strip().lower()


def _score(label: str, field: str, value: str) -> int:
    name, wanted = _split_label(label)
    score = 1
    if wanted and value.lower() == wanted:
        score += 3
    elif wanted and wanted in value.lower():
        score += 2
    if name and name in field.lower():
        score += 1
    return score


def _candidate(request: dict[str, Any], kind: str, field: str,
               before: str | None, value: str, score: int) -> dict[str, Any]:
    return {
        "endpoint": f"{request['method']} {request['host']}{request['path']}",
        "kind": kind,
        "field": field,
        "before": before,
        "value": value,
        "score": score,
        "status": request.get("response_status"),
        "list_sizes": request.get("response_list_sizes"),
    }


def analyze_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Compara cada etapa com as anteriores e lista parâmetros e caminhos alterados."""
    requests = report.get("requests", [])
    steps = [step for step in report.get("steps", []) if step != "carga inicial"]
    history = [r for r in requests if r["step"] == "carga inicial"]
    results = []
    for step in steps:
        current = [r for r in requests if r["step"] == step]
        candidates: list[dict[str, Any]] = []
        for request in current:
            endpoint = _endpoint(request)
            previous = next((r for r in reversed(history) if _endpoint(r) == endpoint), None)
            if previous is None:
                previous = next(
                    (r for r in reversed(history)
                     if (r["host"], r["path"]) == (endpoint[1], endpoint[2])),
                    None,
                )
            before = _fields(previous) if previous else {}
            for field, value in _fields(request).items():
                if before.get(field) == value:
                    continue
                kind = "alterado" if field in before else "novo"
                candidates.append(
                    _candidate(request, kind, field, before.get(field), value, _score(step, field, value))
                )
            if previous is None and request["resource_type"] == "document":
                _, wanted = _split_label(step)
                if wanted and wanted in request["path"].lower():
                    candidates.append(_candidate(request, "caminho", "path", None, request["path"], 4))
        candidates.sort(key=lambda item: -item["score"])
        results.append({"step": step, "candidates": candidates})
        history.extend(current)
    return results


def format_analysis(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(f"Etapa: {result['step']}")
        if not result["candidates"]:
            lines.append("  Nenhum parâmetro novo ou alterado detectado.")
        for item in result["candidates"][:10]:
            before = f" (antes: {item['before']})" if item["before"] is not None else ""
            sizes = f"; listas: {item['list_sizes']}" if item["list_sizes"] else ""
            lines.append(
                f"  [{item['score']}] {item['endpoint']} -> {item['field']}={item['value']}"
                f"{before} [{item['kind']}; status {item['status']}{sizes}]"
            )
    lines.append(
        "Candidatos são sugestões: confirme no navegador que o filtro alterou os resultados "
        "antes de mapear."
    )
    return "\n".join(lines)


def analyze_report_file(path: Path) -> str:
    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    if not isinstance(report, dict) or "requests" not in report:
        raise ValueError("Arquivo não parece ser um relatório de inspeção.")
    return format_analysis(analyze_report(report))
