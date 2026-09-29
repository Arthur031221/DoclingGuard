"""Generate a tiny fixture with one text drop and one invalid source span."""

import json
import tempfile
from pathlib import Path


def write_fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="docling-guard-demo-"))
    before = {
        "name": "sample",
        "texts": [
            {
                "self_ref": "#/texts/0",
                "text": "Invoice total is 42",
                "prov": [{"page_no": 1, "charspan": [0, 19]}],
            }
        ],
        "tables": [],
    }
    after = {
        "name": "sample",
        "texts": [
            {
                "self_ref": "#/texts/0",
                "text": "Invoice total",
                "prov": [{"page_no": 1, "charspan": [0, 15]}],
            }
        ],
        "tables": [],
    }
    (root / "before.json").write_text(json.dumps(before))
    (root / "after.json").write_text(json.dumps(after))
    return root
