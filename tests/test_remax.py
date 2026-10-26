import unittest
from urllib.parse import parse_qs, urlparse

from realestatefinder.connectors.sites import (
    build_site_search_url,
    unsupported_filters,
)
from realestatefinder.models import SearchCriteria, TransactionType


class SearchCriteriaTests(unittest.TestCase):
    def test_strips_location_whitespace(self) -> None:
        criteria = SearchCriteria("  Recife  ")
        self.assertEqual(criteria.location, "Recife")

    def test_rejects_empty_location(self) -> None:
        with self.assertRaises(ValueError):
            SearchCriteria("  ")

    def test_accepts_search_with_city_or_state_only(self) -> None:
        self.assertEqual(SearchCriteria(city=" Recife ").city, "Recife")
        self.assertEqual(SearchCriteria(state=" Pernambuco ").state, "Pernambuco")

    def test_rejects_inverted_ranges(self) -> None:
        with self.assertRaisesRegex(ValueError, "min_price"):
            SearchCriteria("Recife", min_price=500_000, max_price=400_000)
        with self.assertRaisesRegex(ValueError, "min_area"):
            SearchCriteria("Recife", min_area=100, max_area=50)


def build_search_url(criteria: SearchCriteria) -> str:
    return build_site_search_url(criteria, "remax")


class ReMaxConnectorTests(unittest.TestCase):
    def test_builds_purchase_search_url(self) -> None:
        url = build_search_url(SearchCriteria("São Paulo"))
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.remax.com.br")
        self.assertEqual(parsed.path, "/listings")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "FreeText": ["São Paulo"],
                "Country": ["Brasil"],
                "CountryId": ["55"],
                "ListingClass": ["-1"],
                "TransactionTypeUID": ["261"],
            },
        )

    def test_builds_rental_search_url(self) -> None:
        url = build_search_url(
            SearchCriteria("Recife", transaction=TransactionType.RENT)
        )
        self.assertEqual(parse_qs(urlparse(url).query)["TransactionTypeUID"], ["262"])
        self.assertEqual(parse_qs(urlparse(url).query)["FreeText"], ["Recife"])

    def test_maps_supported_optional_filters(self) -> None:
        url = build_search_url(
            SearchCriteria(
                "Boa Viagem",
                state="Pernambuco",
                city="Recife",
                min_price=350_000,
                max_price=600_000,
                min_area=60,
                max_area=100,
                bedrooms=2,
                bathrooms=2,
                parking_spaces=1,
                property_types=("Apartamento", "Studio"),
                property_features=(
                    "Acessível a cadeiras de rodas",
                    "Registro de Água Individual",
                    "Varanda Gourmet",
                ),
            )
        )
        self.assertEqual(
            parse_qs(urlparse(url).query),
            {
                "FreeText": ["Boa Viagem"],
                "Country": ["Brasil"],
                "CountryId": ["55"],
                "ListingClass": ["-1"],
                "TransactionTypeUID": ["261"],
                "Province": ["Pernambuco"],
                "City": ["Recife"],
                "PriceMin": ["350000"],
                "PriceMax": ["600000"],
                "MinTotalArea": ["60"],
                "MaxTotalArea": ["100"],
                "Bedrooms": ["2"],
                "Bathrooms": ["2"],
                "ParkingSpaces": ["1"],
                "MacroPropertyTypeUIDs": ["2667,3247"],
                "PropertyFeatures": ["310,327,319"],
            },
        )

    def test_allows_only_supported_optional_filters(self) -> None:
        url = build_search_url(SearchCriteria(city="Recife"))
        parsed = parse_qs(urlparse(url).query)
        self.assertEqual(parsed["City"], ["Recife"])
        self.assertNotIn("FreeText", parsed)
        self.assertNotIn("Bedrooms", parsed)

    def test_unmapped_property_feature_is_omitted_and_reported(self) -> None:
        criteria = SearchCriteria(
            "Recife", property_features=("Área Pet", "Varanda Gourmet")
        )
        parsed = parse_qs(urlparse(build_search_url(criteria)).query)
        self.assertEqual(parsed["PropertyFeatures"], ["319"])
        self.assertEqual(unsupported_filters(criteria, "remax"), ("property_features",))

    def test_only_unmapped_feature_does_not_break_the_search(self) -> None:
        criteria = SearchCriteria("Recife", property_features=("Área Pet",))
        parsed = parse_qs(urlparse(build_search_url(criteria)).query)
        self.assertNotIn("PropertyFeatures", parsed)
        self.assertEqual(parsed["FreeText"], ["Recife"])

    def test_suites_are_not_supported_by_remax(self) -> None:
        criteria = SearchCriteria("Recife", suites=2)
        self.assertEqual(unsupported_filters(criteria, "remax"), ("suites",))
        self.assertNotIn("suites", build_search_url(criteria).lower())

    def test_partially_unmapped_property_types_keep_the_mapped_ones(self) -> None:
        criteria = SearchCriteria("Recife", property_types=("Apartamento", "Castelo"))
        parsed = parse_qs(urlparse(build_search_url(criteria)).query)
        self.assertEqual(parsed["MacroPropertyTypeUIDs"], ["2667"])
        self.assertEqual(unsupported_filters(criteria, "remax"), ("property_types",))


if __name__ == "__main__":
    unittest.main()
