#!/usr/bin/env bash
#
# beforeShellExecution gate: refuse to finalise a PR unless the PR verification
# battery (scripts/pr_battery.sh) has run green against the *current* commit.
#
# Fires only for `gh pr create` / `gh pr merge` / `gh pr ready` (see matcher in
# .cursor/hooks.json). For everything else it allows immediately.
#
# Decision:
#   - sentinel (.cursor/.pr-battery-pass) SHA == HEAD SHA  -> allow
#   - otherwise                                            -> ask (with reason)
set -uo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.command // empty' 2>/dev/null)"

# Only gate PR finalisation commands; anything else passes straight through.
if ! printf '%s' "$command" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+(create|merge|ready)'; then
  echo '{ "permission": "allow" }'
  exit 0
fi

root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$root" ]]; then
  echo '{ "permission": "allow" }'
  exit 0
fi

sentinel="$root/.cursor/.pr-battery-pass"
head_sha="$(git -C "$root" rev-parse HEAD 2>/dev/null)"
sentinel_sha=""
[[ -f "$sentinel" ]] && sentinel_sha="$(tr -d '[:space:]' < "$sentinel")"

if [[ -n "$head_sha" && "$sentinel_sha" == "$head_sha" ]]; then
  echo '{ "permission": "allow" }'
  exit 0
fi

short="${head_sha:0:12}"
agent_msg="PR-battery gate: scripts/pr_battery.sh has NOT passed for the current commit (${short}). \
Run it and address the REQUIRES-JUDGEMENT items (fresh-install, browser, PDF, CI terminal-green) \
BEFORE creating/merging this PR. Do not bypass — re-run the battery on the exact commit you intend to ship."
user_msg="The PR verification battery has not been run green against the current commit (${short}). \
Cursor is blocking PR finalisation until 'scripts/pr_battery.sh' passes for this commit."

jq -n --arg a "$agent_msg" --arg u "$user_msg" \
  '{permission:"ask", agent_message:$a, user_message:$u}'
exit 0
