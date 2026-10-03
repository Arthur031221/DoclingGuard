# Changelog

## Unreleased

- Reject non-standard `NaN` and infinity constants and overflowed numeric values
  such as `1e999` when loading JSON exports.

## 0.2.0

- Fix: check a text item's provenance charspan against `orig` length when
  `orig` is present, instead of `text` length. Docling strips enumeration
  markers such as `"b. "` from `text` but keeps them in `orig`, so the old
  check flagged most enumerated list items in real exports as invalid. This
  was found by running 0.1.0 against the 15 real Docling exports in the
  Docling project's own test suite: it reported errors in 9 of 15 documents,
  and all but 3 were this false positive.
- Add three real Docling JSON fixtures under `tests/data/real/` and a
  reproduction script, `scripts/measure_real_documents.sh`, for the full
  15-document measurement reported in the README.

## 0.1.0

- Validate text provenance spans and table-cell geometry in Docling JSON.
- Compare extraction size and exact normalized text between two exports.
- Provide JSON output and opt-in CI failure modes.
