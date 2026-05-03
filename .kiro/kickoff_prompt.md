We are building `redactron`, a local-only CLI for batch PII redaction in PDFs
with verification, audit logging, and encrypted multi-client profile vault.

Read these files first, in order:
  1. .kiro/steering/product.md
  2. .kiro/steering/tech.md
  3. .kiro/steering/conventions.md
  4. .kiro/settings/mcp.json

Then connect to the Linear MCP server (linear) and the GitHub MCP server (github).
Verify both are reachable. If Linear OAuth needs browser auth, prompt me.

Your first job is to bootstrap the project end-to-end.

============================================================
0. RESOLVE LINEAR TEAM (do this first, before any Linear creation)
============================================================
- Call linear.list_teams() and show me the result.
- If exactly ONE team: name it explicitly, ask "Use team <Name> (identifier <ID>)?"
  and wait for "yes".
- If MULTIPLE teams: list each with name, identifier, member count; ask which to use.
- If ZERO teams: stop and ask me to create a team via Linear UI, then re-run.
- Once resolved, store the team identifier (e.g. BLD). All Linear ops scope to it.
  Issues will auto-generate as <ID>-1 ... <ID>-34 from this team's prefix.

============================================================
1. CREATE LINEAR PROJECT
============================================================
Create a Linear project named "Redactron" under the resolved team if it doesn't
already exist. If it does, use it as-is and skip to step 2.

============================================================
2. CREATE 6 MILESTONES (skip any that already exist)
============================================================
- M1   Core engine                              (target +4 days)
- M2   Profile + variants                       (target +7 days)
- M3   Verification + audit                     (target +10 days)
- M3.5 Encrypted multi-client profile vault     (target +13 days, security)
- M4   Polish + launch                          (target +17 days)
- M5   Web UI (v1.5)                            (target +24 days, status: Backlog)

============================================================
3. CREATE 34 LINEAR ISSUES
============================================================
From the task list at the bottom of this prompt. Assign each to its milestone
and add the matching phase label (phase-1..phase-5, plus phase-3.5).
- M1–M3 issues (18) and M4 issues (4) go into Cycle 1 in sequential order.
- M3.5 issues (6) stay in Backlog state until M3 fully merges; bring them into
  the cycle when M3 ships.
- M5 issues (6) stay in Backlog state until v1 ships.
Skip any issue whose title already exists (idempotent).

============================================================
4. VERIFY (do not recreate) THE GITHUB REPO tjndr/redactron
============================================================
- Call github.get_repo("tjndr/redactron").
- If it does NOT exist: STOP and ask me before creating. Do not auto-create.
- If it exists:
    a. Inspect contents. If any files exist, tell me what's there and ask
       whether to (i) preserve and add ours alongside, or (ii) overwrite.
    b. If empty: push initial commit with AGPL-3.0 LICENSE, Python .gitignore,
       README stub, and the .kiro/ + spec files.
    c. Configure main branch protection: require PR before merge, require
       status checks to pass, dismiss stale reviews on push, allow auto-merge,
       auto-delete head branches.
    d. Confirm the repo stays PRIVATE.

============================================================
5. GENERATE SPEC FILES in .kiro/specs/redactron/
============================================================
- requirements.md  (user stories from product.md, acceptance per milestone)
- design.md        (architecture, data flow, module boundaries)
- tasks.md         (34 issues with implementation notes, mapping each to its Linear ID)

============================================================
5a. SET LINEAR PROJECT DESCRIPTION
============================================================
"Redactron: a local-only CLI that batch-redacts PII from PDFs using a user
profile, with verification, audit logging, and encrypted multi-client vault.
Python + PyMuPDF + Presidio. AGPL-3.0. v1 ships in 17 days; v1.5 adds Gradio
web UI."

============================================================
5b. CREATE FOUR LINEAR PROJECT DOCUMENTS
============================================================
1. "Architecture" — repo layout, module boundaries, mermaid data-flow:
     PDF → extract → detect → redact → verify → audit log + report
     Profile load → keychain auth → decrypt vault → extract client_id row
2. "Data model" — profile.yaml schema, audit DB schema, credits DB schema,
   vault.enc schema, CLI surface
3. "Conventions and risks" — full conventions.md content + risks table:
     | Risk | Mitigation |
     | PyMuPDF AGPL scares some users | Document in PRIVACY.md; pikepdf alt path in v2 |
     | Presidio NER misses non-English names | Profile aliases override; document |
     | Over-redaction false positives | use_presidio: false default; threshold; dry-run |
     | Numeric over-matching | Numeric tokens never fuzzy-matched; warn+skip |
     | Mid-string partial bbox math wrong | get_text("rawdict"); per-line bbox lists |
     | OCR accuracy on poor scans | Min DPI 300; flag low-confidence |
     | Format drift in PyMuPDF/Presidio | Pin exact versions; renovate weekly |
     | Profile leak / multi-client PII | Encrypted vault (M3.5) + Tier-1 hygiene |
     | Cherry-pick conflicts | Strict PR serialization (per-task workflow) |
     | Kiro hits credit budget | Haiku for boilerplate; Sonnet for logic-heavy |
4. "Credit Budget" template:

   # Redactron — Credit Budget

   ## Allocation
   | Milestone               | Planned | Actual | Status      |
   | M1 Core engine          | 280     | TBD    | not started |
   | M2 Profile + variants   | 310     | TBD    | not started |
   | M3 Verification + audit | 250     | TBD    | not started |
   | M3.5 Encrypted vault    | 350     | TBD    | not started |
   | M4 Polish + launch      | 120     | TBD    | not started |
   | M5 Web UI (v1.5)        | 300     | TBD    | not started |
   | Buffer                  | 40      | n/a    | n/a         |
   | **Total v1**            | **1350**| TBD    |             |
   | **Total v1+v1.5**       | **1650**| TBD    |             |

   ## Running total
   Used: 0
   Remaining v1: 1350 / Remaining v1+v1.5: 1650
   Last updated: <bootstrap timestamp>

   ## Burn-rate alerts
   - WARNING at 80% of v1 (1080 credits)
   - CRITICAL at 95% of v1 (1283 credits)

   ## Per-issue actuals (sorted by cost desc)
   (Empty until first task completes.)

============================================================
5c. SET EACH MILESTONE DESCRIPTION TO ITS ACCEPTANCE CRITERIA
============================================================
M1 done when: redactron run <single-file.pdf> redacts a known PII string and
   produces output; output passes verification; CI green on Linux + macOS.

M2 done when: profile YAML loads/validates/drives detection; "100 Phillip
   Street" matches "100 Philip St" via fuzzy; 1234-5678-9012-3456 redacts to
   XXXX-XXXX-XXXX-3456; folder of 10 mixed PDFs processes in one command;
   numeric tokens never fuzzy-matched; multi-line addresses bridge per-line
   bboxes; column-aware extraction; figure text skipped by default.

M3 done when: every run produces verification report (markdown + JSON) by
   default; audit log queryable by `redactron log --subject <id>`; dry-run
   shows what would be redacted; safety-net second pass catches survivors;
   reports include subject info, detections, verification status, timing.

M3.5 done when: redactron vault init creates encrypted vault + master key in
   keychain; profile add/list/show/edit/delete/rename work; profile show
   masks by default, --reveal requires Touch ID + TTY; profile import
   migrates legacy yaml + secure-wipes source; redactron run --client <id>
   loads correct profile via Touch ID; macOS Touch ID prompts on every vault
   access; vault file is opaque ciphertext; legacy profile.yaml works with
   deprecation warning; zero plaintext PII in logs/swap/temp; all detection
   tests pass against vault-loaded profiles; Touch ID overhead < 2s.

M4 done when: image-only PDF gets OCR'd and redacted with NoTextLayerError
   replaced by automatic OCR; 10 synthetic test PDFs all pass; README +
   PROFILE.md + PRIVACY.md + SECURITY.md + demo GIF; pip install redactron
   works from PyPI; launch post drafted (don't submit yet).

M5 done when: redactron ui opens browser with working web UI; drag-drop
   folder, redact in real time, download zip; visual diff overlay per page;
   profile editable via UI; audit log in UI.

============================================================
5d. ISSUE DESCRIPTION TEMPLATE
============================================================
For each issue:

   ## Goal
   <one sentence>

   ## Implementation notes
   <bullets from the task list>

   ## Files touched
   <paths from the repo layout>

   ## Acceptance criteria
   - [ ] Unit tests pass (95%+ coverage on touched modules)
   - [ ] mypy strict passes for affected modules
   - [ ] ruff clean
   - [ ] Integration test exercises CLI-to-output pipeline (per milestone)
   - [ ] <task-specific criteria>

   ## Model preference
   sonnet | haiku  (Sonnet for tricky logic; Haiku for boilerplate/docs/tests)

   ## Linked spec
   .kiro/specs/redactron/tasks.md#<anchor>

============================================================
5e. ADD LABELS TO EACH ISSUE
============================================================
- phase-1 / phase-2 / phase-3 / phase-3.5 / phase-4 / phase-5 (one, matching milestone)
- type: feat | infra | docs | test | fix (one per issue)
- model: sonnet | haiku (one per issue)
- security: critical (only on M3.5 issues that touch crypto, keychain, or vault)

============================================================
5f. IDEMPOTENCY (so re-running this kickoff is safe)
============================================================
Before creating any Linear entity (project, milestone, issue, document, label,
view), check if one with the same name/identifier exists. If yes, update in
place. If no, create. Never duplicate. Report counts:
  "existing reused: N, newly created: M"

============================================================
5g. CREATE FOUR CUSTOM VIEWS IN THE REDACTRON PROJECT
============================================================
1. "By milestone" — grouped by milestone, sorted by status
2. "Current cycle" — what's being worked on this week
3. "Blocked / needs review" — anything Blocked or PR-pending
4. "By model" — grouped by sonnet/haiku label (for credit budget tracking)

============================================================
5h. CREDIT USAGE TRACKING (mandatory after every completed task)
============================================================
On bootstrap, create scripts/log-credits.sh and .redactron/credits.db:

  scripts/log-credits.sh <issue-id> <delta> <duration_seconds> <model> <pr-url>

The script:
  - Reads latest total_after from .redactron/credits.db (default 0)
  - Computes new_total = previous + delta
  - INSERTs row into .redactron/credits.db (schema in DATA MODEL below)
  - Posts Linear comment on the issue:
      "Task complete. Credits: <delta> | Time: <duration> | Cumulative:
       <total>/1350 (<percent>%) | Remaining v1: <1350 - total>"
  - Updates the "Credit Budget" Linear project document
  - Appends "Credits: <delta> | Time: <duration>" to the GitHub PR description
  - If new_total >= 1080: posts a credit alert comment
  - If new_total >= 1283: refuses to log; requires explicit approval

DO NOT use /usage or `kiro-cli usage` commands — they don't expose data
programmatically. Source: parse Kiro's auto-emitted task summary line at the
end of every completed task, then invoke scripts/log-credits.sh.

After every PR is opened (and tests pass + commit+push complete), run
scripts/log-credits.sh with the parsed values. This is non-negotiable. If
you skip the script, the task is not complete.

============================================================
5i. SPEC FILE MAINTENANCE (standing rule)
============================================================
Whenever ANY of these happens, IMMEDIATELY update .kiro/specs/redactron/
in the same PR or as a follow-up `chore:` PR with auto-merge enabled:
  - User pastes/references a master plan change (new milestone, scope change)
  - A new Linear issue is created → add tasks.md entry
  - An existing Linear issue is renamed or scope-changed → update tasks.md
  - A milestone is added/removed/reordered → update tasks.md and requirements.md
  - Architecture or data model changes → update design.md
  - New module/file paths introduced → update repo layout reference

Spec drift from Linear/master plan is a bug. Spec files always reflect the
latest plan.

============================================================
6. uv init + pyproject.toml
============================================================
With the locked stack from tech.md (Python 3.11, PyMuPDF, presidio-analyzer,
presidio-anonymizer, rapidfuzz, usaddress, pytesseract, typer, pydantic v2,
keyring, cryptography; pytest/ruff/mypy as dev deps; gradio behind [ui]
optional extra for v1.5; cryptography + keyring for vault).

============================================================
7. PUSH INITIAL COMMIT TO GITHUB ON main
============================================================

============================================================
8. STOP AND SHOW STATUS REPORT
============================================================
- Linear: project URL, all 6 milestone URLs, total issue count (34), URLs for
  the 4 project documents
- GitHub: repo URL, initial commit SHA, branch protection state
- Local: tree of created files including .redactron/credits.db and
  scripts/log-credits.sh
- Next task suggested with its Linear ID and branch name

DO NOT start implementation tasks (M1.3 onward) until I explicitly confirm.

============================================================
FOR EVERY SUBSEQUENT TASK
============================================================

STRICT PR SERIALIZATION (mandatory):
Before opening any new PR, run:
    gh pr list --state open --json number,mergeStateStatus
If ANY PR is in BLOCKED, BEHIND, DIRTY, UNSTABLE, or PENDING state, do NOT
open a new PR. Poll every 30 seconds until all open PRs are MERGED or in
CLEAN state with auto-merge enabled and CI complete. Only then proceed.
Cherry-picking onto pending branches is forbidden — it produces conflicts
that cost more to resolve than the time saved by parallel work.

Per-task workflow:

  1. git fetch origin && git checkout main && git pull
  2. Move Linear issue to "In Progress"
  3. git checkout -b m<phase>/<linear-id>-short-desc
       e.g. m2/bld-7-profile-schema, m3.5/bld-29-vault-format
  4. Implement, write tests, run:
        uv run pytest && uv run ruff check && uv run mypy src/
  5. If task changes architecture, data model, or repo layout: update
     .kiro/specs/redactron/design.md (and tasks.md if scope changed) in the
     same commit (Spec maintenance standing rule, 5i).
  6. Conventional commit, push, open PR with "Closes BLD-N"
  7. Run scripts/log-credits.sh <issue-id> <delta> <duration_seconds> sonnet|haiku <pr-url>
  8. ENABLE auto-merge: gh pr merge --auto --squash --delete-branch
     EXCEPTIONS — do NOT auto-merge these issues; open PR, post a Linear
     comment summarizing approach + edge cases + test fixtures + known
     limitations, then STOP and wait for my "merge it":
         - BLD-19  (M4.1 OCR fallback / image-region painting)
         - BLD-29  (M3.5.1 Encrypted vault file format + key management)
         - BLD-30  (M3.5.2 macOS Keychain Services with Touch ID)
     Note: BLD-13 (M3.1 verifier) was an exception during M3 and has shipped;
     it's no longer a manual gate. Add new issues to the exception list ONLY
     if I explicitly request it.
  9. Poll PR until merged: gh pr view <num> --json state,mergedAt
       Wait for state == "MERGED" before continuing.
 10. Verify Linear issue moved to "Done"; if not, move manually and post
     "Auto-merged in PR #<num>" comment.
 11. Repeat for next task.

============================================================
DETECTION INVARIANTS (non-negotiable; tests enforce)
============================================================

1. Numeric tokens are NEVER fuzzy-matched in isolation.
   Postal codes, SSNs, phone numbers, account numbers, decimals — exact match
   or anchored regex only (e.g. \b91325\b, \d{3}-\d{2}-\d{4}). If a numeric
   token reaches a fuzzy-match path, log.warning(...) and route to exact-match
   only. NEVER assert+crash; users hit real-world tokens like "103 9.22".

2. Multi-line redaction bboxes are LISTS, never unioned.
   A multi-line span produces N rectangles (one per line). Sanity guard:
   any single rect with area > 30% of page area or height > 4x median line
   height is REJECTED with logged warning ("Redaction rect too large for
   span <text>; rejecting to prevent over-redaction.").

3. Detection is exhaustive per page.
   Use re.finditer (not re.search). Find ALL occurrences of every profile
   pattern. No first-match-wins. Per-string deduplication is forbidden;
   each occurrence is a separate redaction target with its own bbox.

4. Safety-net second pass.
   After redaction, re-extract and re-detect. If survivors found, redact and
   loop (max 3 passes). RedactionError if non-convergent. Successful
   supplementation is logged at INFO level with calm language:
     "Pass 2 supplemented pass 1 with N additional spans; output is complete."
   NEVER log.warning() on the successful-completion path.

5. Defensive warn+skip, not assert+crash.
   Internal invariants (e.g. "numeric must use exact match") are enforced via
   log.warning + graceful fallback, never assertions. Asserts crash users on
   real-world edge cases. Apply this pattern across detect/, redact/, pipeline.

============================================================
LAYOUT HANDLING
============================================================

1. Column-aware extraction (default: column_aware=true).
   Use get_text("dict") for blocks with bboxes. Cluster blocks by x-center
   to detect columns. Process each column independently. Address bridging
   logic operates ONLY within a single column (next "line" must be in the
   same column AND within 2x median line height vertically).

2. Figure text skipped by default (default: scan_figures=false).
   Detect figure regions via page.get_drawings(). Text inside figure regions
   is skipped. Opt-in via profile.detection.scan_figures=true for users who
   want maximum coverage. Log at INFO when skipping:
     "Skipped text inside figure region at <bbox>: typically not body PII."

3. Image-only PDFs raise NoTextLayerError.
   Pre-flight check: if page chars < 50 AND page has images, raise with:
     "❌ This PDF appears to be a scan or image-only document with no text
      layer. OCR support is coming in v1 milestone M4. Until then:
        1. Re-export from source application with 'searchable text', OR
        2. Run an OCR tool first (e.g. ocrmypdf input.pdf output.pdf)
           and pass the OCR'd file to redactron.
      If you believe this PDF DOES have a text layer, run with --debug."
   Mixed PDFs (some text + some image pages): succeed; log image-only pages
   as "Page N: 0 spans (image-only, OCR not yet enabled)".

============================================================
PROFILE SECURITY DEFAULTS
============================================================

1. detection.use_presidio: false (default).
   Profile is authoritative. Presidio is opt-in with explicit entity list.
   Default `redactron init` writes:
       detection:
         use_presidio: false
         presidio_entities: []

2. Profile / vault file mode: chmod 0600 (enforced on init and load).
   Refuse to load if perms are looser. Mirror SSH id_rsa discipline. Friendly
   error: "Profile permissions too permissive (mode <NNN>). Run: chmod 600 <path>".

3. Auto-gitignore on init.
   Detect git repo (cwd or ~/.redactron parent). Append .redactron/ to
   .gitignore if not present. Print warning banner.

4. Masked profile show by default.
   redactron profile show outputs masked values:
     ssns:           ["***-**-6789"]
     account_numbers: ["************3456"]
     emails:          ["t**@****.org"]
     phones:          ["+1-***-***-1234"]
     addresses:       ["[street redacted], <city>, <state>"]
     display_name:    "T*** S***"
   --reveal flag requires sys.stdin.isatty() AND interactive prompt.

5. No PII in logs.
   SafeFormatter scrubs known PII patterns from log emissions. Code-level rule:
   never log raw SSN, full account, full address, full email/phone. Show
   masked form or last-4 only.

6. Cloud-sync warning on init.
   Detect iCloud Drive / Dropbox / OneDrive / Google Drive paths. Warn user
   prominently with instructions to relocate ~/.redactron.

============================================================
REPORTS WRITTEN BY DEFAULT
============================================================

Every successful redactron run writes three files:
  <stem>_redacted.pdf
  <stem>_report.md
  <stem>_report.json

Opt-out: --no-report flag (suppresses .md and .json).

Every report includes: subject info, items detected (per detector type),
items redacted, verification status (passed/failed + survivors list),
processing duration, profile used, run timestamp, run_id (for re-rendering
via `redactron report <run_id>`).

============================================================
DEFAULTS
============================================================

- Sonnet 4.6 by default; Haiku 4.5 only when /model haiku prefixed
- Conventional commits (feat, fix, docs, test, chore, refactor)
- One Linear issue per PR
- Never skip tests, ruff, or mypy
- Never skip scripts/log-credits.sh
- If MCP servers fail mid-task: reconnect once, then ask me
- If a CI failure looks systemic (>2 attempts to fix): stop and ping me
- If credits >= 1080: post alert + ask before continuing
- If credits >= 1283: stop auto-execution; require approval per task

============================================================
TASK LIST
============================================================

Milestone M1 — Core engine (Days 1-4, 6 issues, ~280 credits)
  M1.1 Repo scaffolding: pyproject.toml, AGPL LICENSE, src/ layout, ruff/mypy config            (haiku)
  M1.2 GitHub Actions CI (lint, type, test on Python 3.11 + 3.12, Linux + macOS)                (haiku)
  M1.3 PyMuPDF text extraction with bounding boxes (extract/text_layer.py, column-aware)        (sonnet)
  M1.4 Presidio detector wrapper (detect/presidio_detector.py)                                  (sonnet)
  M1.5 PyMuPDF redaction engine + apply_redactions() with bbox sanity guards (redact/engine.py) (sonnet)
  M1.6 CLI shell with Typer; init and run (single-file mode) commands                           (sonnet)

Milestone M2 — Profile + variants (Days 5-7, 6 issues, ~310 credits)
  M2.1 Profile schema (Pydantic v2) + YAML loader; chmod 0600 + perm enforcement                (sonnet)
  M2.2 Name variant matching (rapidfuzz + tokenization); corporate-suffix suppression           (sonnet)
  M2.3 Address normalization (libpostal expand + usaddress); multi-line bridging within column  (sonnet)
  M2.4 Account number partial redaction with last-4 preservation                  MANUAL REVIEW (sonnet)
  M2.5 Custom regex patterns from profile (anchored boundaries; no fuzzy on numeric)            (sonnet)
  M2.6 Batch folder processing with progress bar (rich); reports written by default             (haiku)

Milestone M3 — Verification + audit (Days 8-10, 6 issues, ~250 credits)
  M3.1 Verifier: re-extract and re-detect post-redaction; preserve_last suffix handling         (sonnet)
  M3.2 SQLite audit log + migrations (audit/log.py)                                             (sonnet)
  M3.3 Subjects table + --subject flag for multi-subject mode                                   (sonnet)
  M3.4 Markdown + JSON report generator; written by default; --no-report opt-out                (haiku)
  M3.5-DRY Dry-run mode with diff preview                                                       (sonnet)
  M3.6 verify and log CLI commands                                                              (haiku)

Milestone M3.5 — Encrypted multi-client profile vault (Days 11-13, 6 issues, ~350 credits, security)
[INSERT YOUR M3.5 CHUNKS HERE — replace this skeleton with your refined task descriptions]
  M3.5.1 (BLD-29) Encrypted vault file format + key management abstraction          MANUAL REVIEW (sonnet)
       AES-256-GCM, per-vault salt, KDF (Argon2id or HKDF from keychain master),
       pluggable backend interface for keychain providers
  M3.5.2 (BLD-30) macOS Keychain Services integration with Touch ID                  MANUAL REVIEW (sonnet)
       keyring lib with kSecAccessControlBiometryAny; Linux/Windows backends
       stubbed with NotImplementedError for v1.1
  M3.5.3 (BLD-31) Multi-client profile CRUD commands                                              (sonnet/haiku)
       profile add/list/show/edit/delete/rename; masked by default; --reveal
       requires Touch ID + TTY confirmation
  M3.5.4 (BLD-32) Migration from single profile.yaml                                              (sonnet)
       profile import <yaml> --client <id>; secure-wipe via overwrite-then-unlink;
       dry-run preview; idempotent re-runs
  M3.5.5 (BLD-33) CLI --client <id> flag on all profile-using commands                            (haiku)
       Update run/dry-run/verify/log/profile show|edit; legacy profile.yaml
       fallback with deprecation warning; default client = "default"
  M3.5.6 (BLD-34) SECURITY.md + PROFILE.md vault section + integration tests                      (haiku)
       End-to-end: init vault → add 2 profiles → run with each → verify zero
       plaintext on disk; perf test for Touch ID overhead < 2s

Milestone M4 — Polish + launch (Days 14-17, 4 issues, ~120 credits)
  M4.1 (BLD-19) OCR fallback via pytesseract; image-region painting                  MANUAL REVIEW (sonnet)
  M4.2 Synthetic test corpus: 10 PDFs (bank statement, utility bill, medical record,
       tax form, insurance EOB, court doc, payslip, lab report, invoice, leasing
       agreement, two-column research paper, multi-line address fixture)                          (haiku)
  M4.3 Docs: README, PROFILE.md, PRIVACY.md, SECURITY.md, demo GIF                                (haiku)
  M4.4 PyPI release flow (GitHub Actions + trusted publishing) and first published version       (haiku)

Milestone M5 — Web UI (Days 18-23, 6 issues, ~300 credits, v1.5 — Backlog until v1 ships)
  M5.1 Gradio app skeleton (src/redactron/web/app.py) with file upload + run button              (sonnet)
  M5.2 Visual diff preview: before/after side-by-side per page using PyMuPDF rendering            (sonnet)
  M5.3 Profile editor: load/edit/save profile.yaml from a web form (vault-aware via --client)    (haiku)
  M5.4 Audit log viewer: filterable table by subject and date range                               (haiku)
  M5.5 redactron ui CLI command that boots Gradio and auto-opens the browser                     (haiku)
  M5.6 Web UI screenshots in README + pip install redactron[ui] extra                            (haiku)

============================================================
REPO LAYOUT
============================================================

redactron/
├── .github/
│   ├── workflows/{ci,release}.yml
│   └── ISSUE_TEMPLATE/
├── .kiro/
│   ├── settings/mcp.json
│   ├── steering/{product,tech,conventions}.md
│   ├── specs/redactron/{requirements,design,tasks}.md
│   ├── hooks/{on-task-start,on-tests-pass,on-pr-merge}.yml
│   └── kickoff_prompt.md                  # this file
├── .redactron/
│   └── credits.db                          # local credit usage log (gitignored)
├── scripts/
│   └── log-credits.sh                      # credit tracking script
├── src/redactron/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── pipeline.py                         # orchestrator (run_pipeline)
│   ├── profile.py
│   ├── errors.py
│   ├── detect/{presidio_detector,address_detector,account_detector,name_detector}.py
│   ├── extract/{text_layer,ocr,layout}.py  # layout = column detection + figure regions
│   ├── redact/{engine,partial}.py
│   ├── verify/verifier.py
│   ├── audit/log.py
│   ├── report/{markdown,json}.py
│   ├── vault/                              # M3.5
│   │   ├── __init__.py
│   │   ├── store.py                        # AES-256-GCM file format
│   │   ├── keychain.py                     # OS keychain abstraction
│   │   └── migrate.py                      # yaml → vault migration
│   └── web/app.py                          # M5
├── tests/
│   ├── fixtures/
│   ├── test_run_pipeline.py
│   ├── test_detect.py
│   ├── test_redact.py
│   ├── test_verify.py
│   ├── test_layout.py
│   ├── test_report.py
│   ├── test_audit.py
│   ├── test_vault.py                       # M3.5
│   ├── test_keychain.py                    # M3.5
│   └── test_migration.py                   # M3.5
├── docs/
│   ├── PROFILE.md
│   ├── PRIVACY.md
│   ├── SECURITY.md                         # M3.5/M4
│   └── examples/
├── pyproject.toml
├── uv.lock                                 # commit this for CI reproducibility
├── LICENSE                                 # AGPL-3.0
├── README.md
└── CHANGELOG.md

============================================================
DATA MODEL
============================================================

# profile.yaml (or one row in vault.enc keyed by client_id)
version: 1
name: default
subject:
  display_name: "Tejinder Singh"
  aliases: ["Tejinder", "T. Singh", "Singh, Tejinder"]
  addresses: ["100 Phillip Street, San Jose, CA 95020, USA"]
  phones: ["+1-408-000-0000"]
  emails: ["tejinder.singh@ieee.org"]
  ssns: []
  account_numbers:
    - { value: "1234567890123456", preserve_last: 4 }
  custom_patterns: []
detection:
  use_presidio: false
  presidio_entities: []
  fuzzy_match: true
  match_threshold: 0.85
  full_token_min_length: 2
  ocr_fallback: true
  column_aware: true
  scan_figures: false
  address_line_bridge_window: 3

# Audit DB (.redactron/audit.db)
CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  file_hash TEXT NOT NULL,
  original_filename TEXT, output_filename TEXT,
  processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  profile_name TEXT, subject_id TEXT, client_id TEXT,
  pages_processed INTEGER, items_detected INTEGER, items_redacted INTEGER,
  verification_passed BOOLEAN, verification_survivors_json TEXT,
  duration_ms INTEGER, notes TEXT
);
CREATE TABLE subjects (
  id TEXT PRIMARY KEY, display_name TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used_at TIMESTAMP, document_count INTEGER DEFAULT 0
);

# Credits log (.redactron/credits.db)
CREATE TABLE usage (
  id INTEGER PRIMARY KEY,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  task_id TEXT, milestone TEXT, model TEXT,
  delta INTEGER, duration_seconds INTEGER, total_after INTEGER,
  pr_url TEXT, notes TEXT
);

# Vault (~/.redactron/vault.enc — AES-256-GCM; master key in OS keychain)
# Decrypted in-memory only. Schema of decrypted contents:
{
  "version": 1,
  "salt": "<base64 per-vault salt>",       # also written to vault.salt
  "profiles": {
    "<client_id>": {
      "display_name": "<string>",
      "created_at": "<ISO8601>",
      "updated_at": "<ISO8601>",
      "profile_json": { ... full profile.yaml structure ... },
      "notes": "<optional>"
    },
    ...
  }
}

============================================================
CLI SURFACE
============================================================

redactron init                                       # creates profile + .redactron/
redactron run <path> [--profile|--client, --output, --threshold, --ocr,
                      --no-verify, --no-report, --subject/-s, --debug, --json]
redactron verify <path> [--client]                   # re-verify already-redacted PDF
redactron log [--subject, --client, --limit, --json] # query audit log
redactron report <run_id>                            # re-render markdown report
redactron dry-run <path> [--client, --json]         # preview without writing files
redactron profile show [<id>] [--reveal] [--client]
redactron profile edit [<id>] [--client]
redactron profile add --client <id> [--name <name>] [--from <yaml>]
redactron profile list
redactron profile delete <id>
redactron profile rename <old> <new>
redactron profile import <yaml> --client <id>        # M3.5: migrate legacy yaml
redactron subject add|list|show <id>
redactron vault init                                 # M3.5: create encrypted vault
redactron ui                                         # M5: launch Gradio web UI

GO.