import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from realestatefinder import observability, storage
from realestatefinder.connectors.sites import build_site_search_url
from realestatefinder.models import SearchCriteria

ROOT = Path(__file__).resolve().parents[1]


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        observability.metrics.reset()
        self.addCleanup(observability.setup_logging, "INFO", None, False)

    def test_timed_records_metrics_and_logs(self):
        with self.assertLogs("realestatefinder.metrics", level="INFO") as logs:
            with observability.timed("teste.op", contexto="x"):
                pass
        self.assertIn("fim teste.op", logs.output[0])
        self.assertEqual(len(observability.metrics.timings["teste.op"]), 1)

    def test_timed_counts_errors_and_reraises(self):
        with self.assertLogs("realestatefinder.metrics", level="WARNING"):
            with self.assertRaises(RuntimeError):
                with observability.timed("teste.falha"):
                    raise RuntimeError("boom")
        self.assertEqual(observability.metrics.counters["teste.falha.erros"], 1)

    def test_summary_lines(self):
        observability.metrics.incr("a", 2)
        observability.metrics.record("b", 0.5)
        text = "\n".join(observability.metrics.summary_lines())
        self.assertIn("contador a = 2", text)
        self.assertIn("tempo b: n=1", text)

    def test_setup_logging_writes_debug_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "sub" / "app.log"
            observability.setup_logging("ERROR", log_file, console=False)
            logging.getLogger("realestatefinder.teste").debug("mensagem-debug")
            observability.setup_logging("INFO", None, console=False)
            self.assertIn("mensagem-debug", log_file.read_text(encoding="utf-8"))

    def test_instrumented_functions_emit_metrics(self):
        build_site_search_url(SearchCriteria(location="Recife"), "remax")
        self.assertEqual(observability.metrics.counters["sites.urls_geradas"], 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.properties"
            storage.save(path, {"nacional": ["https://a.com/"]})
            storage.load(path)
        self.assertEqual(len(observability.metrics.timings["storage.salvar"]), 1)
        self.assertEqual(len(observability.metrics.timings["storage.carregar"]), 1)

    def test_cli_creates_log_file_with_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "cli.log"
            result = subprocess.run(
                [sys.executable, "-m", "realestatefinder", "--buscar-site", "remax",
                 "--localidade", "Recife", "--log-arquivo", str(log_file)],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = log_file.read_text(encoding="utf-8")
            self.assertIn("execução finalizada (sucesso)", content)
            self.assertIn("métrica contador sites.urls_geradas = 1", content)


if __name__ == "__main__":
    unittest.main()
