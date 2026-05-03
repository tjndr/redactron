We are building `redactron`, a local-only CLI for batch PII redaction in PDFs.

Read these files first, in order:
  1. .kiro/steering/product.md
  2. .kiro/steering/tech.md
  3. .kiro/steering/conventions.md
  4. .kiro/settings/mcp.json

Then connect to the Linear MCP server (linear) and the GitHub MCP server (github).
Verify both are reachable. If Linear OAuth needs browser auth, prompt me.

Your first job is to bootstrap the project end-to-end.

0. RESOLVE LINEAR TEAM (do this first, before any Linear creation):
   - Call linear.list_teams() and show me the result.
   - If exactly ONE team: name it explicitly, ask "Use team <Name> (identifier <ID>)?"
     and wait for "yes".
   - If MULTIPLE teams: list each with name, identifier, member count; ask which to use.
   - If ZERO teams: stop and ask me to create a team via Linear UI, then re-run.
   - Once resolved, store the team identifier (e.g. RED). All Linear ops scope to it.
     Issues will auto-generate as <ID>-1 ... <ID>-28 from this team's prefix.

1. Create a Linear project named "Redactron" under the resolved team if it doesn't
   already exist. If it does, use it as-is and skip to step 2.

2. Create 5 milestones (skip any that already exist):
   - M1 Core engine             (target +4 days)
   - M2 Profile + variants      (target +7 days)
   - M3 Verification + audit    (target +10 days)
   - M4 Polish + launch         (target +14 days)
   - M5 Web UI (v1.5)           (target +21 days, status: Backlog)

3. Create 28 Linear issues from the task list below, assign each to its milestone,
   and add the matching phase label (phase-1..phase-5). M1–M4 issues (22 total)
   go into Cycle 1 in sequential order. M5 issues (6 total) stay in Backlog state
   until v1 ships. Skip any issue whose title already exists (idempotent).

4. VERIFY (do not recreate) the GitHub repo tjndr/redactron:
   - Call github.get_repo("tjndr/redactron").
   - If it does NOT exist: STOP and ask me before creating. Do not auto-create.
   - If it exists:
       a. Inspect contents. If any files exist, tell me what's there and ask
          whether to (i) preserve and add ours alongside, or (ii) overwrite.
       b. If empty: push initial commit with AGPL-3.0 LICENSE, Python .gitignore,
          README stub, and the .kiro/ + spec files.
       c. Configure main branch protection: require PR before merge, require
          status checks to pass, dismiss stale reviews on push.
       d. Confirm the repo stays PRIVATE.

5. Generate the spec files in .kiro/specs/redactron/:
   - requirements.md  (user stories from product.md, acceptance per milestone)
   - design.md        (architecture, data flow, module boundaries)
   - tasks.md         (28 issues with implementation notes, mapping each to its Linear ID)

5a. Set the Linear project description to:
    "Redactron: a local-only CLI that batch-redacts PII from PDFs using a user
     profile, with verification and audit logging. Python + PyMuPDF + Presidio.
     AGPL-3.0. v1 ships in 14 focused days; v1.5 adds a Gradio web UI."

5b. Create FOUR Linear project documents in the Redactron project:
    - "Architecture" — repo layout, module boundaries, mermaid data-flow diagram:
        PDF → extract → detect → redact → verify → audit log + report
    - "Data model" — profile.yaml schema, audit DB schema, CLI surface
    - "Conventions and risks" — full conventions.md content + risks table:
        | Risk | Mitigation |
        | PyMuPDF AGPL scares some users | Document in PRIVACY.md; pikepdf alt path in v2 |
        | Presidio NER misses non-English names | Profile aliases override; document |
        | Over-redaction false positives | full_token_min_length: 2; dry-run; threshold |
        | Mid-string partial redaction bbox math wrong | get_text("rawdict") char positions |
        | OCR accuracy on poor scans | Min DPI 300; flag low-confidence |
        | Format drift in PyMuPDF/Presidio | Pin exact versions; renovate weekly |
        | Kiro hits credit budget | Haiku for boilerplate; Sonnet for logic-heavy |
    - "Credit Budget" — use this template:

        # Redactron — Credit Budget

        ## Allocation
        | Milestone               | Planned | Actual | Status      |
        | M1 Core engine          | 280     | TBD    | not started |
        | M2 Profile + variants   | 310     | TBD    | not started |
        | M3 Verification + audit | 250     | TBD    | not started |
        | M4 Polish + launch      | 120     | TBD    | not started |
        | M5 Web UI (v1.5)        | 300     | TBD    | not started |
        | Buffer                  | 40      | n/a    | n/a         |
        | **Total**               | **1300**| TBD    |             |

        ## Running total
        Used: 0
        Remaining: 1000 (v1) / 1300 (v1+v1.5)
        Last updated: <bootstrap timestamp>

        ## Burn-rate alerts
        - WARNING at 80% of v1 (800 credits)
        - CRITICAL at 95% of v1 (950 credits)

        ## Per-issue actuals (sorted by cost desc)
        (Empty until first task completes.)

5c. For each milestone, set its description to the matching acceptance criteria:
    - M1: redactron run <single-file.pdf> redacts a known PII string and produces output;
          output passes verification; CI green on Linux + macOS.
    - M2: profile YAML loads/validates/drives detection; "100 Phillip Street" matches
          "100 Philip St" via fuzzy; 1234-5678-9012-3456 redacts to XXXX-XXXX-XXXX-3456;
          folder of 10 mixed PDFs processes in one command.
    - M3: every run produces verification report (markdown + JSON); audit log queryable
          by redactron log --subject <id>; dry-run shows what would be redacted.
    - M4: image-only PDF gets OCR'd and redacted; 10 synthetic test PDFs all pass; README
          quickstart + demo GIF; pip install redactron works from PyPI; launch post drafted.
    - M5: redactron ui opens browser with working web UI; drag-drop folder, redact in real time,
          download zip; visual diff overlay per page; profile editable via UI; audit log in UI.

5d. For each issue, populate the description with this template:

       ## Goal
       <one sentence>

       ## Implementation notes
       <bullets from the task list below>

       ## Files touched
       <paths from the repo layout below>

       ## Acceptance criteria
       - [ ] Unit tests pass
       - [ ] mypy strict passes for affected modules
       - [ ] <task-specific criteria>

       ## Model preference
       sonnet | haiku  (Sonnet for tricky logic; Haiku for boilerplate/docs/tests)

       ## Linked spec
       .kiro/specs/redactron/tasks.md#<anchor>

5e. Add labels to each issue:
    - phase-1, phase-2, phase-3, phase-4, phase-5 (one per issue, matching milestone)
    - type: feat | infra | docs | test (one per issue)
    - model: sonnet | haiku (one per issue)

5f. Idempotency: before creating any Linear entity, check if one with the same
    name/identifier exists. If yes, update in place. If no, create. Never duplicate.
    Report counts: "existing reused: N, newly created: M".

5g. Create four custom views in the Redactron project:
    - "By milestone" — grouped by milestone, sorted by status
    - "Current cycle" — what's being worked on this week
    - "Blocked / needs review" — anything Blocked or PR-pending
    - "By model" — grouped by sonnet/haiku label (for credit budget tracking)

5h. CREDIT USAGE TRACKING (mandatory after every PR opens):
    Run scripts/log-credits.sh immediately after opening each PR:
        bash scripts/log-credits.sh <issue-id> <delta> <duration_seconds> [model] [pr-url]
    Do NOT parse chat output or use /usage commands. The script reads
    .redactron/credits.db for the running total, inserts the new row,
    prints the Linear comment text, and fires a credit alert if >= 800.
    Estimate delta from the task complexity if an exact count is unavailable.

6. Run `uv init` and create pyproject.toml with the locked stack from tech.md
   (Python 3.11, PyMuPDF, presidio-analyzer, presidio-anonymizer, rapidfuzz,
   usaddress, pytesseract, typer, pydantic v2; pytest/ruff/mypy as dev deps;
   gradio behind an [ui] optional extra for v1.5).

7. Push the initial commit to GitHub on main.

8. Stop and show me a status report:
   - Linear: project URL, all 5 milestone URLs, total issue count (28), URLs for
     the 4 project documents (Architecture, Data model, Conventions and risks,
     Credit Budget)
   - GitHub: repo URL, initial commit SHA, branch protection state
   - Local: tree of created files including .redactron/credits.db
   - Next task suggested with its Linear ID and branch name

Do NOT start implementation tasks (M1.3 onward) until I explicitly confirm.

For every subsequent task:
  - Move the Linear issue to "In Progress"
  - Create branch <phase>/<linear-id>-short-desc (e.g. m2/bld-7-profile-schema)
  - Implement, write tests, run: uv run pytest && uv run ruff check && uv run mypy src/
  - Only when all three pass: commit (conventional commit), push, open PR closing
    the Linear issue ("Closes BLD-N" in PR body)
  - Immediately enable auto-merge with squash:
        gh pr merge --auto --squash --delete-branch
    GitHub will auto-merge as soon as all 4 CI checks pass and delete the branch.
  - EXCEPTIONS — do NOT enable auto-merge for these issues; open the PR and stop,
    wait for my explicit "merge it" approval before continuing to the next task:
        - BLD-10 (M2.4 partial redaction with last-4 bbox math)
        - BLD-13 (M3.1 verifier module)
        - BLD-19 (M4.1 OCR fallback / image-region painting)
  - Capture your task summary line and execute the credit tracking workflow (5h)
  - For non-exception tasks:
        a. Proceed to the next task immediately without waiting for auto-merge
           to complete. GitHub will handle it asynchronously.
        b. After picking up the next task, trust GitHub's auto-merge + the on-pr-merge hook to handle Linear state. Only spot-check at the end of each milestone.
  - For exception tasks: STOP and wait for my approval before continuing.

Use Claude Sonnet 4.6 by default. Switch to Claude Haiku 4.5 only when I prefix
a message with /model haiku.

--- TASK LIST ---

Milestone M1 — Core engine (Days 1-4, 6 issues)
  M1.1 Repo scaffolding: pyproject.toml, AGPL LICENSE, src/ layout, ruff/mypy config
  M1.2 GitHub Actions CI (lint, type, test on Python 3.11 and 3.12, Linux + macOS)
  M1.3 PyMuPDF text extraction with bounding boxes (src/redactron/extract/text_layer.py)
  M1.4 Presidio detector wrapper (src/redactron/detect/presidio_detector.py)
  M1.5 PyMuPDF redaction engine + apply_redactions() (src/redactron/redact/engine.py)
  M1.6 CLI shell with Typer; init and run (single-file mode) commands

Milestone M2 — Profile + variants (Days 5-7, 6 issues)
  M2.1 Profile schema with Pydantic v2; YAML loader (src/redactron/profile.py)
  M2.2 Name variant matching (rapidfuzz + tokenization) (detect/name_detector.py)
  M2.3 Address normalization (usaddress + libpostal) and variant search (detect/address_detector.py)
  M2.4 Account number partial redaction with last-4 preservation (redact/partial.py)
  M2.5 Custom regex patterns from profile (detect/account_detector.py)
  M2.6 Batch folder processing with progress bar (rich)

Milestone M3 — Verification + audit (Days 8-10, 6 issues)
  M3.1 Verifier module: re-extract and re-detect post-redaction (verify/verifier.py)
  M3.2 SQLite audit log + migrations (audit/log.py)
  M3.3 Subjects table + --subject flag for multi-subject mode
  M3.4 Markdown report generator (report/markdown.py)
  M3.5 Dry-run mode with diff preview
  M3.6 verify and log CLI commands

Milestone M4 — Polish + launch (Days 11-14, 4 issues)
  M4.1 OCR fallback via pytesseract; image-region painting (extract/ocr.py)
  M4.2 Synthetic test corpus: 10 PDFs (bank statement, utility bill, medical record,
       tax form, insurance EOB, court doc, payslip, lab report, invoice, leasing agreement)
  M4.3 Docs: README, PROFILE.md, PRIVACY.md, demo GIF
  M4.4 PyPI release flow (GitHub Actions + trusted publishing) and first published version

Milestone M5 — Web UI (Days 15-20, 6 issues, v1.5 — keep in Backlog until v1 ships)
  M5.1 Gradio app skeleton (src/redactron/web/app.py) with file upload + run button
  M5.2 Visual diff preview: before/after side-by-side per page using PyMuPDF rendering
  M5.3 Profile editor: load/edit/save profile.yaml from a web form
  M5.4 Audit log viewer: filterable table by subject and date range
  M5.5 redactron ui CLI command that boots Gradio and auto-opens the browser
  M5.6 Web UI screenshots in README + pip install redactron[ui] extra in pyproject.toml

--- REPO LAYOUT ---

redactron/
├── .github/
│   ├── workflows/{ci,release}.yml
│   └── ISSUE_TEMPLATE/
├── .kiro/
│   ├── settings/mcp.json
│   ├── steering/{product,tech,conventions}.md
│   ├── specs/redactron/{requirements,design,tasks}.md
│   └── hooks/{on-task-start,on-tests-pass,on-pr-merge}.yml
├── .redactron/
│   └── credits.db                        # local credit usage log
├── src/redactron/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── profile.py
│   ├── detect/{presidio_detector,address_detector,account_detector,name_detector}.py
│   ├── extract/{text_layer,ocr}.py
│   ├── redact/{engine,partial}.py
│   ├── verify/verifier.py
│   ├── audit/log.py
│   ├── report/markdown.py
│   └── web/app.py                        # M5 only
├── tests/
│   ├── fixtures/
│   ├── test_detect.py
│   ├── test_redact.py
│   └── test_verify.py
├── docs/{PROFILE,PRIVACY}.md
├── pyproject.toml
├── LICENSE                               # AGPL-3.0
├── README.md
└── CHANGELOG.md

--- DATA MODEL ---

# profile.yaml
version: 1
name: default
subject:
  display_name: "Tejinder Singh"
  aliases: ["Tejinder", "T. Singh", "Singh, Tejinder"]
  addresses:
    - "100 Phillip Street, San Jose, CA 95020, USA"
  phones: ["+1-408-555-1234"]
  emails: ["tejinder.singh@ieee.org"]
  ssns: ["xxx-xx-xxxx"]
  account_numbers:
    - value: "1234567890123456"
      preserve_last: 4
  custom_patterns:
    - name: patient_id
      regex: "PT-\\d{6}"
detection:
  use_presidio: true
  presidio_entities:
    [PERSON, LOCATION, PHONE_NUMBER, EMAIL_ADDRESS, US_SSN, CREDIT_CARD, DATE_TIME]
  fuzzy_match: true
  match_threshold: 0.85
  full_token_min_length: 2
  ocr_fallback: true

# Audit DB
CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  file_hash TEXT NOT NULL,
  original_filename TEXT,
  output_filename TEXT,
  processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  profile_name TEXT,
  subject_id TEXT,
  pages_processed INTEGER,
  items_detected INTEGER,
  items_redacted INTEGER,
  verification_passed BOOLEAN,
  verification_survivors_json TEXT,
  duration_ms INTEGER,
  notes TEXT
);

CREATE TABLE subjects (
  id TEXT PRIMARY KEY,
  display_name TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used_at TIMESTAMP,
  document_count INTEGER DEFAULT 0
);

# Credit usage log
CREATE TABLE usage (
  id INTEGER PRIMARY KEY,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  task_id TEXT,
  milestone TEXT,
  model TEXT,
  delta INTEGER,
  duration_seconds INTEGER,
  total_after INTEGER,
  pr_url TEXT,
  notes TEXT
);

--- CLI SURFACE ---

redactron init
redactron run <path> [--profile, --output, --threshold, --ocr, --no-verify, --json]
redactron verify <path>
redactron log [--subject, --json]
redactron profile show|edit|add|list
redactron subject add|list|show <id>
redactron dry-run <path>
redactron report <run_id>
redactron ui                                 # M5: launch Gradio web UI