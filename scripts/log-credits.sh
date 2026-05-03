#!/usr/bin/env bash
# Usage: log-credits.sh <issue-id> <delta> <duration_seconds> [model] [pr-url]
set -euo pipefail

ISSUE_ID="${1:?issue-id required}"
DELTA="${2:?delta required}"
DURATION="${3:?duration_seconds required}"
MODEL="${4:-sonnet}"
PR_URL="${5:-}"

DB="${REDACTRON_DB:-.redactron/credits.db}"

# Derive milestone from issue-id (e.g. BLD-7 -> M2)
milestone_from_id() {
  local raw="${1##*-}"  # strip prefix, get trailing part
  local id
  id=$(echo "$raw" | grep -o '^[0-9]*' || true)
  if [[ -z "$id" || ! "$id" =~ ^[0-9]+$ ]]; then echo "M1"; return; fi
  if   [[ $id -le 6  ]]; then echo "M1"
  elif [[ $id -le 12 ]]; then echo "M2"
  elif [[ $id -le 18 ]]; then echo "M3"
  elif [[ $id -le 22 ]]; then echo "M4"
  else                        echo "M5"
  fi
}
MILESTONE=$(milestone_from_id "$ISSUE_ID")

# Read latest total_after (default 0)
PREV=$(sqlite3 "$DB" "SELECT COALESCE(MAX(total_after),0) FROM usage;" 2>/dev/null || echo 0)
NEW_TOTAL=$(( PREV + DELTA ))
PCT=$(( NEW_TOTAL * 100 / 1000 ))
REMAINING=$(( 1000 - NEW_TOTAL ))

# Insert row
sqlite3 "$DB" "INSERT INTO usage (task_id, milestone, model, delta, duration_seconds, total_after, pr_url)
  VALUES ('${ISSUE_ID}', '${MILESTONE}', '${MODEL}', ${DELTA}, ${DURATION}, ${NEW_TOTAL}, $([ -n "$PR_URL" ] && echo "'${PR_URL}'" || echo "NULL"));"

echo "Logged: ${ISSUE_ID} | delta=${DELTA} | total=${NEW_TOTAL}/1000 (${PCT}%) | remaining=${REMAINING}"

# Post Linear comment
LINEAR_COMMENT="Task complete. Credits: ${DELTA} | Time: ${DURATION}s | Cumulative: ${NEW_TOTAL}/1000 (${PCT}%) | Remaining v1: ${REMAINING}"
if command -v linear-mcp &>/dev/null 2>&1; then
  : # MCP handled externally
fi

# Credit alert at >= 800
if [[ $NEW_TOTAL -ge 800 ]]; then
  echo "⚠️  CREDIT ALERT: ${NEW_TOTAL}/1000 credits used (${PCT}%). Only ${REMAINING} remaining for v1!"
fi

# Append to PR description if gh available and PR_URL provided
if [[ -n "$PR_URL" ]] && command -v gh &>/dev/null; then
  PR_NUM="${PR_URL##*/}"
  REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
  if [[ -n "$REPO" && "$PR_NUM" =~ ^[0-9]+$ ]]; then
    CURRENT_BODY=$(gh pr view "$PR_NUM" --repo "$REPO" --json body -q .body 2>/dev/null || echo "")
    gh pr edit "$PR_NUM" --repo "$REPO" --body "${CURRENT_BODY}

---
Credits: ${DELTA} | Time: ${DURATION}s" 2>/dev/null || true
  fi
fi

echo "$LINEAR_COMMENT"
