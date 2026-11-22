#!/usr/bin/env bash
# Offline checks of this release, standard library Python only, no network.
# Stops with a non zero exit on the first mismatch.
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1. data files match data/SHA256SUMS"
(cd data && sha256sum -c SHA256SUMS 2>/dev/null || shasum -a 256 -c SHA256SUMS)

echo "== 2. unit tests (classifier and forward logger)"
# The logger tests print JSON run summaries; show only the unittest verdict, keep its exit code.
if ! out=$(python3 -I -B -m unittest discover -s scripts -p 'test_*.py' 2>&1); then
  echo "$out"; exit 1
fi
echo "$out" | grep -E '^(Ran|OK)'

echo "== 3. class rule on the 100 market check"
python3 -I -B scripts/16_check_class_rule.py

echo "== 4. dispute headline figures (README finding 1)"
python3 -I -B scripts/reproduce_headlines.py

echo "== 5. other figures recomputable from shipped data"
python3 -I -B scripts/15_check_headlines.py

echo "All checks passed."
