import unittest
from urllib.parse import parse_qs, urlparse

from realestatefinder.connectors.sites import (
    available_sites,
    build_site_search_url,
    unsupported_filters,
)
from realestatefinder.models import SearchCriteria, TransactionType


class SiteConnectorTests(unittest.TestCase):
    def test_zap_maps_location_transaction_and_confirmed_numeric_filters(self) -> None:
        criteria = SearchCriteria(
            state="Pernambuco",
            city="Recife",
            transaction=TransactionType.RENT,
            property_types=("Apartamento",),
            min_price=300_000,
            max_area=120,
            bedrooms=3,
            suites=1,
            bathrooms=2,
            parking_spaces=1,
        )
        url = build_site_search_url(criteria, "zap")
        parsed = urlparse(url)
        self.assertEqual(
            parsed.path,
            "/aluguel/apartamentos/pe+recife/",
        )
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "precoMinimo": ["300000"],
                "areaMaxima": ["120"],
                "quartos": ["3"],
                "suites": ["1"],
                "banheiros": ["2"],
                "vagas": ["1"],
            },
        )

    def test_imovelguide_maps_form_fields(self) -> None:
        criteria = SearchCriteria(
            state="PE",
            city="Recife",
            property_types=("Apartamento",),
            min_price=500_000,
            max_price=2_000_000,
            min_area=100,
            max_area=250,
            bedrooms=4,
            bathrooms=2,
            parking_spaces=2,
        )
        url = build_site_search_url(criteria, "imovelguide")
        parsed = urlparse(url)
        self.assertEqual(parsed.path, "/venda/apartamento/pe/recife")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "quarto": ["4"],
                "banheiro": ["2"],
                "vagas": ["2"],
                "precominimo": ["500000"],
                "precomaximo": ["2000000"],
                "areaminima": ["100"],
                "areamaxima": ["250"],
            },
        )

    def test_imovelweb_uses_confirmed_slug_filters_only(self) -> None:
        criteria = SearchCriteria(
            state="Pernambuco",
            city="Recife",
            property_types=("Apartamento",),
            bedrooms=2,
            bathrooms=1,
            parking_spaces=2,
            min_price=200_000,
        )
        url = build_site_search_url(criteria, "imovelweb")
        self.assertEqual(
            url,
            "https://www.imovelweb.com.br/"
            "apartamentos-venda-recife-pe-mais-de-1-banheiro-"
            "mais-de-2-vagas-mais-de-2-quartos.html",
        )
        self.assertEqual(unsupported_filters(criteria, "imovelweb"), ("min_price",))

    def test_wimoveis_builds_confirmed_location_and_type_path(self) -> None:
        criteria = SearchCriteria(
            state="PE",
            city="Recife",
            transaction=TransactionType.RENT,
            property_types=("Casa",),
            min_area=80,
        )
        self.assertEqual(
            build_site_search_url(criteria, "wimoveis"),
            "https://www.wimoveis.com.br/aluguel/casas/pe/recife",
        )
        self.assertEqual(unsupported_filters(criteria, "wimoveis"), ("min_area",))

    def test_lopes_and_cti_map_confirmed_path_filters(self) -> None:
        criteria = SearchCriteria(
            state="Pernambuco",
            city="Recife",
            transaction=TransactionType.RENT,
            property_types=("Apartamento",),
            bedrooms=2,
        )
        self.assertEqual(
            build_site_search_url(criteria, "lopes"),
            "https://www.lopes.com.br/busca/aluguel/br/pe/recife/tipo/apartamento",
        )
        self.assertEqual(
            build_site_search_url(criteria, "cti"),
            "https://www.ctiimobiliaria.com.br/aluguel/apartamento/recife",
        )

    def test_luiza_parizi_maps_confirmed_path_filters(self) -> None:
        criteria = SearchCriteria(
            state="Pernambuco",
            city="Recife",
            property_types=("Apartamento",),
        )
        self.assertEqual(
            build_site_search_url(criteria, "luizaparizi"),
            "https://www.luizapariziimoveis.com.br/"
            "venda/apartamento/pe/recife",
        )

    def test_local_brokerage_sites_build_observed_search_routes(self) -> None:
        criteria = SearchCriteria(city="Recife")
        self.assertEqual(
            build_site_search_url(criteria, "ancora"),
            "https://ancoraimobiliaria.com.br/venda/residencial_comercial/recife/",
        )
        self.assertEqual(
            build_site_search_url(
                SearchCriteria(city="Recife", property_types=("Apartamento",)),
                "ancora",
            ),
            "https://ancoraimobiliaria.com.br/venda/apartamento/recife/",
        )
        self.assertEqual(
            build_site_search_url(criteria, "djm"),
            "https://www.djmimoveis.com.br/comprar",
        )
        self.assertEqual(
            build_site_search_url(criteria, "gvi"),
            "https://www.gviimoveis.com.br/venda",
        )
        self.assertEqual(
            build_site_search_url(criteria, "bci"),
            "https://bciimobiliaria.com.br/imoveis/a-venda",
        )

    def test_newville_maps_confirmed_get_filter_keys(self) -> None:
        criteria = SearchCriteria(
            city="Recife",
            transaction=TransactionType.RENT,
            min_price=1_000_000,
            max_price=1_500_000,
            suites=2,
            parking_spaces=1,
        )
        url = build_site_search_url(criteria, "newville")
        parsed = urlparse(url)
        self.assertEqual(parsed.path, "/imoveis")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "negociacao": ["locacao"],
                "preco_min": ["1000000"],
                "preco_max": ["1500000"],
                "suites": ["2"],
                "vagas": ["1"],
            },
        )
        self.assertEqual(unsupported_filters(criteria, "newville"), ("city",))

    def test_newville_warns_when_purchase_filter_is_not_mapped(self) -> None:
        criteria = SearchCriteria(city="Recife")
        self.assertEqual(
            unsupported_filters(criteria, "newville"),
            ("city",),
        )

    def test_newville_maps_confirmed_transaction_city_and_type_values(self) -> None:
        criteria = SearchCriteria(
            state="PE",
            city="Recife",
            property_types=("Casa",),
        )
        url = build_site_search_url(criteria, "newville")
        self.assertEqual(
            parse_qs(urlparse(url).query),
            {
                "negociacao": ["venda"],
                "cidade": ["recife--pe"],
                "tipo": ["casa"],
            },
        )
        self.assertEqual(unsupported_filters(criteria, "newville"), ())

    def test_kenlo_sites_share_confirmed_url_grammar(self) -> None:
        criteria = SearchCriteria(
            city="Recife",
            property_types=("Apartamento",),
            bedrooms=3,
        )
        self.assertEqual(
            build_site_search_url(criteria, "bellolar"),
            "https://www.bellolarimoveis.com.br/"
            "imoveis/a-venda/apartamento/recife?quartos=3",
        )
        self.assertEqual(
            build_site_search_url(criteria, "fleischman"),
            "https://www.fleischman.com.br/"
            "imoveis/a-venda/apartamento/recife?quartos=3",
        )

    def test_all_returns_registered_mapped_sites(self) -> None:
        self.assertEqual(
            set(available_sites()),
            {
                "zap", "imovelguide", "imovelweb", "wimoveis", "lopes", "cti",
                "luizaparizi", "ancora", "djm", "gvi",
                "newville", "bci",
                "bellolar", "trueimoveis", "moradasol", "redeimoveispe", "fleischman",
            },
        )

    def test_unknown_site_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "sem mapeamento"):
            build_site_search_url(SearchCriteria("Recife"), "unknown")


if __name__ == "__main__":
    unittest.main()
