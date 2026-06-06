#!/usr/bin/env bash
#
# PR verification battery — single entry point, FULL end-to-end gate.
#
# A PR branch must be fully tested BEFORE its PR is created. This script:
#
#   STAGE 1 (local, fast)  lint/pre-commit, unit tests + coverage, coverage
#                          floor, role×surface branch-desk matrix, HTTP smoke
#                          on the dev site. Fast feedback before spending CI.
#
#   STAGE 2 (CI, full e2e) requires the branch to be pushed and the CI run for
#                          the EXACT current commit to be terminal-green. CI is
#                          the canonical full battery: fresh-install (drop +
#                          new-site + install-app + migrate), seed, branch
#                          matrix, live HTTP battery, and Playwright browser
#                          e2e. We do not fake this locally — we require the
#                          real run to be green for this commit.
#
# On success it writes .cursor/.pr-battery-pass stamped with the current commit
# SHA. The require-battery Cursor hook refuses `gh pr create|merge|ready` unless
# that sentinel matches HEAD — so a PR cannot be opened until its branch passed
# the full battery end-to-end on the exact commit being shipped.
#
# Usage:
#   scripts/pr_battery.sh                 # dev site myschools.localhost
#   scripts/pr_battery.sh other.localhost
#   SKIP_CI_WAIT=1 scripts/pr_battery.sh  # local stage only (NOT a PR gate)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

SITE="${1:-myschools.localhost}"
BENCH="$ROOT/frappe-bench"
APP_DIR="$BENCH/apps/myschools"
SENTINEL="$ROOT/.cursor/.pr-battery-pass"
HEAD_SHA="$(git rev-parse HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
CI_WORKFLOW="CI"
CI_WAIT_SECONDS="${CI_WAIT_SECONDS:-2400}"   # poll up to 40 min by default

red()   { printf '\033[31m%s\033[0m' "$1"; }
green() { printf '\033[32m%s\033[0m' "$1"; }

declare -a NAMES STATUSES
overall=0

run_step() {
  local name="$1"; shift
  echo ""; echo "=== ${name} ==="
  if "$@"; then NAMES+=("$name"); STATUSES+=("PASS")
  else NAMES+=("$name"); STATUSES+=("FAIL"); overall=1; fi
}

step_precommit()       { ( cd "$APP_DIR" && pre-commit run --all-files ); }
step_tests_coverage()  { ( cd "$BENCH" && bench --site "$SITE" run-tests --app myschools --coverage ); }
step_coverage_floor()  { ( cd "$BENCH" && ./env/bin/python apps/myschools/myschools/scripts/check_coverage_floor.py ); }
step_http_smoke()      { ( cd "$BENCH" && ./env/bin/python -c "from myschools.scripts.verify_http_battery import run; run(host='${SITE}')" ); }
step_branch_matrix()   { ( cd "$BENCH" && bench --site "$SITE" execute myschools.scripts.verify_branch_desk_cards.run ); }
step_late_fee_e2e()    { ( cd "$BENCH" && bench --site "$SITE" execute myschools.scripts.verify_late_fees.run ); }
step_fee_admin_matrix() { ( cd "$BENCH" && bench --site "$SITE" execute myschools.scripts.verify_fee_admin_surfaces.run ); }
step_student_lifecycle_matrix() { ( cd "$BENCH" && bench --site "$SITE" execute myschools.scripts.verify_student_lifecycle_surfaces.run ); }
step_sms_adapters() { ( cd "$BENCH" && bench --site "$SITE" execute myschools.scripts.verify_sms_adapters.run ); }

echo "PR battery — site=${SITE} branch=${BRANCH} commit=${HEAD_SHA:0:12}"
echo "###############  STAGE 1 — local fast checks  ###############"

run_step "2. Lint / pre-commit"            step_precommit
run_step "1. Unit tests (+coverage data)"  step_tests_coverage
run_step "8. Role x surface (branch desk)" step_branch_matrix
run_step "8. Role x surface (fee admin)"   step_fee_admin_matrix
run_step "8. Role x surface (student lifecycle)" step_student_lifecycle_matrix
run_step "SMS adapter smoke (8c)"          step_sms_adapters
run_step "Late-fee scheduler e2e (8a)"     step_late_fee_e2e
run_step "Coverage floor"                  step_coverage_floor
run_step "3. HTTP smoke (dev site)"        step_http_smoke

print_table() {
  echo ""; echo "========================================================"
  echo "Battery for commit ${HEAD_SHA:0:12} (site ${SITE})"
  echo "--------------------------------------------------------"
  for i in "${!NAMES[@]}"; do
    if [[ "${STATUSES[$i]}" == "PASS" ]]; then printf '  %s  %s\n' "$(green "PASS")" "${NAMES[$i]}"
    else printf '  %s  %s\n' "$(red FAIL)" "${NAMES[$i]}"; fi
  done
  echo "--------------------------------------------------------"
}

if [[ "$overall" -ne 0 ]]; then
  print_table
  rm -f "$SENTINEL"
  echo ""; red "STAGE 1 FAILED"; echo " — fix the local step(s) above before pushing. Sentinel cleared."
  exit 1
fi
print_table
green "STAGE 1 PASSED"; echo ""

# ---------------------------------------------------------------------------
# STAGE 2 — require the FULL CI battery (fresh-install + browser e2e) to be
# terminal-green for THIS commit. This is the end-to-end gate.
# ---------------------------------------------------------------------------
if [[ "${SKIP_CI_WAIT:-0}" == "1" ]]; then
  echo "SKIP_CI_WAIT=1 set — skipping the CI end-to-end gate."
  echo "This run does NOT satisfy the PR gate; sentinel NOT written."
  exit 0
fi

echo "###############  STAGE 2 — CI end-to-end gate  ###############"

if ! command -v gh >/dev/null 2>&1; then
  red "gh CLI not found"; echo " — cannot verify CI. Install gh or set SKIP_CI_WAIT=1 (not a real gate)."
  exit 1
fi

git fetch origin "$BRANCH" -q 2>/dev/null || true
REMOTE_SHA="$(git rev-parse "origin/${BRANCH}" 2>/dev/null || echo "")"
if [[ "$REMOTE_SHA" != "$HEAD_SHA" ]]; then
  red "Branch not pushed at this commit"; echo ""
  echo "  origin/${BRANCH} = ${REMOTE_SHA:0:12} , HEAD = ${HEAD_SHA:0:12}"
  echo "  Push first so CI runs the full battery on this commit:  git push"
  exit 1
fi

echo "Waiting for CI workflow '${CI_WORKFLOW}' to be terminal-green for ${HEAD_SHA:0:12} (≤ ${CI_WAIT_SECONDS}s)…"
deadline=$(( $(date +%s) + CI_WAIT_SECONDS ))
while :; do
  run_json="$(gh run list --branch "$BRANCH" --limit 25 \
      --json databaseId,headSha,status,conclusion,workflowName 2>/dev/null \
      | jq -c --arg sha "$HEAD_SHA" --arg wf "$CI_WORKFLOW" \
          'map(select(.headSha==$sha and .workflowName==$wf)) | sort_by(.databaseId) | last // empty')"

  if [[ -z "$run_json" || "$run_json" == "null" ]]; then
    if (( $(date +%s) >= deadline )); then
      red "No CI run found for ${HEAD_SHA:0:12} within timeout."
      echo "  Is CI configured to run on this branch? (push triggers feature/**)"
      exit 1
    fi
    echo "  …no CI run for this commit yet; waiting."
    sleep 15; continue
  fi

  status="$(printf '%s' "$run_json"   | jq -r '.status')"
  conclusion="$(printf '%s' "$run_json" | jq -r '.conclusion')"
  run_id="$(printf '%s' "$run_json"   | jq -r '.databaseId')"

  if [[ "$status" == "completed" ]]; then
    if [[ "$conclusion" == "success" ]]; then
      green "CI terminal-green"; echo " for ${HEAD_SHA:0:12} (run ${run_id})."
      break
    fi
    red "CI concluded '${conclusion}'"; echo " for ${HEAD_SHA:0:12} (run ${run_id})."
    echo "  Inspect:  gh run view ${run_id} --log-failed"
    exit 1
  fi

  if (( $(date +%s) >= deadline )); then
    red "CI still '${status}' after timeout"; echo " (run ${run_id}). Re-run this script to keep waiting."
    exit 1
  fi
  echo "  …CI ${status} (run ${run_id}); waiting."
  sleep 20
done

# ---------------------------------------------------------------------------
mkdir -p "$ROOT/.cursor"
printf '%s\n' "$HEAD_SHA" > "$SENTINEL"
echo ""
echo "========================================================"
green "FULL BATTERY PASSED"; echo " — local checks green AND CI end-to-end green for ${HEAD_SHA:0:12}."
echo "Sentinel written. The PR gate will now allow gh pr create / merge / ready."
echo ""
echo "Still confirm in the PR body (judgement-only, not auto-gated):"
echo "  • PDF round-trip — only if a print format changed this PR."
echo "  • Any brand-new surface with no Playwright spec yet — walk it once, then add a spec."
echo "========================================================"
exit 0
