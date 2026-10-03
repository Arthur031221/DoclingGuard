"""Schema-aware quality checks for Docling JSON documents."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_GEOMETRY_CELLS = 2000


class DocumentError(ValueError):
    """An input file cannot be inspected safely."""


class _InvalidJSONNumber(ValueError):
    """A JSON number cannot be represented as a finite Python float."""


def _reject_json_constant(value: str) -> None:
    raise _InvalidJSONNumber(f"Non-standard JSON constant: {value}")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _InvalidJSONNumber(f"JSON number outside finite range: {value}")
    return parsed


def load_document(path: Path) -> dict[str, Any]:
    """Load a bounded JSON file without requiring Docling or model weights."""
    try:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise DocumentError(f"File exceeds the 64 MiB limit: {path}")
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(
                stream,
                parse_constant=_reject_json_constant,
                parse_float=_parse_json_float,
            )
    except (_InvalidJSONNumber, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DocumentError(f"Cannot read Docling JSON {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise DocumentError("Docling JSON must be an object")
    if not isinstance(document.get("texts"), list) or not isinstance(
        document.get("tables"), list
    ):
        raise DocumentError("Docling JSON must contain texts and tables arrays")
    return document


def _finding(code: str, severity: str, location: str, detail: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "location": location, "detail": detail}


def _check_provenance(item: dict[str, Any], location: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    text = item.get("text")
    if not isinstance(text, str):
        return [_finding("invalid_text", "error", location, "Text item has no string text")]
    orig = item.get("orig")
    # charspan indexes into orig, not text: Docling strips enumeration markers like
    # "b. " from text but keeps them in orig, so a marker item's span legitimately
    # extends past len(text). Falling back to len(text) only when orig is absent
    # preserves detection of the real dehyphenation overshoot this tool targets.
    span_bound = len(orig) if isinstance(orig, str) else len(text)
    prov = item.get("prov", [])
    if not isinstance(prov, list):
        return [_finding("invalid_provenance", "error", location, "prov must be an array")]
    for index, entry in enumerate(prov):
        span = entry.get("charspan") if isinstance(entry, dict) else None
        if not (
            isinstance(span, list)
            and len(span) == 2
            and all(isinstance(value, int) and not isinstance(value, bool) for value in span)
            and 0 <= span[0] <= span[1] <= span_bound
        ):
            findings.append(
                _finding(
                    "invalid_charspan",
                    "error",
                    f"{location}/prov/{index}",
                    f"charspan must lie within source text length {span_bound}",
                )
            )
    return findings


def _rectangle(cell: dict[str, Any]) -> tuple[int, int, int, int] | None:
    keys = (
        "start_row_offset_idx",
        "end_row_offset_idx",
        "start_col_offset_idx",
        "end_col_offset_idx",
    )
    values = [cell.get(key) for key in keys]
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return None
    return tuple(values)  # type: ignore[return-value]


def _bbox_x(cell: dict[str, Any]) -> tuple[float, float] | None:
    bbox = cell.get("bbox")
    if not isinstance(bbox, dict):
        return None
    left, right = bbox.get("l"), bbox.get("r")
    if not all(isinstance(value, (int, float)) for value in (left, right)):
        return None
    return float(min(left, right)), float(max(left, right))


def _check_table(item: dict[str, Any], location: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    data = item.get("data")
    if not isinstance(data, dict):
        return [_finding("invalid_table", "error", location, "Table has no data object")]
    rows, cols, cells = data.get("num_rows"), data.get("num_cols"), data.get("table_cells")
    if not (
        isinstance(rows, int)
        and not isinstance(rows, bool)
        and rows >= 0
        and isinstance(cols, int)
        and not isinstance(cols, bool)
        and cols >= 0
        and isinstance(cells, list)
    ):
        return [_finding("invalid_table", "error", location, "Invalid dimensions or table_cells")]
    rectangles: list[tuple[int, int, int, int, int, tuple[float, float] | None]] = []
    for index, cell in enumerate(cells):
        where = f"{location}/data/table_cells/{index}"
        if not isinstance(cell, dict):
            findings.append(_finding("invalid_cell", "error", where, "Cell is not an object"))
            continue
        rect = _rectangle(cell)
        if rect is None or not (
            0 <= rect[0] < rect[1] <= rows and 0 <= rect[2] < rect[3] <= cols
        ):
            findings.append(
                _finding("invalid_cell_bounds", "error", where, "Cell is outside table")
            )
            continue
        rectangles.append((*rect, index, _bbox_x(cell)))
    if len(rectangles) > MAX_GEOMETRY_CELLS:
        findings.append(
            _finding(
                "geometry_skipped",
                "warning",
                location,
                f"Overlap check limited to {MAX_GEOMETRY_CELLS} cells per table",
            )
        )
        return findings
    rectangles.sort()
    for first_index, first in enumerate(rectangles):
        for second in rectangles[first_index + 1 :]:
            if second[0] >= first[1]:
                break
            row_overlap = first[0] < second[1] and second[0] < first[1]
            col_overlap = first[2] < second[3] and second[2] < first[3]
            if row_overlap and col_overlap:
                findings.append(
                    _finding(
                        "overlapping_cells",
                        "error",
                        location,
                        f"Cells {first[4]} and {second[4]} occupy the same grid position",
                    )
                )
            elif (
                row_overlap
                and first[3] - first[2] == 1
                and second[3] - second[2] == 1
                and first[5] is not None
                and second[5] is not None
                and first[5][0] < second[5][1]
                and second[5][0] < first[5][1]
            ):
                findings.append(
                    _finding(
                        "overlapping_cell_boxes",
                        "warning",
                        location,
                        f"Cells {first[4]} and {second[4]} have overlapping x coordinates",
                    )
                )
    return findings


def check_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return findings and a small extraction fingerprint."""
    findings: list[dict[str, str]] = []
    texts = document["texts"]
    tables = document["tables"]
    normalized_text: list[str] = []
    for index, item in enumerate(texts):
        location = f"#/texts/{index}"
        if not isinstance(item, dict):
            findings.append(
                _finding("invalid_text", "error", location, "Text item is not an object")
            )
            continue
        findings.extend(_check_provenance(item, location))
        if isinstance(item.get("text"), str):
            normalized_text.append(" ".join(item["text"].split()))
    cell_count = 0
    for index, item in enumerate(tables):
        location = f"#/tables/{index}"
        if not isinstance(item, dict):
            findings.append(_finding("invalid_table", "error", location, "Table is not an object"))
            continue
        findings.extend(_check_table(item, location))
        data = item.get("data")
        if isinstance(data, dict) and isinstance(data.get("table_cells"), list):
            cell_count += len(data["table_cells"])
    fingerprint = {
        "text_items": len(texts),
        "text_chars": sum(len(text) for text in normalized_text),
        "tables": len(tables),
        "table_cells": cell_count,
    }
    return {"findings": findings, "fingerprint": fingerprint, "text": normalized_text}


def compare_documents(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare extraction volume and exact normalized text without claiming semantic equivalence."""
    baseline = check_document(before)
    candidate = check_document(after)
    older = Counter(baseline["text"])
    newer = Counter(candidate["text"])
    removed = list((older - newer).elements())
    added = list((newer - older).elements())
    drops = {
        key: baseline["fingerprint"][key] - candidate["fingerprint"][key]
        for key in ("text_items", "text_chars", "tables", "table_cells")
        if candidate["fingerprint"][key] < baseline["fingerprint"][key]
    }
    return {
        "before": baseline["fingerprint"],
        "after": candidate["fingerprint"],
        "drops": drops,
        "removed_text_items": len(removed),
        "added_text_items": len(added),
        "removed_samples": removed[:3],
        "added_samples": added[:3],
        "before_findings": baseline["findings"],
        "after_findings": candidate["findings"],
    }
