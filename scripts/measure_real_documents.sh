#!/bin/sh
# Reproduce the real-document measurement in the README.
# Downloads the 15 groundtruth Docling JSON exports from docling-project/docling
# and runs docling-guard check against each.
set -eu
COMMIT=d6f03078ad364108df3e7e82e8f0dcc3fd7f39ea
BASE="https://raw.githubusercontent.com/docling-project/docling/$COMMIT/tests/data/pdf/groundtruth"
DIR=$(mktemp -d)
FILES="2203.01017v2.json 2206.01062.json 2305.03393v1-pg9.json 2305.03393v1.json
amt_handbook_sample.json code_and_formula.json elsevier-00.json multi_page.json
newspaper-00.json normal_4pages.json picture_classification.json
redp5110_sampled.json right_to_left_01.json right_to_left_02.json right_to_left_03.json"
clean=0
total=0
for f in $FILES; do
  curl -fsSL "$BASE/$f" -o "$DIR/$f"
  total=$((total + 1))
  if docling-guard check "$DIR/$f" >/dev/null 2>&1; then
    clean=$((clean + 1))
  else
    echo "findings: $f"
    docling-guard check "$DIR/$f" || true
  fi
done
echo "$clean of $total documents passed with zero findings"
rm -rf "$DIR"
