import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from realestatefinder.connectors.remax import (
    DEFAULT_CONFIG_PATH,
    build_search_url,
    load_config,
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

    def test_rejects_unmapped_property_feature(self) -> None:
        with self.assertRaisesRegex(ValueError, "não suportado"):
            build_search_url(
                SearchCriteria("Recife", property_features=("Área Pet",))
            )

    def test_rejects_unsupported_schema_version(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "remax.json"
            config_path.write_text('{"schema_version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema_version"):
                load_config(config_path)

    def test_legacy_config_without_optional_mappings_keeps_basic_search(self) -> None:
        data = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        for field in ("optional_parameters", "property_types", "property_features"):
            data.pop(field)
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "remax.json"
            config_path.write_text(json.dumps(data), encoding="utf-8")
            url = build_search_url(SearchCriteria("Recife"), config_path)
        self.assertEqual(
            parse_qs(urlparse(url).query),
            {
                "FreeText": ["Recife"],
                "Country": ["Brasil"],
                "CountryId": ["55"],
                "ListingClass": ["-1"],
                "TransactionTypeUID": ["261"],
            },
        )


if __name__ == "__main__":
    unittest.main()
