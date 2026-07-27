from __future__ import annotations

import json
import tempfile
import unittest
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from trace_engine.ingestion import load_directory, parse_mailing_address


def _write_test_xlsx(path: Path, rows: list[list[str]]) -> None:
    def cell(reference: str, value: str) -> str:
        return (
            f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
        )

    sheet_rows = []
    for row_index, values in enumerate(rows, start=1):
        cells = "".join(
            cell(f"{chr(ord('A') + column_index)}{row_index}", value)
            for column_index, value in enumerate(values)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/'
                'spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/'
                'package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/'
                'spreadsheetml/2006/main"><sheetData>'
                f"{''.join(sheet_rows)}"
                "</sheetData></worksheet>"
            ),
        )


class IngestionTests(unittest.TestCase):
    def test_kansas_food_source_schema_is_adapted(self) -> None:
        path = Path(__file__).parents[1] / "data" / "sample" / "kansas_source.csv"
        providers = load_directory(path)
        first = providers[0]
        self.assertEqual(first.provider_id, "source-001")
        self.assertEqual(first.name, "Example Pantry")
        self.assertEqual(first.county, "Sedgwick")
        self.assertEqual(first.eligibility, "No ID required, /category/tefap/")
        self.assertEqual(first.source_url, "https://kansasfoodsource.org/category/tefap/")
        self.assertEqual(first.category, "Food")

    def test_211_xlsx_is_adapted_and_address_is_parsed(self) -> None:
        rows = [
            [
                "Name",
                "Organization",
                "Description",
                "Application Process",
                "Required Documents",
                "Fees",
                "Email",
                "Phones",
                "Mailing Address",
                "County",
                "Service Page URL",
                "Hours",
                "Category (Auto)",
            ],
            [
                "Example Shelter",
                "Example Organization",
                "Emergency shelter.",
                "Call first.",
                "-",
                "-",
                "help@example.org",
                "Main: 3165550100",
                "100 Main St, Wichita, KS 67202",
                "Sedgwick County",
                (
                    "https://211.example/itemDetails?"
                    "q=%7B%22id%22%3A123%7D"
                ),
                "Mon-Sun Open 24 hours",
                "Housing & Shelter",
            ],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "services.xlsx"
            _write_test_xlsx(path, rows)
            providers = load_directory(path)

        self.assertEqual(len(providers), 1)
        provider = providers[0]
        self.assertEqual(provider.provider_id, "211-123")
        self.assertEqual(provider.city, "Wichita")
        self.assertEqual(provider.state, "KS")
        self.assertEqual(provider.county, "Sedgwick")
        self.assertEqual(provider.zipcode, "67202")
        self.assertEqual(provider.category, "Housing & Shelter")
        self.assertEqual(provider.location_source, "parsed")

    def test_address_parser_normalizes_nonstandard_zip_extension(self) -> None:
        parsed = parse_mailing_address("PO Box 1987, Hutchinson, KS 67504 1987")
        self.assertEqual(
            parsed,
            {"city": "Hutchinson", "state": "KS", "zipcode": "67504"},
        )

    def test_json_ingestion_preserves_leading_zipcode_zeroes(self) -> None:
        value = [
            {
                "provider_id": "one",
                "name": "Example",
                "city": "Town",
                "county": "County",
                "zipcode": 1234,
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            providers = load_directory(path)
        self.assertEqual(providers[0].zipcode, "01234")

    def test_normalized_provider_can_omit_location(self) -> None:
        value = [{"provider_id": "remote", "name": "Remote Assistance"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            providers = load_directory(path)
        self.assertEqual(providers[0].city, "")
        self.assertEqual(providers[0].zipcode, "")

    def test_duplicate_provider_ids_are_rejected(self) -> None:
        value = [
            {"provider_id": "one", "name": "A", "city": "X", "county": "Y", "zipcode": "12345"},
            {"provider_id": "one", "name": "B", "city": "X", "county": "Y", "zipcode": "12345"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be unique"):
                load_directory(path)


if __name__ == "__main__":
    unittest.main()
