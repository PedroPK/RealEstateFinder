import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from realestatefinder.inspection_analysis import analyze_report, analyze_report_file
from realestatefinder.site_inspector import NetworkRecorder, list_sizes, schema_of


def _request(step, path="/api/search", query=(), body=(), resource_type="fetch"):
    return {
        "step": step,
        "method": "GET",
        "resource_type": resource_type,
        "host": "api.example.com",
        "path": path,
        "query": [{"name": n, "value": v} for n, v in query],
        "body_fields": [{"name": n, "value": v} for n, v in body],
        "response_status": 200,
        "response_content_type": "application/json",
    }


class SchemaTests(unittest.TestCase):
    def test_schema_keeps_names_and_types_but_no_values(self) -> None:
        data = {"total": 2, "items": [{"id": 1, "title": "Casa secreta"}, {"id": 2, "price": None}]}
        schema = schema_of(data)
        self.assertEqual(
            schema,
            {"total": "number", "items": [{"id": "number", "title": "string", "price": "null"}]},
        )
        self.assertNotIn("secreta", json.dumps(schema))

    def test_list_sizes_reports_result_counts(self) -> None:
        self.assertEqual(list_sizes({"data": {"items": [1, 2, 3]}}), {"data.items": 3})

    def test_recorder_captures_only_json_xhr_schema(self) -> None:
        recorder = NetworkRecorder(capture_schema=True)
        request = SimpleNamespace(
            resource_type="fetch", url="https://api.example.com/search", method="GET", post_data=None
        )
        recorder.on_request(request)

        async def body() -> bytes:
            return b'{"items":[{"id":1}],"owner":"Maria"}'

        response = SimpleNamespace(
            request=request, status=200, headers={"content-type": "application/json"}, body=body
        )
        recorder.on_response(response)
        asyncio.run(recorder.capture_response_schema(response))
        record = recorder.requests[0]
        self.assertEqual(record["response_schema"], {"items": [{"id": "number"}], "owner": "string"})
        self.assertEqual(record["response_list_sizes"], {"items": 1})
        self.assertNotIn("Maria", json.dumps(record))

    def test_recorder_ignores_invalid_json_and_documents(self) -> None:
        recorder = NetworkRecorder(capture_schema=True)
        doc = SimpleNamespace(
            resource_type="document", url="https://example.com/", method="GET", post_data=None
        )
        bad = SimpleNamespace(
            resource_type="fetch", url="https://api.example.com/x", method="GET", post_data=None
        )
        recorder.on_request(doc)
        recorder.on_request(bad)

        async def bad_body() -> bytes:
            return b"not json"

        for req, ctype in ((doc, "application/json"), (bad, "application/json")):
            response = SimpleNamespace(
                request=req, status=200, headers={"content-type": ctype}, body=bad_body
            )
            asyncio.run(recorder.capture_response_schema(response))
        self.assertNotIn("response_schema", recorder.requests[0])
        self.assertNotIn("response_schema", recorder.requests[1])


class AnalysisTests(unittest.TestCase):
    def _report(self):
        return {
            "steps": ["carga inicial", "quartos=2", "cidade=Recife"],
            "requests": [
                _request("carga inicial", query=[("page", "1")]),
                _request("quartos=2", query=[("page", "1"), ("bedrooms", "2")]),
                _request("cidade=Recife", query=[("page", "1"), ("bedrooms", "2"), ("city", "Recife")]),
            ],
        }

    def test_suggests_new_parameter_for_each_step_with_best_score_first(self) -> None:
        results = analyze_report(self._report())
        first = results[0]["candidates"]
        self.assertEqual([c["field"] for c in first], ["query:bedrooms"])
        self.assertEqual(first[0]["kind"], "novo")
        self.assertGreaterEqual(first[0]["score"], 4)
        second = results[1]["candidates"]
        self.assertEqual([c["field"] for c in second], ["query:city"])

    def test_detects_changed_values_and_body_fields(self) -> None:
        report = {
            "steps": ["carga inicial", "preço=500"],
            "requests": [
                _request("carga inicial", body=[("filters.priceMax", "100")]),
                _request("preço=500", body=[("filters.priceMax", "500")]),
            ],
        }
        candidate = analyze_report(report)[0]["candidates"][0]
        self.assertEqual(candidate["kind"], "alterado")
        self.assertEqual((candidate["before"], candidate["value"]), ("100", "500"))

    def test_detects_filter_in_document_path(self) -> None:
        report = {
            "steps": ["carga inicial", "tipo=casas"],
            "requests": [
                _request("carga inicial", path="/venda", resource_type="document"),
                _request("tipo=casas", path="/venda/casas", resource_type="document"),
            ],
        }
        kinds = [c["kind"] for c in analyze_report(report)[0]["candidates"]]
        self.assertIn("caminho", kinds)

    def test_step_without_changes_reports_nothing(self) -> None:
        report = {
            "steps": ["carga inicial", "x=1"],
            "requests": [_request("carga inicial", query=[("a", "1")]),
                         _request("x=1", query=[("a", "1")])],
        }
        self.assertEqual(analyze_report(report)[0]["candidates"], [])

    def test_analyze_file_formats_and_rejects_invalid_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "r.json"
            good.write_text(json.dumps(self._report()), encoding="utf-8")
            text = analyze_report_file(good)
            self.assertIn("Etapa: quartos=2", text)
            self.assertIn("query:bedrooms=2", text)
            bad = Path(tmp) / "b.json"
            bad.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_report_file(bad)


if __name__ == "__main__":
    unittest.main()
