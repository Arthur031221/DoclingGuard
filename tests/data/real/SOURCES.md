# Real document fixtures

These three files are Docling JSON exports from the Docling project's own
test suite, not synthetic fixtures. They were fetched on 2026-10-01 from
`docling-project/docling` at commit `d6f03078ad364108df3e7e82e8f0dcc3fd7f39ea`,
path `tests/data/pdf/groundtruth/`. Docling is MIT licensed; these files are
used here under that license, unmodified.

- `amt_handbook_sample.json`: a page from a technical handbook. No findings.
- `right_to_left_01.json`: a short right-to-left document. No findings.
- `newspaper-00.json`: a German-language newspaper interview. Three
  `invalid_charspan` findings, each a multi-span text item whose combined
  charspan runs 2 characters past `orig` length, the same dehyphenation
  pattern reported in
  [docling-project/docling#4217](https://github.com/docling-project/docling/issues/4217).

A fourth file in the same groundtruth set, `2203.01017v2.json` (an arXiv
paper on TableFormer), produces the same finding five times and is not
committed here because of its size; see the README for the full 15-document
measurement and how to reproduce it.
