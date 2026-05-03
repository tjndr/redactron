#!/usr/bin/env bash
# Test for log-credits.sh using a temp SQLite DB
set -euo pipefail

SCRIPT="$(dirname "$0")/log-credits.sh"
TMPDB=$(mktemp /tmp/credits_test_XXXXXX.db)
trap 'rm -f "$TMPDB"' EXIT

# Bootstrap schema
sqlite3 "$TMPDB" "CREATE TABLE usage (
  id INTEGER PRIMARY KEY,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  task_id TEXT, milestone TEXT, model TEXT,
  delta INTEGER, duration_seconds INTEGER,
  total_after INTEGER, pr_url TEXT, notes TEXT
);"

export REDACTRON_DB="$TMPDB"

# Test 1: first insert, total should be 77
REDACTRON_DB="$TMPDB" bash "$SCRIPT" "BLD-1..6" 77 0 mixed "" >/dev/null
TOTAL=$(sqlite3 "$TMPDB" "SELECT total_after FROM usage ORDER BY id DESC LIMIT 1;")
[[ "$TOTAL" == "77" ]] || { echo "FAIL test1: expected 77, got $TOTAL"; exit 1; }
echo "PASS test1: first insert total_after=77"

# Test 2: second insert adds delta
REDACTRON_DB="$TMPDB" bash "$SCRIPT" "BLD-7" 50 120 sonnet "" >/dev/null
TOTAL=$(sqlite3 "$TMPDB" "SELECT total_after FROM usage ORDER BY id DESC LIMIT 1;")
[[ "$TOTAL" == "127" ]] || { echo "FAIL test2: expected 127, got $TOTAL"; exit 1; }
echo "PASS test2: cumulative total_after=127"

# Test 3: milestone derivation
MILESTONE=$(sqlite3 "$TMPDB" "SELECT milestone FROM usage WHERE task_id='BLD-7';")
[[ "$MILESTONE" == "M2" ]] || { echo "FAIL test3: expected M2, got $MILESTONE"; exit 1; }
echo "PASS test3: milestone=M2 for BLD-7"

# Test 4: alert fires at >= 800
OUTPUT=$(REDACTRON_DB="$TMPDB" bash "$SCRIPT" "BLD-99" 700 60 sonnet "" 2>&1)
if echo "$OUTPUT" | grep -q "CREDIT ALERT"; then
  echo "PASS test4: credit alert fires at >=800"
else
  echo "FAIL test4: expected credit alert"; exit 1
fi

echo "All tests passed."
