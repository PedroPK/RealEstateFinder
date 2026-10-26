"""Classificação de sites: indica se o site oferece busca de imóveis."""
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_TRANSACTION = re.compile(
    r"(comprar|alugar|a-venda|para-alugar|aluguel|locacao|locação|for-sale|for-rent|\bvenda\b)",
    re.IGNORECASE,
)
_FILTER_FIELD = re.compile(
    r"(quarto|dormit|suite|suíte|vaga|preco|preço|valor|bairro|cidade|"
    r"tipo.?(do.?)?im|finalidade|negocia|codigo|código)",
    re.IGNORECASE,
)
_LISTING_PATH = re.compile(
    r"/(imoveis|imovel|apartamentos?|casas?|lancamentos|comprar|alugar|venda|aluguel)(/|\?|$)",
    re.IGNORECASE,
)
_SEARCH_CUE = re.compile(
    r"(pesquis|busc|encontr)\w*\s+(?:(?:o|a|seu|sua|um|uma)\s+)*(im[oó]ve|apart|casa)",
    re.IGNORECASE,
)
_SALE = re.compile(r"(comprar|a-venda|for-sale|venda)", re.IGNORECASE)
_RENT = re.compile(r"(alugar|para-alugar|aluguel|locacao|locação|for-rent)", re.IGNORECASE)
_MIN_READABLE_SIZE = 5000
_PRICE = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})+")


class _SignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.transaction_signals = 0
        self.filter_fields = 0
        self.listing_links = 0
        self._in_form = 0
        self.search_cues = 0
        self.anchors = 0
        self.nav_sale = 0
        self.nav_rent = 0
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "form":
            self._in_form += 1
        if tag in {"input", "select", "textarea"}:
            descriptor = " ".join(
                values.get(key, "") for key in ("name", "id", "placeholder", "aria-label")
            )
            if _FILTER_FIELD.search(descriptor):
                self.filter_fields += 1
        href = values.get("href", "")
        if tag == "a" and href:
            self.anchors += 1
            if _TRANSACTION.search(href):
                self.transaction_signals += 1
            path = urllib.parse.urlparse(href).path.strip("/")
            if path and "/" not in path and len(path) <= 20:
                self.nav_sale += bool(_SALE.search(path))
                self.nav_rent += bool(_RENT.search(path))
            if _LISTING_PATH.search(href):
                self.listing_links += 1
        if tag == "option" and _TRANSACTION.search(values.get("value", "")):
            self.transaction_signals += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_form:
            self._in_form -= 1

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self._text.append(stripped)
            if _SEARCH_CUE.search(stripped):
                self.search_cues += 1

    @property
    def price_mentions(self) -> int:
        return len(_PRICE.findall(" ".join(self._text)))

    @property
    def transaction_text(self) -> int:
        return sum(1 for text in self._text if len(text) <= 40 and _TRANSACTION.search(text))


def has_property_search(html: str) -> bool | None:
    """Heurística da página inicial: compra/aluguel mais filtros, anúncios com preço ou chamada de busca.

    Retorna None quando a página é só um shell JavaScript (sem links nem conteúdo para analisar).
    """
    if len(html) < _MIN_READABLE_SIZE:
        return None
    parser = _SignalParser()
    parser.feed(html)
    if parser.anchors == 0 and "<script" in html.lower():
        return None
    has_transaction = parser.transaction_signals + parser.transaction_text >= 2
    has_filters = parser.filter_fields >= 1 and parser.transaction_signals >= 5
    has_listings = parser.listing_links >= 3 and parser.price_mentions >= 2
    has_cue = parser.search_cues > 0
    has_nav = parser.nav_sale > 0 and parser.nav_rent > 0
    return has_transaction and (has_filters or has_listings or has_cue or has_nav)


def fetch_html(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(2_000_000).decode("utf-8", errors="replace")


def supports_property_search(url: str) -> bool | None:
    """True/False pela análise da página inicial; None quando o site não pôde ser lido."""
    try:
        return has_property_search(fetch_html(url))
    except (OSError, ValueError):
        return None


def _host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")


def trusted_hosts() -> frozenset[str]:
    """Domínios já mapeados em sites.json, aceitos sem nova verificação."""
    from .connectors import sites

    return frozenset(_host(url) for url in sites.SITE_BASE_URLS.values())


def filter_search_sites(
    urls: list[str], workers: int = 8
) -> tuple[list[str], list[str], list[str]]:
    """Separa as URLs em (com busca, sem busca, não verificáveis).

    Sites já mapeados são aceitos sem acesso à rede. Os não verificáveis (erro de rede
    ou página somente JavaScript) permanecem na lista de mantidos, pois não há evidência
    de que não tenham busca.
    """
    from concurrent.futures import ThreadPoolExecutor

    trusted = trusted_hosts()
    pending = [url for url in urls if _host(url) not in trusted]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = dict(zip(pending, pool.map(supports_property_search, pending)))
    kept: list[str] = []
    removed: list[str] = []
    unverified: list[str] = []
    for url in urls:
        verdict = True if url not in verdicts else verdicts[url]
        if verdict is False:
            removed.append(url)
        else:
            kept.append(url)
            if verdict is None:
                unverified.append(url)
    return kept, removed, unverified
