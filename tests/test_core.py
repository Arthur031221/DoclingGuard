"""Regression fixtures for document extraction quality checks."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from docling_guard.cli import main
from docling_guard.core import DocumentError, check_document, compare_documents, load_document


def document(text: str = "Source text", end: int | None = None) -> dict:
    return {
        "name": "fixture",
        "texts": [
            {
                "self_ref": "#/texts/0",
                "text": text,
                "prov": [{"page_no": 1, "charspan": [0, len(text) if end is None else end]}],
            }
        ],
        "tables": [],
    }


def cell(row: int, col: int, left: float, right: float) -> dict:
    return {
        "start_row_offset_idx": row,
        "end_row_offset_idx": row + 1,
        "start_col_offset_idx": col,
        "end_col_offset_idx": col + 1,
        "text": "value",
        "bbox": {"l": left, "r": right, "t": 100.0, "b": 90.0},
    }


class CheckTests(unittest.TestCase):
    def test_valid_document(self) -> None:
        report = check_document(document())
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["fingerprint"]["text_chars"], len("Source text"))

    def test_out_of_range_charspan_matches_reported_docling_failure(self) -> None:
        report = check_document(document("Dehyphenated text", 19))
        self.assertEqual(report["findings"][0]["code"], "invalid_charspan")

    def test_fused_table_cell_box_is_flagged(self) -> None:
        sample = document()
        sample["tables"] = [
            {
                "self_ref": "#/tables/0",
                "data": {
                    "num_rows": 1,
                    "num_cols": 2,
                    "table_cells": [cell(0, 0, 10.0, 90.0), cell(0, 1, 50.0, 100.0)],
                },
            }
        ]
        report = check_document(sample)
        self.assertEqual(report["findings"][0]["code"], "overlapping_cell_boxes")
        self.assertEqual(report["findings"][0]["severity"], "warning")

    def test_grid_collision_is_error(self) -> None:
        sample = document()
        sample["tables"] = [
            {
                "data": {
                    "num_rows": 1,
                    "num_cols": 1,
                    "table_cells": [cell(0, 0, 0, 10), cell(0, 0, 0, 10)],
                }
            }
        ]
        report = check_document(sample)
        self.assertIn("overlapping_cells", {item["code"] for item in report["findings"]})

    def test_compare_reports_text_loss_without_claiming_accuracy(self) -> None:
        before = document("alpha beta")
        after = document("alpha")
        report = compare_documents(before, after)
        self.assertEqual(report["drops"]["text_chars"], 5)
        self.assertEqual(report["removed_text_items"], 1)

    def test_loader_rejects_wrong_shape(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "wrong.json"
            path.write_text(json.dumps({"texts": []}))
            with self.assertRaises(DocumentError):
                load_document(path)

    def test_loader_rejects_nonfinite_json_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "nonstandard.json"
            values = (
                ("NaN", "Non-standard JSON constant: NaN"),
                ("Infinity", "Non-standard JSON constant: Infinity"),
                ("-Infinity", "Non-standard JSON constant: -Infinity"),
                ("1e999", "JSON number outside finite range: 1e999"),
            )
            for value, error in values:
                with self.subTest(value=value):
                    raw = (
                        '{"texts": [], "tables": [{"data": {"num_rows": 1, '
                        '"num_cols": 1, "table_cells": [{"start_row_offset_idx": 0, '
                        '"end_row_offset_idx": 1, "start_col_offset_idx": 0, '
                        '"end_col_offset_idx": 1, "bbox": {"l": '
                        + value
                        + ', "r": 10}}]}}]}'
                    )
                    path.write_text(raw, encoding="utf-8")
                    with self.assertRaisesRegex(
                        DocumentError, error
                    ):
                        load_document(path)

    def test_cli_check_failure(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "bad.json"
            path.write_text(json.dumps(document("word", 8)))
            with redirect_stdout(StringIO()) as output:
                code = main(["check", str(path), "--json"])
            self.assertEqual(code, 2)
            self.assertEqual(
                json.loads(output.getvalue())["findings"][0]["code"], "invalid_charspan"
            )

    def test_cli_fail_on_drop(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            before = Path(name) / "before.json"
            after = Path(name) / "after.json"
            before.write_text(json.dumps(document("full text")))
            after.write_text(json.dumps(document("text")))
            with redirect_stdout(StringIO()):
                code = main(["compare", str(before), str(after), "--fail-on-drop"])
            self.assertEqual(code, 1)


class RealDocumentTests(unittest.TestCase):
    """Regression fixtures from real Docling exports, not synthetic ones.

    See tests/data/real/SOURCES.md for provenance.
    """

    data_dir = Path(__file__).parent / "data" / "real"

    def _check(self, name: str) -> list[dict]:
        document = load_document(self.data_dir / name)
        return check_document(document)["findings"]

    def test_handbook_page_is_clean(self) -> None:
        self.assertEqual(self._check("amt_handbook_sample.json"), [])

    def test_right_to_left_document_is_clean(self) -> None:
        self.assertEqual(self._check("right_to_left_01.json"), [])

    def test_newspaper_dehyphenation_overshoot_is_caught(self) -> None:
        findings = self._check("newspaper-00.json")
        self.assertEqual(len(findings), 3)
        self.assertTrue(all(item["code"] == "invalid_charspan" for item in findings))

    def test_marker_item_is_not_a_false_positive(self) -> None:
        # "orig" keeps a list marker like "b. " that "text" strips. Earlier
        # versions compared charspan against len(text) and flagged this as
        # invalid on every enumerated item in the real corpus.
        orig = "b. Red-annotation of bounding boxes"
        item = {
            "text": "Red-annotation of bounding boxes",
            "orig": orig,
            "prov": [{"page_no": 1, "charspan": [0, len(orig)]}],
        }
        document = {"texts": [item], "tables": []}
        self.assertEqual(check_document(document)["findings"], [])


if __name__ == "__main__":
    unittest.main()
