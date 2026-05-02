# Redactron — Design

## Architecture

Redactron is a local-only CLI pipeline. Each stage is a pure module with no side effects
except the final write and audit log.

```
PDF input
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  extract/                                                   │
│  text_layer.py  ──► List[TextLayer]  (page, text, bbox)     │
│  ocr.py         ──► List[TextLayer]  (OCR fallback)         │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  detect/                                                    │
│  presidio_detector.py  ──► List[Detection]                  │
│  name_detector.py      ──► List[Detection]  (fuzzy)         │
│  address_detector.py   ──► List[Detection]  (normalized)    │
│  account_detector.py   ──► List[Detection]  (regex)         │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  redact/                                                    │
│  engine.py   ──► redacted fitz.Document                     │
│  partial.py  ──► partial redaction (last-N preserve)        │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  verify/                                                    │
│  verifier.py  ──► VerificationResult (passed, survivors)    │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  audit/                                                     │
│  log.py  ──► SQLite write (documents + subjects tables)     │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│  report/                                                    │
│  markdown.py  ──► .report.md + .report.json                 │
└─────────────────────────────────────────────────────────────┘
```

## Module Boundaries

| Module | Responsibility | Inputs | Outputs |
|--------|---------------|--------|---------|
| `extract/text_layer.py` | Read-only PDF parsing | `fitz.Document` | `List[TextLayer]` |
| `extract/ocr.py` | OCR fallback for image pages | `fitz.Page` | `List[TextLayer]` |
| `detect/presidio_detector.py` | Presidio NER detection | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `detect/name_detector.py` | Fuzzy name matching | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `detect/address_detector.py` | Address normalization + match | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `detect/account_detector.py` | Regex pattern matching | `List[TextLayer]`, `Profile` | `List[Detection]` |
| `redact/engine.py` | Apply redaction annotations | `fitz.Document`, `List[Detection]` | `fitz.Document` |
| `redact/partial.py` | Partial redaction (last-N) | `fitz.Document`, `Detection` | `fitz.Document` |
| `verify/verifier.py` | Post-redaction re-detection | `fitz.Document`, `Profile` | `VerificationResult` |
| `audit/log.py` | SQLite I/O only | `DocumentRecord` | None |
| `report/markdown.py` | Report generation | `DocumentRecord`, `VerificationResult` | `str` (markdown) |
| `cli.py` | Orchestration only | CLI args | Exit code |

## Key Data Structures

```python
@dataclass
class TextLayer:
    page_num: int
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    block_type: int  # fitz block type

@dataclass
class Detection:
    text: str
    entity_type: str
    start: int
    end: int
    score: float
    page_num: int
    bbox: tuple[float, float, float, float]
    preserve_last: int = 0  # for partial redaction

@dataclass
class VerificationResult:
    passed: bool
    survivors: list[Detection]
    duration_ms: int
```

## Repo Layout

```
redactron/
├── .github/workflows/{ci,release}.yml
├── .kiro/
│   ├── settings/mcp.json
│   ├── steering/{product,tech,conventions}.md
│   ├── specs/redactron/{requirements,design,tasks}.md
│   └── hooks/{on-task-start,on-tests-pass,on-pr-merge}.yml
├── .redactron/credits.db
├── src/redactron/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── errors.py
│   ├── profile.py
│   ├── detect/{presidio_detector,address_detector,account_detector,name_detector}.py
│   ├── extract/{text_layer,ocr}.py
│   ├── redact/{engine,partial}.py
│   ├── verify/verifier.py
│   ├── audit/log.py
│   ├── report/markdown.py
│   └── web/app.py  (M5 only)
├── tests/
│   ├── fixtures/  (10 synthetic PDFs)
│   ├── test_detect.py
│   ├── test_redact.py
│   ├── test_verify.py
│   └── test_e2e.py
├── docs/{PROFILE,PRIVACY}.md
├── pyproject.toml
├── LICENSE  (AGPL-3.0)
├── README.md
└── CHANGELOG.md
```

## Performance Targets

| Scenario | Target |
|----------|--------|
| 10-page text PDF | < 3s end-to-end including verification |
| 10-page image PDF (OCR) | < 30s |
| Peak memory per document | < 500 MB |

## Error Handling

All typed exceptions live in `redactron.errors`:
- `ProfileValidationError` — bad profile.yaml
- `ExtractionError` — PDF unreadable/encrypted
- `RedactionError` — redaction failed
- `VerificationError` — survivors found post-redaction

CLI catches all and prints user-friendly messages; `--debug` shows full stack trace.
