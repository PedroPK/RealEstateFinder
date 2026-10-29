"""Inspeção manual assistida do tráfego de busca de um site."""
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

from .connectors.sites import SITE_BASE_URLS, SITE_LABELS

_SENSITIVE_FIELD = re.compile(
    r"authorization|auth|token|secret|password|senha|cookie|session|csrf|xsrf|"
    r"email|e-mail|phone|telefone|celular|cpf|cnpj|document|user.?id|uid|"
    r"visitor.?id|device.?id|customer.?id|profile.?id|api.?key|redirect|callback|url|ip",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_JWT = re.compile(r"^[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}$")
MAX_SCHEMA_BODY_BYTES = 2_000_000
_MAX_SCHEMA_DEPTH = 6
_MAX_SCHEMA_KEYS = 60


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "unknown"


def _merge_schemas(left: Any, right: Any) -> Any:
    if left == right:
        return left
    if isinstance(left, dict) and isinstance(right, dict):
        merged = dict(left)
        for key, value in right.items():
            merged[key] = _merge_schemas(merged[key], value) if key in merged else value
        return merged
    return "mixed"


def schema_of(value: Any, depth: int = 0) -> Any:
    """Descreve só a estrutura (nomes e tipos); nenhum valor é preservado."""
    if depth >= _MAX_SCHEMA_DEPTH:
        return "..."
    if isinstance(value, dict):
        return {
            str(key)[:60]: schema_of(child, depth + 1)
            for key, child in list(value.items())[:_MAX_SCHEMA_KEYS]
        }
    if isinstance(value, list):
        item_schema: Any = None
        for child in value[:20]:
            child_schema = schema_of(child, depth + 1)
            item_schema = (
                child_schema if item_schema is None
                else _merge_schemas(item_schema, child_schema)
            )
        return [item_schema] if item_schema is not None else []
    return _type_name(value)


def list_sizes(value: Any, prefix: str = "", depth: int = 0) -> dict[str, int]:
    """Tamanhos das listas (úteis para confirmar que um filtro reduziu os resultados)."""
    sizes: dict[str, int] = {}
    if depth > 4:
        return sizes
    if isinstance(value, list):
        sizes[prefix or "$"] = len(value)
    elif isinstance(value, dict):
        for key, child in list(value.items())[:_MAX_SCHEMA_KEYS]:
            if isinstance(child, (dict, list)):
                sizes.update(list_sizes(child, f"{prefix}.{key}" if prefix else str(key), depth + 1))
    return dict(list(sizes.items())[:20])


def resolve_site_target(target: str) -> tuple[str, str]:
    """Resolve um identificador mapeado ou uma URL pública fornecida pelo usuário."""
    if target in SITE_BASE_URLS:
        return SITE_LABELS[target], SITE_BASE_URLS[target]
    parsed = urlsplit(target)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(
            "Informe um identificador mapeado ou uma URL completa começando com http:// ou https://."
        )
    if parsed.username or parsed.password:
        raise ValueError("A URL não pode conter credenciais.")
    return parsed.hostname, target


def _safe_value(name: str, value: Any) -> str:
    text = str(value)
    if _SENSITIVE_FIELD.search(name) or _EMAIL.search(text) or _JWT.fullmatch(text):
        return "[redigido]"
    if len(text) > 160:
        return "[valor longo redigido]"
    return text


def _safe_fields(fields: list[tuple[str, Any]]) -> list[dict[str, str]]:
    return [
        {"name": name, "value": _safe_value(name, value)}
        for name, value in fields
    ]


def _json_fields(value: Any, prefix: str = "", depth: int = 0) -> list[tuple[str, Any]]:
    if depth > 3:
        return []
    fields: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, (dict, list)):
                fields.extend(_json_fields(child, name, depth + 1))
            else:
                fields.append((name, child))
    elif isinstance(value, list):
        for child in value:
            if not isinstance(child, (dict, list)):
                fields.append((prefix, child))
    return fields[:100]


def _request_body_fields(body: str | None) -> list[dict[str, str]]:
    if not body:
        return []
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        fields = parse_qsl(body, keep_blank_values=True)
    else:
        fields = _json_fields(parsed)
    return _safe_fields(fields[:100])


def _safe_path(path: str) -> str:
    segments = []
    for segment in path.split("/"):
        decoded = unquote(segment)
        if _EMAIL.search(decoded) or _JWT.fullmatch(decoded):
            decoded = "[redigido]"
        elif len(decoded) > 60 or re.fullmatch(r"\d{8,}", decoded):
            decoded = "[id]"
        segments.append(decoded)
    return "/".join(segments)


class NetworkRecorder:
    """Registra endpoints e campos de busca, sem cabeçalhos nem corpos de resposta."""

    def __init__(self, capture_schema: bool = False) -> None:
        self.capture_schema = capture_schema
        self.active_step = "carga inicial"
        self.requests: list[dict[str, Any]] = []
        self._by_request_id: dict[int, dict[str, Any]] = {}

    def set_step(self, label: str) -> None:
        self.active_step = label

    def on_request(self, request: Any) -> None:
        resource_type = request.resource_type
        if resource_type not in {"document", "xhr", "fetch"}:
            return
        parsed = urlsplit(request.url)
        query_fields = _safe_fields(parse_qsl(parsed.query, keep_blank_values=True))
        record = {
            "step": self.active_step,
            "method": request.method,
            "resource_type": resource_type,
            "host": parsed.hostname or "",
            "path": _safe_path(parsed.path),
            "query": query_fields,
            "body_fields": _request_body_fields(request.post_data),
            "response_status": None,
            "response_content_type": None,
        }
        self.requests.append(record)
        self._by_request_id[id(request)] = record

    def on_response(self, response: Any) -> None:
        record = self._by_request_id.get(id(response.request))
        if record is None:
            return
        record["response_status"] = response.status
        content_type = response.headers.get("content-type", "")
        record["response_content_type"] = content_type[:100]

    async def capture_response_schema(self, response: Any) -> None:
        """Guarda o esquema de respostas JSON de XHR/fetch, sem os valores."""
        record = self._by_request_id.get(id(response.request))
        if record is None or record["resource_type"] not in {"xhr", "fetch"}:
            return
        if "json" not in response.headers.get("content-type", "").lower():
            return
        try:
            body = await response.body()
            if len(body) > MAX_SCHEMA_BODY_BYTES:
                record["response_schema"] = "[corpo grande demais]"
                return
            data = json.loads(body)
        except Exception:  # corpo indisponível ou JSON inválido: apenas não há esquema
            return
        record["response_schema"] = schema_of(data)
        record["response_list_sizes"] = list_sizes(data)


def _safe_report_url(url: str) -> str:
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = _safe_fields(query)
    return parsed._replace(
        path=_safe_path(parsed.path),
        query=urlencode([(item["name"], item["value"]) for item in safe_query]),
        fragment="",
    ).geturl()


def _default_report_path(host: str) -> Path:
    slug = re.sub(r"[^a-z0-9-]+", "-", host.lower()).strip("-") or "site"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("inspecoes") / f"{slug}-{timestamp}.json"


async def _inspect_site(
    target: str,
    report_path: Path | None,
    input_fn: Callable[[str], str],
    capture_schema: bool = False,
) -> Path:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "A inspeção requer Playwright. Instale com "
            "`python3 -m pip install -r requirements-inspecao.txt` e "
            "`python3 -m playwright install chromium`."
        ) from exc

    label, url = resolve_site_target(target)
    output = report_path or _default_report_path(urlsplit(url).hostname or label)
    recorder = NetworkRecorder(capture_schema)
    report: dict[str, Any] = {
        "site": label,
        "url": _safe_report_url(url),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "privacy": (
            "Não registra cabeçalhos completos, cookies, tokens, nem corpos de resposta. "
            "Armazena apenas o content-type da resposta"
            + (
                " e o esquema (nomes e tipos de campos, sem valores) de respostas JSON"
                if capture_schema else ""
            )
            + "; valores de campos sensíveis são redigidos."
        ),
        "steps": ["carga inicial"],
        "requests": recorder.requests,
    }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        page = await browser.new_page()
        tasks: list[asyncio.Task] = []

        def handle_response(response: Any) -> None:
            recorder.on_response(response)
            if capture_schema:
                tasks.append(asyncio.create_task(recorder.capture_response_schema(response)))

        page.on("request", recorder.on_request)
        page.on("response", handle_response)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            print(
                "Navegador aberto. Interaja com os filtros do site sem entrar "
                "em contas nem contornar bloqueios."
            )
            while True:
                label = await asyncio.to_thread(
                    input_fn,
                    "Próximo filtro/etapa (ex.: quartos=2; Enter encerra): ",
                )
                label = label.strip()[:100]
                if not label:
                    break
                recorder.set_step(label)
                report["steps"].append(label)
                await asyncio.to_thread(
                    input_fn,
                    f"Altere '{label}' no navegador, aguarde os resultados e pressione Enter: ",
                )
                await page.wait_for_timeout(500)
        except PlaywrightError as exc:
            report["error"] = type(exc).__name__
        finally:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await browser.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if report.get("error"):
        raise RuntimeError(
            f"A navegação falhou; relatório parcial salvo em {output}: {report['error']}"
        )
    return output


def inspect_site(
    target: str, report_path: Path | None = None, capture_schema: bool = False
) -> Path:
    """Abre um site para inspeção manual e salva um relatório JSON sanitizado."""
    return asyncio.run(_inspect_site(target, report_path, input, capture_schema))
