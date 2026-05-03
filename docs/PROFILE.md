# redactron Profile Reference

A profile YAML file tells redactron **what to redact** and **how to detect it**.
By default, redactron runs in **profile-only mode** — it redacts exactly what you declare, nothing more.

---

## Quick start

```bash
redactron init          # creates ~/.redactron/profile.yaml
# edit the file, then:
redactron run document.pdf
```

---

## Detection modes

### Profile-only mode (default)

```yaml
detection:
  use_presidio: false
  presidio_entities: []
```

Redacts only the names, addresses, account numbers, and patterns you declare.
**Deterministic and privacy-preserving** — no ML model, no false positives from unrelated text.

### Profile + Presidio mode (opt-in)

```yaml
detection:
  use_presidio: true
  presidio_entities:
    - PERSON
    - PHONE_NUMBER
    - EMAIL_ADDRESS
    - US_SSN
    - CREDIT_CARD
```

Adds Microsoft Presidio NER on top of profile detection. Profile hits are **authoritative** — they always win over Presidio on overlapping spans. Only the entity types you list are detected; there are no implicit defaults.

**Why profile-only is the v1 default:** Presidio can produce false positives (acquisition dates, market values, unrelated names). Profile-only mode gives you a deterministic privacy guarantee: only your declared PII is redacted.

---

## Full schema

```yaml
version: 1                          # required; only version 1 supported
name: my-profile                    # optional label

subject:
  display_name: "Tejinder Singh"    # required; used as primary name to redact
  aliases:                          # optional; additional name forms
    - "Tejinder"
    - "T. Singh"
    - "Singh, Tejinder"
  addresses:                        # optional; full addresses to redact
    - "100 Phillip Street, San Jose, CA 95020, USA"
  phones:                           # optional; phone numbers (future detector)
    - "+1-408-555-1234"
  emails:                           # optional
    - "tejinder@example.com"
  ssns:                             # optional; SSN patterns
    - "xxx-xx-xxxx"
  account_numbers:                  # optional; financial account numbers
    - value: "1234567890123456"
      preserve_last: 4              # keep last N digits visible (default 4)
  custom_patterns:                  # optional; arbitrary regex patterns
    - name: patient_id
      regex: "PT-\\d{6}"
    - name: employee_id
      regex: "EMP-\\d{5}"

detection:
  use_presidio: false               # default: profile-only
  presidio_entities: []             # entities to detect when use_presidio: true
  fuzzy_match: true                 # use fuzzy matching for names/addresses
  match_threshold: 0.85             # 0.0–1.0; lower = more matches, more false positives
  full_token_min_length: 2          # ignore alias tokens shorter than this
  ocr_fallback: false               # enable OCR for image-only PDFs (slow)
```

---

## Name matching

- **Case-insensitive**: "TEJINDER SINGH" matches "Tejinder Singh"
- **Middle initials**: "Tejinder K. Singh" matches alias "Tejinder Singh"
- **Aliases**: each alias in the list is tried independently
- **Corporate suppression**: spans ending in Inc., Corp., LLC, Ltd., Industries, etc. are not matched as person names
- **Threshold**: `match_threshold: 0.85` works well for most names. Raise to 0.92+ to reduce false positives with common first names used as standalone aliases.

**Note on single-token aliases:** A bare first-name alias like `"Tejinder"` will match any span containing that first name (e.g., "Tejinder Sharma"). If you want to avoid this, use only full-name or last-name-first aliases.

---

## Address matching

- **Abbreviation expansion**: "St" → "street", "Ave" → "avenue", etc.
- **Case-insensitive**: "100 PHILLIP STREET" matches "100 Phillip Street"
- **ZIP+4**: "95020-1234" in the PDF matches a profile ZIP of "95020"
- **No-comma variants**: "100 Phillip St San Jose CA 95020" matches
- **Multi-line**: each PDF text span is matched independently; a multi-line address produces one detection per line

**Known limitation — house number disambiguation:** At the default threshold (0.85), "200 Phillip Street" will match a profile address of "100 Phillip Street" because they differ by only one character (~97% similar). To distinguish house numbers, raise `match_threshold` to 0.99 — but this may miss abbreviated or slightly misspelled forms. This is a v1 limitation; v2 will use structured address comparison.

**Known limitation — cross-page splits:** An address split across a page boundary (last line on page 1, rest on page 2) will not be detected as a single match. Each page's text is processed independently. Workaround: add both the full address and the street-only form as separate profile addresses.

---

## Account numbers

```yaml
account_numbers:
  - value: "1234567890123456"
    preserve_last: 4    # redacts to XXXX-XXXX-XXXX-3456
  - value: "9876543210"
    preserve_last: 0    # redacts entire number
```

- Matches with or without separators (hyphens, spaces, dots)
- `preserve_last: 0` redacts the entire number
- The redaction bbox covers only the prefix; the last N digits remain visible in the PDF

---

## Custom regex patterns

```yaml
custom_patterns:
  - name: patient_id
    regex: "PT-\\d{6}"
  - name: case_number
    regex: "CASE-\\d{4}-[A-Z]{2}"
```

- Invalid regex raises a `ProfileValidationError` at load time with a clear message
- The `name` field becomes the `entity_type` in the detection log
- Patterns are applied to every text span on every page

---

## Friendly error messages

If your profile has a validation error, redactron prints:

```
❌ Profile error: Profile validation failed: ...
See docs/PROFILE.md for the full schema. Use --debug for details.
```

Run with `--debug` to see the full Pydantic traceback.

---

## Matching semantics

Understanding how each field type is matched prevents surprises:

| Field type | Matching strategy | Why |
|---|---|---|
| Names | Whole-string fuzzy (`token_set_ratio`) against full span | Aliases are complete strings, not tokens |
| Addresses | Span must parse as address first, then `partial_ratio` | Prevents numeric substrings from matching |
| Account numbers | Exact digit match (separators stripped) | Fuzzy on digits causes catastrophic over-redaction |
| Custom patterns | Regex with `re.finditer` | Exact by definition |

**Numeric tokens are NEVER fuzzy-matched in isolation.** This is enforced by:

1. `_is_address_candidate()` — rejects any span that is purely numeric or shorter than 5 characters before any fuzzy comparison is attempted
2. An assertion in the matching loop that fires if a numeric-normalized form reaches the fuzzy step

This guarantees that table columns with quantities (1, 4, 9, 11, 37...) or prices ($1.23, $5.67...) are never redacted due to substring matches against a ZIP code or house number in the profile address.

---

## v2 backlog

- Cross-page address split detection
- International address formats (non-US)
- Structured house-number comparison (exact match on number, fuzzy on street name)
- Phone and email detectors wired into profile
- SSN pattern matching
