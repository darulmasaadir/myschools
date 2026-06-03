#!/usr/bin/env bash
#
# PR verification battery — single entry point.
#
# Runs every *automatable* item from .cursor/rules/pr-verification.mdc in order
# and prints the status table. On success it writes a sentinel
# (.cursor/.pr-battery-pass) stamped with the current commit SHA. The
# `require-battery` Cursor hook refuses `gh pr create` / `gh pr merge` /
# `gh pr ready` unless that sentinel matches HEAD — so a PR cannot be
# finalised without this having run green against the exact commit.
#
# Usage:
#   scripts/pr_battery.sh                 # default site myschools.localhost
#   scripts/pr_battery.sh other.localhost
#
# Manual items (fresh-install, browser, PDF, role matrix) are NOT auto-run;
# they are printed as REQUIRES-JUDGEMENT and must be ticked in the PR body.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

SITE="${1:-myschools.localhost}"
BENCH="$ROOT/frappe-bench"
APP_DIR="$BENCH/apps/myschools"
SENTINEL="$ROOT/.cursor/.pr-battery-pass"
HEAD_SHA="$(git rev-parse HEAD)"

red()   { printf '\033[31m%s\033[0m' "$1"; }
green() { printf '\033[32m%s\033[0m' "$1"; }

declare -a NAMES STATUSES
overall=0

run_step() {
  local name="$1"; shift
  echo ""
  echo "=== ${name} ==="
  if "$@"; then
    NAMES+=("$name"); STATUSES+=("PASS")
  else
    NAMES+=("$name"); STATUSES+=("FAIL")
    overall=1
  fi
}

step_precommit() {
  ( cd "$APP_DIR" && pre-commit run --all-files )
}

step_tests_coverage() {
  ( cd "$BENCH" && bench --site "$SITE" run-tests --app myschools --coverage )
}

step_coverage_floor() {
  ( cd "$BENCH" && ./env/bin/python apps/myschools/myschools/scripts/check_coverage_floor.py )
}

step_http_smoke() {
  ( cd "$BENCH" && ./env/bin/python -c \
      "from myschools.scripts.verify_http_battery import run; run(host='${SITE}')" )
}

step_branch_matrix() {
  ( cd "$BENCH" && bench --site "$SITE" execute \
      myschools.scripts.verify_branch_desk_cards.run )
}

echo "PR battery — site=${SITE} commit=${HEAD_SHA:0:12}"

run_step "2. Lint / pre-commit"            step_precommit
run_step "1. Unit tests (+coverage data)"  step_tests_coverage
run_step "8. Role x surface (branch desk)" step_branch_matrix
run_step "Coverage floor"                  step_coverage_floor
run_step "3. HTTP smoke (dev site)"        step_http_smoke

echo ""
echo "========================================================"
echo "Battery for commit ${HEAD_SHA:0:12} (site ${SITE})"
echo "--------------------------------------------------------"
for i in "${!NAMES[@]}"; do
  if [[ "${STATUSES[$i]}" == "PASS" ]]; then
    printf '  %s  %s\n' "$(green "PASS")" "${NAMES[$i]}"
  else
    printf '  %s  %s\n' "$(red FAIL)" "${NAMES[$i]}"
  fi
done
echo "--------------------------------------------------------"
echo "REQUIRES JUDGEMENT — tick these in the PR body, never drop silently:"
echo "  4.  Fresh-install smoke (drop-site -> new-site -> install-app -> migrate)"
echo "  4b. Fresh-install BROWSER pass (real login on the fresh site)"
echo "  5.  Browser visual on dev (every role x surface cell)"
echo "  6.  PDF round-trip (only if a print format changed)"
echo "  9.  CI terminal-green (gh pr checks <N> — pending != green)"
echo "========================================================"

if [[ "$overall" -eq 0 ]]; then
  mkdir -p "$ROOT/.cursor"
  printf '%s\n' "$HEAD_SHA" > "$SENTINEL"
  echo ""
  green "Automatable battery PASSED"; echo " — sentinel written for ${HEAD_SHA:0:12}."
  echo "You may now open / merge the PR once the REQUIRES-JUDGEMENT items above"
  echo "and CI (item 9) are addressed."
  exit 0
else
  rm -f "$SENTINEL"
  echo ""
  red "Battery FAILED"; echo " — sentinel cleared. Fix the failing step(s) above and re-run."
  exit 1
fi
