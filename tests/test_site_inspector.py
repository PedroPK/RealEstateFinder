import asyncio
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from realestatefinder import site_inspector
from realestatefinder.site_inspector import (
    NetworkRecorder,
    _request_body_fields,
    _safe_report_url,
    resolve_site_target,
)


class SiteInspectorTests(unittest.TestCase):
    def test_resolves_mapped_site(self) -> None:
        label, url = resolve_site_target("remax")
        self.assertEqual(label, "RE/MAX")
        self.assertEqual(url, "https://www.remax.com.br")

    def test_accepts_public_http_or_https_url(self) -> None:
        label, url = resolve_site_target("https://example.com/busca")
        self.assertEqual(label, "example.com")
        self.assertEqual(url, "https://example.com/busca")

    def test_rejects_invalid_schemes_and_url_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "URL completa"):
            resolve_site_target("javascript:alert(1)")
        with self.assertRaisesRegex(ValueError, "credenciais"):
            resolve_site_target("https://user:password@example.com")

    def test_report_url_redacts_sensitive_query_and_long_path_ids(self) -> None:
        result = _safe_report_url(
            "https://example.com/api/users/123456789?city=Recife&api_token=secret#frag"
        )
        self.assertEqual(
            result,
            "https://example.com/api/users/[id]?city=Recife&api_token=%5Bredigido%5D",
        )

    def test_request_body_fields_parse_json_and_redact_sensitive_values(self) -> None:
        fields = _request_body_fields(
            '{"filters":{"bedrooms":2,"city":"Recife"},"access_token":"secret",'
            '"uid":"visitor-123"}'
        )
        self.assertEqual(
            fields,
            [
                {"name": "filters.bedrooms", "value": "2"},
                {"name": "filters.city", "value": "Recife"},
                {"name": "access_token", "value": "[redigido]"},
                {"name": "uid", "value": "[redigido]"},
            ],
        )

    def test_recorder_groups_requests_by_step_and_never_records_headers(self) -> None:
        recorder = NetworkRecorder()
        request = SimpleNamespace(
            resource_type="fetch",
            url="https://api.example.com/search?city=Recife",
            method="POST",
            post_data='{"bedrooms":2}',
        )
        recorder.on_request(request)
        recorder.set_step("quartos=2")
        next_request = SimpleNamespace(
            resource_type="xhr",
            url="https://api.example.com/search?bedrooms=2",
            method="GET",
            post_data=None,
        )
        recorder.on_request(next_request)
        recorder.on_response(
            SimpleNamespace(
                request=next_request,
                status=200,
                headers={"content-type": "application/json"},
            )
        )
        self.assertEqual(recorder.requests[0]["step"], "carga inicial")
        self.assertEqual(recorder.requests[1]["step"], "quartos=2")
        self.assertEqual(recorder.requests[1]["response_status"], 200)
        self.assertNotIn("headers", recorder.requests[1])

    def test_recorder_ignores_static_resources(self) -> None:
        recorder = NetworkRecorder()
        recorder.on_request(
            SimpleNamespace(
                resource_type="image",
                url="https://example.com/image.jpg",
                method="GET",
                post_data=None,
            )
        )
        self.assertEqual(recorder.requests, [])

    def test_inspection_writes_a_report_with_filter_steps(self) -> None:
        request = SimpleNamespace(
            resource_type="document",
            url="https://example.com/search",
            method="GET",
            post_data=None,
        )

        class FakePage:
            def __init__(self) -> None:
                self.handlers = {}

            def on(self, event, handler) -> None:
                self.handlers[event] = handler

            async def goto(self, url, **kwargs) -> None:
                self.handlers["request"](request)
                self.handlers["response"](
                    SimpleNamespace(
                        request=request,
                        status=200,
                        headers={"content-type": "text/html"},
                    )
                )

            async def wait_for_timeout(self, milliseconds) -> None:
                pass

        page = FakePage()

        class FakeBrowser:
            async def new_page(self):
                return page

            async def close(self) -> None:
                pass

        class FakeChromium:
            async def launch(self, **kwargs):
                return FakeBrowser()

        class FakePlaywright:
            chromium = FakeChromium()

        class FakeManager:
            async def __aenter__(self):
                return FakePlaywright()

            async def __aexit__(self, *args) -> None:
                pass

        fake_package = SimpleNamespace()
        fake_api = SimpleNamespace(
            Error=type("FakePlaywrightError", (Exception,), {}),
            async_playwright=FakeManager,
        )
        inputs = iter(("quartos=2", "", ""))

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "inspection.json"
            with patch.dict(
                sys.modules,
                {"playwright": fake_package, "playwright.async_api": fake_api},
            ):
                output = asyncio.run(
                    site_inspector._inspect_site(
                        "https://example.com",
                        report_path,
                        lambda prompt: next(inputs),
                    )
                )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(output, report_path)
        self.assertEqual(report["steps"], ["carga inicial", "quartos=2"])
        self.assertEqual(report["requests"][0]["response_status"], 200)


if __name__ == "__main__":
    unittest.main()
