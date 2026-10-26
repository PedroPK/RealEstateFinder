import unittest
from unittest import mock

from realestatefinder import classifier, search

PADDING = "<!-- " + "x" * 6000 + " -->"


def page(body: str) -> str:
    return f"<html><body>{body}{PADDING}</body></html>"


class HasPropertySearchTests(unittest.TestCase):
    def test_site_with_sale_and_rent_navigation_has_search(self) -> None:
        html = page('<a href="/venda">Venda</a><a href="/aluguel">Aluguel</a>')
        self.assertTrue(classifier.has_property_search(html))

    def test_site_with_filter_form_and_many_transaction_links_has_search(self) -> None:
        links = "".join(f'<a href="/venda/apartamento-{n}">v</a>' for n in range(6))
        html = page(f'{links}<form><input name="quartos"></form>')
        self.assertTrue(classifier.has_property_search(html))

    def test_search_call_to_action_has_search(self) -> None:
        html = page('<a href="/comprar">Comprar</a><a href="/x">Pesquise o seu imóvel</a>')
        self.assertTrue(classifier.has_property_search(html))

    def test_blog_with_sale_article_links_has_no_search(self) -> None:
        links = "".join(
            f'<a href="/blog/como-funciona-a-compra-e-venda-{n}/">Compra e venda</a>'
            for n in range(5)
        )
        self.assertFalse(classifier.has_property_search(page(links)))

    def test_directory_without_transaction_signals_has_no_search(self) -> None:
        html = page('<a href="/empresas">Empresas</a><a href="/contato">Contato</a>')
        self.assertFalse(classifier.has_property_search(html))

    def test_javascript_shell_is_unverifiable(self) -> None:
        html = page('<script src="/app.js"></script>')
        self.assertIsNone(classifier.has_property_search(html))

    def test_tiny_page_is_unverifiable(self) -> None:
        self.assertIsNone(classifier.has_property_search("<html></html>"))


class FilterSearchSitesTests(unittest.TestCase):
    def test_splits_trusted_searchable_removed_and_unverified_sites(self) -> None:
        verdicts = {
            "https://portal.example/": True,
            "https://blog-diretorio.example/": False,
            "https://fora-do-ar.example/": None,
        }
        urls = ["https://www.zapimoveis.com.br/", *verdicts]
        with mock.patch.object(
            classifier, "supports_property_search", side_effect=lambda url: verdicts[url]
        ) as checker:
            kept, removed, unverified = classifier.filter_search_sites(urls)
        self.assertEqual(
            kept,
            ["https://www.zapimoveis.com.br/", "https://portal.example/",
             "https://fora-do-ar.example/"],
        )
        self.assertEqual(removed, ["https://blog-diretorio.example/"])
        self.assertEqual(unverified, ["https://fora-do-ar.example/"])
        self.assertNotIn(
            mock.call("https://www.zapimoveis.com.br/"), checker.call_args_list
        )

    def test_network_failure_is_unverifiable(self) -> None:
        with mock.patch.object(classifier, "fetch_html", side_effect=OSError("offline")):
            self.assertIsNone(classifier.supports_property_search("https://x.example/"))


class DiscoveryFilterTests(unittest.TestCase):
    def test_blog_subdomains_and_software_vendors_are_ignored(self) -> None:
        self.assertTrue(search._is_ignored("blog.redeuno.com.br"))
        self.assertTrue(search._is_ignored("josefabricioneto.com.br"))
        self.assertFalse(search._is_ignored("newville.com.br"))


if __name__ == "__main__":
    unittest.main()
