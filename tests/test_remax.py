import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from realestatefinder.connectors.remax import build_search_url, load_config
from realestatefinder.models import SearchCriteria, TransactionType


class SearchCriteriaTests(unittest.TestCase):
    def test_strips_location_whitespace(self) -> None:
        criteria = SearchCriteria("  Recife  ")
        self.assertEqual(criteria.location, "Recife")

    def test_rejects_empty_location(self) -> None:
        with self.assertRaises(ValueError):
            SearchCriteria("  ")


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

    def test_rejects_unsupported_schema_version(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "remax.json"
            config_path.write_text('{"schema_version": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema_version"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
