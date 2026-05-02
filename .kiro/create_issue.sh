#!/usr/bin/env bash
# Usage: create_issue.sh "title" "milestone_id" "state_id" "label_ids_json" "description"
TEAM_ID="b2216415-f525-4ff0-a658-afd510af8369"
PROJECT_ID="cd5cdf0a-1fa3-497a-93a5-e5392ec9215b"

TITLE="$1"
MILESTONE_ID="$2"
STATE_ID="$3"
LABEL_IDS="$4"  # JSON array string e.g. ["id1","id2"]
DESCRIPTION="$5"

# Escape title and description for JSON
TITLE_ESC=$(echo "$TITLE" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
DESC_ESC=$(echo "$DESCRIPTION" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

QUERY="mutation {
  issueCreate(input: {
    teamId: \"$TEAM_ID\",
    projectId: \"$PROJECT_ID\",
    projectMilestoneId: \"$MILESTONE_ID\",
    stateId: \"$STATE_ID\",
    title: $TITLE_ESC,
    description: $DESC_ESC,
    labelIds: $LABEL_IDS
  }) {
    issue { id title identifier url }
  }
}"

curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"query\": $(echo "$QUERY" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); i=d['data']['issueCreate']['issue']; print(i['identifier'], i['url'])"
