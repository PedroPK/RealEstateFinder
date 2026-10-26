"""Busca de sites de imobiliárias via DuckDuckGo (HTML, sem chave de API)."""
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SEARCH_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = "Mozilla/5.0 (compatible; RealEstateFinder/0.1)"

# Domínios que não são sites próprios de imobiliárias.
IGNORED_DOMAINS = {
    "facebook.com", "instagram.com", "youtube.com", "linkedin.com", "twitter.com",
    "x.com", "tiktok.com", "wikipedia.org", "reclameaqui.com.br", "google.com",
    "duckduckgo.com", "pinterest.com", "glassdoor.com.br", "indeed.com",
    "jusbrasil.com.br", "gov.br", "mercadolivre.com.br", "olx.com.br",
    "josefabricioneto.com.br", "imobibrasil.com.br",
}

NATIONAL_QUERIES = [
    "imobiliárias no Brasil",
    "maiores imobiliárias do Brasil",
    "corretoras de imóveis com atuação nacional",
    "rede de imobiliárias franquia Brasil",
    "portal de imóveis comprar e alugar apartamentos casas",
    "site de imóveis à venda e para alugar no Brasil",
]

LOCAL_QUERIES = [
    "imobiliárias em {cidade}",
    "corretoras de imóveis em {cidade}",
    "imobiliária {cidade} comprar alugar imóveis",
    "melhores imobiliárias de {cidade}",
    "imóveis à venda em {cidade}",
    "apartamentos para alugar em {cidade}",
]


class _ResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        if "result__a" not in (attrs.get("class") or ""):
            return
        href = attrs.get("href") or ""
        if href.startswith("//"):
            href = "https:" + href
        query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in query:
            href = query["uddg"][0]
        if href.startswith("http"):
            self.urls.append(href)


def _base_domain(host: str) -> str:
    host = host.lower().removeprefix("www.")
    return host


def _is_ignored(host: str) -> bool:
    if host.startswith("blog."):
        return True
    return any(host == d or host.endswith("." + d) for d in IGNORED_DOMAINS)


def _fetch(query: str, timeout: int = 20) -> list[str]:
    data = urllib.parse.urlencode({"q": query, "kl": "br-pt"}).encode()
    req = urllib.request.Request(SEARCH_URL, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = _ResultParser()
    parser.feed(html)
    return parser.urls


def search_sites(queries: list[str], delay: float = 2.0) -> list[str]:
    """Executa as consultas e retorna a URL raiz de cada site candidato, sem duplicatas."""
    found: dict[str, str] = {}
    for i, query in enumerate(queries):
        if i:
            time.sleep(delay)
        try:
            urls = _fetch(query)
        except OSError as exc:
            print(f"Aviso: falha na consulta '{query}': {exc}")
            continue
        for url in urls:
            parsed = urllib.parse.urlparse(url)
            host = _base_domain(parsed.hostname or "")
            if not host or _is_ignored(host) or not re.search(r"\.[a-z]{2,}$", host):
                continue
            found.setdefault(host, f"{parsed.scheme}://{parsed.netloc}/")
    return list(found.values())


def search_national() -> list[str]:
    return search_sites(NATIONAL_QUERIES)


def search_local(cidade: str) -> list[str]:
    return search_sites([q.format(cidade=cidade) for q in LOCAL_QUERIES])
