"""Logs de execução e métricas de desempenho."""
import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT_LOGGER = "realestatefinder"
DEFAULT_LOG_FILE = Path("logs") / "realestatefinder.log"
LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"

logger = logging.getLogger(f"{ROOT_LOGGER}.metrics")


class Metrics:
    """Acumula contadores e tempos por operação (seguro entre threads)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[str, int] = defaultdict(int)
        self.timings: dict[str, list[float]] = defaultdict(list)

    def incr(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] += amount

    def record(self, name: str, seconds: float) -> None:
        with self._lock:
            self.timings[name].append(seconds)

    def reset(self) -> None:
        with self._lock:
            self.counters.clear()
            self.timings.clear()

    def summary_lines(self) -> list[str]:
        with self._lock:
            lines = [f"contador {name} = {value}" for name, value in sorted(self.counters.items())]
            for name, values in sorted(self.timings.items()):
                lines.append(
                    f"tempo {name}: n={len(values)} total={sum(values):.3f}s "
                    f"média={sum(values) / len(values):.3f}s máx={max(values):.3f}s"
                )
        return lines

    def log_summary(self) -> None:
        for line in self.summary_lines():
            logger.info("métrica %s", line)


metrics = Metrics()


@contextmanager
def timed(name: str, log: logging.Logger | None = None, **context):
    """Mede a duração do bloco, registra em log e acumula nas métricas."""
    log = log or logger
    details = " ".join(f"{key}={value}" for key, value in context.items())
    log.debug("início %s %s", name, details)
    start = time.perf_counter()
    try:
        yield
    except BaseException:
        elapsed = time.perf_counter() - start
        metrics.record(name, elapsed)
        metrics.incr(f"{name}.erros")
        log.warning("falha %s após %.3fs %s", name, elapsed, details)
        raise
    elapsed = time.perf_counter() - start
    metrics.record(name, elapsed)
    log.info("fim %s em %.3fs %s", name, elapsed, details)


def setup_logging(
    level: str = "INFO",
    log_file: Path | str | None = DEFAULT_LOG_FILE,
    console: bool = True,
) -> None:
    """Configura o logger raiz da aplicação (console em stderr e arquivo rotativo).

    O arquivo sempre registra em DEBUG; o console respeita ``level``.
    """
    root = logging.getLogger(ROOT_LOGGER)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.DEBUG)
    root.propagate = False
    formatter = logging.Formatter(LOG_FORMAT)
    if console:
        stream = logging.StreamHandler()
        stream.setLevel(getattr(logging, level.upper()))
        stream.setFormatter(formatter)
        root.addHandler(stream)
    if log_file:
        path = Path(log_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
        except OSError as exc:
            root.warning("não foi possível gravar o log em %s: %s", path, exc)
        else:
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
    if not root.handlers:
        root.addHandler(logging.NullHandler())
