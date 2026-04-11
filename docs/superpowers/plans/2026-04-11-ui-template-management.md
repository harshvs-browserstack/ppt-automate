# UI & Template Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded single-template generation screen with a multi-template system — template registry, AI suggestion, power-user setup UI, and a rebuilt generation screen with entry banners.

**Architecture:** A JSON file (`templates.json`) stores template definitions; `core/template_registry.py` owns all CRUD. The Streamlit app loads templates at runtime, passes the selected template's `slides_id` and excluded slide numbers directly into the existing pipeline. A new Streamlit page (`pages/1_Template_Setup.py`) handles power-user template creation. The AI suggest flow is a synchronous Gemini call in `core/suggest_template.py`.

**Tech Stack:** Python 3.9, Streamlit, google-genai, google-api-python-client (Slides API), pytest. No new dependencies required.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `core/template_registry.py` | Create | `Template` + `SlideDefault` dataclasses, JSON load/save |
| `core/slides_helpers.py` | Create | Fetch slide titles from Google Slides API |
| `core/suggest_template.py` | Create | Gemini-powered template suggestion |
| `pages/1_Template_Setup.py` | Create | Power-user template setup Streamlit page |
| `tests/test_template_registry.py` | Create | Registry CRUD tests |
| `tests/test_slides_helpers.py` | Create | Slide title extraction tests |
| `tests/test_suggest_template.py` | Create | Suggestion parsing tests |
| `core/config.py` | Modify | Add `power_user_mode: bool`, make `original_slides_id` optional |
| `core/auth_helpers.py` | Modify | Add `get_slides_service()`, add Slides readonly scope |
| `core/formatter_pipeline.py` | Modify | Add `slides_id: str` parameter |
| `core/prompt_templates.py` | Modify | Add `template_context: str` parameter |
| `app.py` | Modify | Rebuild input screen with banners, template row, suggest flow |
| `styles.css` | Modify | Add CSS for banner cards, template tiles, suggest panel |

---

## Task 1: Template Registry

**Files:**
- Create: `core/template_registry.py`
- Create: `tests/test_template_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_template_registry.py
import json, pathlib, tempfile, pytest
from core.template_registry import (
    SlideDefault, Template, load_templates, save_templates,
    get_template_by_id, get_excluded_slide_numbers,
)


def _write_registry(path, data):
    path.write_text(json.dumps(data))


def test_load_returns_empty_list_when_file_missing(tmp_path):
    result = load_templates(str(tmp_path / "missing.json"))
    assert result == []


def test_save_and_load_roundtrip(tmp_path):
    reg = tmp_path / "templates.json"
    t = Template(
        id="t1", name="Battlecard",
        slides_id="abc123",
        variable_label="Competitor Name",
        variable_hint="e.g. Sauce Labs",
        slides=[
            SlideDefault(number=1, title="Cover", enabled=True),
            SlideDefault(number=3, title="Pricing", enabled=False),
        ],
    )
    save_templates([t], str(reg))
    loaded = load_templates(str(reg))
    assert len(loaded) == 1
    assert loaded[0].id == "t1"
    assert loaded[0].name == "Battlecard"
    assert loaded[0].slides[1].enabled is False


def test_get_template_by_id_found(tmp_path):
    reg = tmp_path / "templates.json"
    t = Template(id="x1", name="T", slides_id="s", variable_label="L", variable_hint="H", slides=[])
    save_templates([t], str(reg))
    templates = load_templates(str(reg))
    found = get_template_by_id(templates, "x1")
    assert found is not None
    assert found.name == "T"


def test_get_template_by_id_missing_returns_none():
    assert get_template_by_id([], "nope") is None


def test_get_excluded_slide_numbers():
    t = Template(
        id="t1", name="T", slides_id="s", variable_label="L", variable_hint="H",
        slides=[
            SlideDefault(number=1, title="Cover", enabled=True),
            SlideDefault(number=2, title="Overview", enabled=True),
            SlideDefault(number=3, title="Pricing", enabled=False),
            SlideDefault(number=4, title="FAQ", enabled=False),
        ],
    )
    assert get_excluded_slide_numbers(t) == [3, 4]


def test_get_excluded_slide_numbers_all_enabled():
    t = Template(
        id="t1", name="T", slides_id="s", variable_label="L", variable_hint="H",
        slides=[SlideDefault(number=1, title="Cover", enabled=True)],
    )
    assert get_excluded_slide_numbers(t) == []


def test_save_appends_new_template(tmp_path):
    reg = tmp_path / "templates.json"
    t1 = Template(id="t1", name="A", slides_id="s1", variable_label="L", variable_hint="H", slides=[])
    t2 = Template(id="t2", name="B", slides_id="s2", variable_label="L", variable_hint="H", slides=[])
    save_templates([t1], str(reg))
    save_templates([t1, t2], str(reg))
    loaded = load_templates(str(reg))
    assert len(loaded) == 2


def test_save_overwrites_on_id_collision(tmp_path):
    reg = tmp_path / "templates.json"
    t_old = Template(id="t1", name="Old Name", slides_id="s", variable_label="L", variable_hint="H", slides=[])
    t_new = Template(id="t1", name="New Name", slides_id="s", variable_label="L", variable_hint="H", slides=[])
    save_templates([t_old], str(reg))
    templates = load_templates(str(reg))
    # Replace t_old with t_new
    updated = [t_new if t.id == "t1" else t for t in templates]
    save_templates(updated, str(reg))
    loaded = load_templates(str(reg))
    assert len(loaded) == 1
    assert loaded[0].name == "New Name"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_template_registry.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'core.template_registry'`

- [ ] **Step 3: Implement `core/template_registry.py`**

```python
# core/template_registry.py
"""
Template registry — stores and retrieves slide template definitions.
Templates are persisted as JSON at REGISTRY_PATH (project root / templates.json).
"""
import json
import pathlib
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional

REGISTRY_PATH = pathlib.Path(__file__).parent.parent / "templates.json"


@dataclass
class SlideDefault:
    number: int
    title: str
    enabled: bool


@dataclass
class Template:
    id: str
    name: str
    slides_id: str
    variable_label: str
    variable_hint: str
    slides: List[SlideDefault] = field(default_factory=list)


def load_templates(registry_path: str = str(REGISTRY_PATH)) -> List[Template]:
    """Load all templates from the registry JSON file. Returns [] if file missing."""
    path = pathlib.Path(registry_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    templates = []
    for raw in data.get("templates", []):
        slides = [SlideDefault(**s) for s in raw.get("slides", [])]
        templates.append(Template(
            id=raw["id"],
            name=raw["name"],
            slides_id=raw["slides_id"],
            variable_label=raw["variable_label"],
            variable_hint=raw["variable_hint"],
            slides=slides,
        ))
    return templates


def save_templates(templates: List[Template], registry_path: str = str(REGISTRY_PATH)) -> None:
    """Persist the full template list to the registry JSON file."""
    path = pathlib.Path(registry_path)
    data = {"templates": [
        {**asdict(t)} for t in templates
    ]}
    path.write_text(json.dumps(data, indent=2))


def get_template_by_id(templates: List[Template], template_id: str) -> Optional[Template]:
    """Return the template with the given id, or None if not found."""
    return next((t for t in templates if t.id == template_id), None)


def get_excluded_slide_numbers(template: Template) -> List[int]:
    """Return slide numbers that are disabled (should be excluded from generation)."""
    return [s.number for s in template.slides if not s.enabled]


def new_template_id() -> str:
    """Generate a new unique template ID."""
    return str(uuid.uuid4())[:8]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_template_registry.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add core/template_registry.py tests/test_template_registry.py && git commit -m "feat: add template registry with JSON persistence"
```

---

## Task 2: Update Config + Auth

**Files:**
- Modify: `core/config.py:57-67`
- Modify: `core/auth_helpers.py:1-38`

- [ ] **Step 1: Update `core/config.py`**

Make `original_slides_id` optional (templates now own slides IDs) and add `power_user_mode`:

```python
# Replace the Config dataclass and get_config() in core/config.py

@dataclass
class Config:
    """Configuration dataclass for the application."""
    gemini_api_key: str
    model_id: str
    gas_web_app_url: str
    gdrive_credentials_path: str
    folder_drive_id: str
    slides_batch_size: int
    research_files_folder_id: str
    original_slides_id: str = ""          # optional — templates own slides IDs now
    google_service_account_email: str = ""
    power_user_mode: bool = False          # set POWER_USER_MODE=true to enable


def get_config() -> Config:
    def require(key: str) -> str:
        val = os.getenv(key)
        if not val:
            raise EnvironmentError(f"Required environment variable '{key}' is not set.")
        return val

    return Config(
        gemini_api_key=require("GEMINI_API_KEY"),
        model_id=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"),
        gas_web_app_url=require("GAS_WEB_APP_URL"),
        gdrive_credentials_path=require("GDRIVE_CREDENTIALS_PATH"),
        folder_drive_id=require("FOLDER_DRIVE_ID"),
        slides_batch_size=int(os.getenv("SLIDES_BATCH_SIZE", "5")),
        research_files_folder_id=require("RESEARCH_FILES_FOLDER_ID"),
        original_slides_id=os.getenv("ORIGINAL_SLIDES_ID", ""),
        google_service_account_email=os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", ""),
        power_user_mode=os.getenv("POWER_USER_MODE", "").lower() == "true",
    )
```

- [ ] **Step 2: Update `core/auth_helpers.py`**

Add Slides readonly scope and `get_slides_service()`:

```python
# core/auth_helpers.py
"""
Authentication helpers for Google APIs using service account credentials.
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations.readonly",
]


def get_credentials(credentials_path: str):
    """Return service account credentials with Drive + Sheets + Slides scopes."""
    return service_account.Credentials.from_service_account_file(
        credentials_path, scopes=_SCOPES
    )


def get_drive_service(credentials_path: str):
    """Return an authenticated Google Drive v3 service client."""
    creds = get_credentials(credentials_path)
    return build("drive", "v3", credentials=creds)


def get_sheets_service(credentials_path: str):
    """Return an authenticated Google Sheets v4 service client."""
    creds = get_credentials(credentials_path)
    return build("sheets", "v4", credentials=creds)


def get_slides_service(credentials_path: str):
    """Return an authenticated Google Slides v1 service client."""
    creds = get_credentials(credentials_path)
    return build("slides", "v1", credentials=creds)


def get_gspread_client(credentials_path: str) -> gspread.Client:
    """Return an authenticated gspread client."""
    creds = get_credentials(credentials_path)
    return gspread.authorize(creds)
```

- [ ] **Step 3: Verify existing config tests still pass**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_config.py -v
```

Expected: all tests PASS (original_slides_id is now optional — existing tests may need updating if they assert it raises without it)

- [ ] **Step 4: Fix any broken config tests**

If `test_config.py` asserts `ORIGINAL_SLIDES_ID` is required, remove or update that assertion since it's now optional.

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add core/config.py core/auth_helpers.py tests/test_config.py && git commit -m "feat: add power_user_mode config flag, make ORIGINAL_SLIDES_ID optional, add Slides API scope"
```

---

## Task 3: Slide Title Fetcher

**Files:**
- Create: `core/slides_helpers.py`
- Create: `tests/test_slides_helpers.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_slides_helpers.py
from unittest.mock import MagicMock, patch
from core.slides_helpers import extract_slide_titles_from_presentation


def _make_presentation(slides_data):
    """Build a mock Slides API presentation response."""
    slides = []
    for i, title in enumerate(slides_data, start=1):
        if title is None:
            # Slide with no title placeholder
            page = {"pageElements": []}
        else:
            page = {
                "pageElements": [
                    {
                        "shape": {
                            "placeholder": {"type": "TITLE"},
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": title}}
                                ]
                            },
                        }
                    }
                ]
            }
        slides.append(page)
    return {"slides": slides}


def test_extracts_titles_in_order():
    presentation = _make_presentation(["Cover", "Overview", "Pricing"])
    result = extract_slide_titles_from_presentation(presentation)
    assert result == [
        {"number": 1, "title": "Cover"},
        {"number": 2, "title": "Overview"},
        {"number": 3, "title": "Pricing"},
    ]


def test_falls_back_to_slide_n_when_no_title():
    presentation = _make_presentation(["Cover", None, "Pricing"])
    result = extract_slide_titles_from_presentation(presentation)
    assert result[1] == {"number": 2, "title": "Slide 2"}


def test_empty_presentation_returns_empty_list():
    result = extract_slide_titles_from_presentation({"slides": []})
    assert result == []


def test_strips_trailing_newline_from_title():
    presentation = _make_presentation(["Cover Slide\n"])
    result = extract_slide_titles_from_presentation(presentation)
    assert result[0]["title"] == "Cover Slide"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_slides_helpers.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'core.slides_helpers'`

- [ ] **Step 3: Implement `core/slides_helpers.py`**

```python
# core/slides_helpers.py
"""
Google Slides API helpers.
Fetches slide structure (titles) from a presentation for template setup.
"""
from typing import List, Dict
from core.auth_helpers import get_slides_service


def fetch_slide_titles(credentials_path: str, slides_id: str) -> List[Dict]:
    """
    Fetch slide titles from a Google Slides presentation.

    Args:
        credentials_path: Path to service account JSON credentials
        slides_id: Google Slides presentation ID (not URL)

    Returns:
        List of {"number": int, "title": str} dicts, one per slide
    """
    service = get_slides_service(credentials_path)
    presentation = (
        service.presentations()
        .get(presentationId=slides_id, fields="slides")
        .execute()
    )
    return extract_slide_titles_from_presentation(presentation)


def extract_slide_titles_from_presentation(presentation: Dict) -> List[Dict]:
    """
    Parse a Slides API presentation response and return slide titles.
    Falls back to "Slide N" when a slide has no TITLE placeholder.

    Args:
        presentation: Raw dict from Slides API presentations.get()

    Returns:
        List of {"number": int, "title": str} dicts
    """
    results = []
    for i, slide in enumerate(presentation.get("slides", []), start=1):
        title = _extract_title_from_slide(slide) or f"Slide {i}"
        results.append({"number": i, "title": title})
    return results


def _extract_title_from_slide(slide: Dict) -> str:
    """Return the text of the TITLE placeholder, or empty string if not found."""
    for element in slide.get("pageElements", []):
        shape = element.get("shape", {})
        placeholder = shape.get("placeholder", {})
        if placeholder.get("type") == "TITLE":
            text_content = shape.get("text", {})
            parts = []
            for te in text_content.get("textElements", []):
                if "textRun" in te:
                    parts.append(te["textRun"]["content"])
            return "".join(parts).strip()
    return ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_slides_helpers.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add core/slides_helpers.py tests/test_slides_helpers.py && git commit -m "feat: add slide title fetcher using Google Slides API"
```

---

## Task 4: Update Prompt Templates

**Files:**
- Modify: `core/prompt_templates.py`
- Modify: `tests/test_prompt_templates.py`

- [ ] **Step 1: Write the new failing test**

Add to `tests/test_prompt_templates.py`:

```python
def test_custom_template_context_replaces_battlecard_context():
    """When template_context is provided, it replaces the hardcoded battlecard context."""
    elements = [{"placeholderId": "t1", "originalContent": "Title", "contentRuns": []}]
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="Fintech",
        template_view_pdf_name="ref.pdf",
        template_context="This is an industry pitch deck for the Fintech sector.",
    )
    assert "Fintech" in prompt
    assert "This is an industry pitch deck" in prompt


def test_default_context_is_battlecard():
    """Without template_context, prompt defaults to battlecard language."""
    elements = []
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="Acme",
        template_view_pdf_name="ref.pdf",
    )
    assert "battlecard" in prompt.lower()
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_prompt_templates.py -v 2>&1 | tail -10
```

Expected: `test_custom_template_context_replaces_battlecard_context` FAILS with `TypeError` (unexpected keyword argument)

- [ ] **Step 3: Update `core/prompt_templates.py`**

```python
# core/prompt_templates.py
"""
Prompt templates for Gemini slide content generation.
"""
import json
from typing import Any, Dict, List


def create_slide_generation_prompt(
    slide_elements_json: List[Dict[str, Any]],
    competitor: str,
    template_view_pdf_name: str,
    template_context: str = "",
) -> str:
    """
    Build the Gemini prompt for a single slide's content generation.

    Args:
        slide_elements_json: List of text element dicts
        competitor: Name of competitor or target value
        template_view_pdf_name: Name of the template PDF for reference
        template_context: Optional override for the context section.
            If empty, defaults to battlecard framing.

    Returns:
        A complete prompt string for Gemini
    """
    if not template_context:
        template_context = (
            f"The presentation is a competitive battlecard comparing "
            f"BrowserStack to {competitor}."
        )

    return f"""
You are a helpful assistant tasked with generating presentation slide content in JSON format.
Use the provided JSON template structure as a guide for the output format.
Replace the existing content in the template with new content, drawing from the provided source documents.

**CONTEXT:**
{template_context}
Use the attached research documents to inform the content you generate.
Use the document named {template_view_pdf_name} for context on what the presentation should look like.
The target value for this presentation is: {competitor}

**INPUT SLIDE JSON:**
```json
{json.dumps(slide_elements_json, indent=2)}
```

**INSTRUCTIONS:**
1. **Prioritize Document Context:** Generate content based primarily on the information in the uploaded documents. Avoid hallucinations.
2. **Fill Information Gaps:** If specific information is missing from the documents, use your search tool to find current details.
3. **JSON Output Requirements:**
   - Return a single valid JSON array of the text elements for this slide.
   - Never change objectIds, placeholderIds, or any style objects.
   - Only replace text within the "text" fields inside "contentRuns" arrays.
   - Preserve all escape characters like \\n.
4. **Content:** Keep texts between 95-105% of the original character count. Maintain a professional tone.
5. **References:** Only add references in speaker notes, in Chicago MLA format.

Generate the JSON slide content:
"""
```

- [ ] **Step 4: Run all prompt template tests**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_prompt_templates.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add core/prompt_templates.py tests/test_prompt_templates.py && git commit -m "feat: add template_context parameter to prompt builder"
```

---

## Task 5: Update Pipeline to Accept slides_id

**Files:**
- Modify: `core/formatter_pipeline.py:213-220`
- Modify: `tests/test_formatter_helpers.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_formatter_helpers.py`:

```python
import pytest

def test_run_ai_content_population_signature_accepts_slides_id():
    """run_ai_content_population must accept a slides_id keyword argument."""
    import inspect
    from core.formatter_pipeline import run_ai_content_population
    sig = inspect.signature(run_ai_content_population)
    assert "slides_id" in sig.parameters
    # slides_id should be optional (has a default)
    assert sig.parameters["slides_id"].default is None
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_formatter_helpers.py::test_run_ai_content_population_signature_accepts_slides_id -v
```

Expected: FAIL — `AssertionError: 'slides_id' not in parameters`

- [ ] **Step 3: Add `slides_id` parameter to `run_ai_content_population`**

In `core/formatter_pipeline.py`, update the function signature at line 213:

```python
async def run_ai_content_population(
    pdf_bytes: bytes,
    pdf_filename: str,
    competitor: str,
    config: Config,
    slides_id: Optional[str] = None,
    excluded_slide_numbers: Optional[List[int]] = None,
    template_view_pdf_name: Optional[str] = None,
    on_status: Optional[Callable[[str, float, Optional[str]], None]] = None,
) -> str:
```

Then in step 1b (around line 273), replace the `ORIGINAL_SLIDES_ID` property setting:

```python
# Step 1b: Set Apps Script properties
print("[1b/7] Configuring Apps Script properties...")
effective_slides_id = slides_id or config.original_slides_id
if not effective_slides_id:
    raise ValueError(
        "No slides_id provided and ORIGINAL_SLIDES_ID env var is not set. "
        "Select a template or set ORIGINAL_SLIDES_ID."
    )
await _set_apps_script_property(
    client_httpx, config.gas_web_app_url,
    "ORIGINAL_SLIDES_ID", effective_slides_id
)
await _set_apps_script_property(
    client_httpx, config.gas_web_app_url,
    "FOLDER_DRIVE_ID", config.folder_drive_id
)
if config.google_service_account_email:
    await _set_apps_script_property(
        client_httpx, config.gas_web_app_url,
        "SERVICE_ACCOUNT_EMAIL", config.google_service_account_email
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_formatter_helpers.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add core/formatter_pipeline.py tests/test_formatter_helpers.py && git commit -m "feat: pipeline accepts slides_id param, falls back to ORIGINAL_SLIDES_ID env var"
```

---

## Task 6: AI Template Suggestion

**Files:**
- Create: `core/suggest_template.py`
- Create: `tests/test_suggest_template.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_suggest_template.py
import pytest
from core.template_registry import Template
from core.suggest_template import parse_suggestion_response, SuggestionResult


TEMPLATES = [
    Template(id="t1", name="Competitor Battlecard", slides_id="s1",
             variable_label="Competitor Name", variable_hint="e.g. Sauce Labs", slides=[]),
    Template(id="t2", name="Industry Pitch Deck", slides_id="s2",
             variable_label="Client Industry", variable_hint="e.g. Fintech", slides=[]),
]


def test_parse_valid_response():
    raw = '{"template_id": "t1", "reason": "Looks like a comparison.", "extracted_target": "Sauce Labs"}'
    result = parse_suggestion_response(raw, TEMPLATES)
    assert result.template_id == "t1"
    assert result.reason == "Looks like a comparison."
    assert result.extracted_target == "Sauce Labs"


def test_parse_null_extracted_target():
    raw = '{"template_id": "t2", "reason": "Looks like a pitch.", "extracted_target": null}'
    result = parse_suggestion_response(raw, TEMPLATES)
    assert result.extracted_target is None


def test_parse_unknown_template_id_falls_back_to_first():
    raw = '{"template_id": "unknown", "reason": "Not sure.", "extracted_target": null}'
    result = parse_suggestion_response(raw, TEMPLATES)
    assert result.template_id == "t1"


def test_parse_malformed_json_falls_back_to_first():
    result = parse_suggestion_response("this is not json", TEMPLATES)
    assert result.template_id == "t1"
    assert "could not" in result.reason.lower()


def test_parse_empty_templates_list_raises():
    with pytest.raises(ValueError, match="No templates"):
        parse_suggestion_response('{"template_id": "t1", "reason": "x", "extracted_target": null}', [])
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_suggest_template.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'core.suggest_template'`

- [ ] **Step 3: Implement `core/suggest_template.py`**

```python
# core/suggest_template.py
"""
AI-powered template suggestion using Gemini.
Given a natural language description, returns the best matching template
and optionally the extracted target value (competitor name, industry, etc.).
"""
import json
from dataclasses import dataclass
from typing import List, Optional

from google import genai

from core.template_registry import Template


@dataclass
class SuggestionResult:
    template_id: str
    reason: str
    extracted_target: Optional[str]


def suggest_template(
    description: str,
    templates: List[Template],
    api_key: str,
    model_id: str = "gemini-2.5-flash",
) -> SuggestionResult:
    """
    Use Gemini to suggest the best template for the given description.

    Args:
        description: Natural language description of what the user needs
        templates: Available templates to choose from
        api_key: Gemini API key
        model_id: Gemini model to use

    Returns:
        SuggestionResult with template_id, reason, and optional extracted_target
    """
    if not templates:
        raise ValueError("No templates available to suggest from.")

    template_list = "\n".join(
        f'- id: "{t.id}", name: "{t.name}", variable: "{t.variable_label}"'
        for t in templates
    )

    prompt = f"""You are helping a user pick the right presentation template.

Available templates:
{template_list}

User description: "{description}"

Pick the best template for this description. Also try to extract the specific target value
(e.g. the competitor name, industry name, or client name) from the description if it's mentioned.

Respond with ONLY valid JSON in this exact format:
{{
  "template_id": "<id of the best matching template>",
  "reason": "<one sentence explaining why this template fits>",
  "extracted_target": "<the extracted target value, or null if not mentioned>"
}}"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
    )
    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return parse_suggestion_response(raw.strip(), templates)


def parse_suggestion_response(raw: str, templates: List[Template]) -> SuggestionResult:
    """
    Parse a raw Gemini JSON response string into a SuggestionResult.
    Falls back to the first template if parsing fails or template_id is unknown.

    Args:
        raw: Raw JSON string from Gemini
        templates: Available templates (must not be empty)
    """
    if not templates:
        raise ValueError("No templates provided to parse_suggestion_response.")

    fallback_id = templates[0].id
    valid_ids = {t.id for t in templates}

    try:
        data = json.loads(raw)
        template_id = data.get("template_id", fallback_id)
        if template_id not in valid_ids:
            template_id = fallback_id
        return SuggestionResult(
            template_id=template_id,
            reason=data.get("reason", ""),
            extracted_target=data.get("extracted_target") or None,
        )
    except (json.JSONDecodeError, AttributeError):
        return SuggestionResult(
            template_id=fallback_id,
            reason="Could not parse suggestion — defaulting to first template.",
            extracted_target=None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/test_suggest_template.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add core/suggest_template.py tests/test_suggest_template.py && git commit -m "feat: add AI template suggestion with Gemini"
```

---

## Task 7: Template Setup Page (Power User)

**Files:**
- Create: `pages/1_Template_Setup.py`

No unit tests — this is a Streamlit page; verify manually.

- [ ] **Step 1: Create `pages/` directory and `__init__.py`**

```bash
mkdir -p /Users/harshvardhan/Desktop/Dev/ppt-automate/pages && touch /Users/harshvardhan/Desktop/Dev/ppt-automate/pages/__init__.py
```

- [ ] **Step 2: Create `pages/1_Template_Setup.py`**

```python
# pages/1_Template_Setup.py
"""
Template Setup — power user page for creating and editing templates.
Only accessible when POWER_USER_MODE=true.
"""
import streamlit as st
from core.config import get_config
from core.template_registry import (
    Template, SlideDefault, load_templates, save_templates,
    get_template_by_id, new_template_id, REGISTRY_PATH,
)
from core.slides_helpers import fetch_slide_titles
from core.auth_helpers import get_credentials
import re

st.set_page_config(page_title="Template Setup", layout="centered")

config = get_config()

if not config.power_user_mode:
    st.error("Template setup requires POWER_USER_MODE=true.")
    st.stop()

# ── Session state ──────────────────────────────────────────────────────────
if "setup_slides_loaded" not in st.session_state:
    st.session_state.setup_slides_loaded = []  # list of {"number": int, "title": str}
if "setup_slide_defaults" not in st.session_state:
    st.session_state.setup_slide_defaults = {}  # {number: bool}
if "setup_editing_id" not in st.session_state:
    st.session_state.setup_editing_id = None  # template id being edited, or None for new


# ── Helpers ────────────────────────────────────────────────────────────────
def _extract_slides_id(value: str) -> str:
    """Extract presentation ID from a Google Slides URL or return as-is."""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", value)
    return match.group(1) if match else value.strip()


# ── Page ───────────────────────────────────────────────────────────────────
st.title("Template Setup")
st.caption("Create and manage presentation templates.")

templates = load_templates()

# ── Existing templates list ────────────────────────────────────────────────
if templates:
    st.subheader("Existing Templates")
    for t in templates:
        col1, col2 = st.columns([5, 1])
        col1.markdown(f"**{t.name}** — `{t.variable_label}`")
        if col2.button("Edit", key=f"edit_{t.id}"):
            st.session_state.setup_editing_id = t.id
            # Pre-populate slides from saved defaults
            st.session_state.setup_slides_loaded = [
                {"number": s.number, "title": s.title} for s in t.slides
            ]
            st.session_state.setup_slide_defaults = {
                s.number: s.enabled for s in t.slides
            }
            st.rerun()

st.divider()

# ── Form: create or edit ───────────────────────────────────────────────────
editing = get_template_by_id(templates, st.session_state.setup_editing_id) if st.session_state.setup_editing_id else None
form_title = f"Edit: {editing.name}" if editing else "New Template"
st.subheader(form_title)

template_name = st.text_input(
    "Template Name",
    value=editing.name if editing else "",
    placeholder="e.g. Industry Targeted Comparison",
)

slides_url = st.text_input(
    "Google Slides Template",
    value=editing.slides_id if editing else "",
    placeholder="Paste Google Slides URL or ID",
)

col_load, col_hint = st.columns([2, 5])
load_clicked = col_load.button("Load Slides →")
col_hint.caption("Fetches slide structure from your template deck.")

if load_clicked and slides_url.strip():
    slides_id = _extract_slides_id(slides_url.strip())
    with st.spinner("Fetching slides..."):
        try:
            titles = fetch_slide_titles(config.gdrive_credentials_path, slides_id)
            st.session_state.setup_slides_loaded = titles
            st.session_state.setup_slide_defaults = {s["number"]: True for s in titles}
            st.success(f"Loaded {len(titles)} slides.")
        except Exception as e:
            st.error(f"Could not load slides: {e}")

col_lbl, col_hint_input = st.columns(2)
variable_label = col_lbl.text_input(
    "Label shown to users",
    value=editing.variable_label if editing else "",
    placeholder="e.g. Competitor Name",
)
variable_hint = col_hint_input.text_input(
    "Placeholder hint",
    value=editing.variable_hint if editing else "",
    placeholder="e.g. Sauce Labs",
)

# ── Slide defaults ─────────────────────────────────────────────────────────
if st.session_state.setup_slides_loaded:
    st.markdown("**Slides — Set Defaults**")
    st.caption("Toggle off slides that should be hidden by default.")
    for slide in st.session_state.setup_slides_loaded:
        num = slide["number"]
        default_val = st.session_state.setup_slide_defaults.get(num, True)
        enabled = st.toggle(
            f"Slide {num}: {slide['title']}",
            value=default_val,
            key=f"slide_toggle_{num}",
        )
        st.session_state.setup_slide_defaults[num] = enabled

# ── Save ───────────────────────────────────────────────────────────────────
if st.button("Save Template", type="primary"):
    if not template_name.strip():
        st.error("Template name is required.")
    elif not slides_url.strip():
        st.error("Google Slides URL or ID is required.")
    elif not variable_label.strip():
        st.error("Variable label is required.")
    else:
        slides_id = _extract_slides_id(slides_url.strip())
        slide_defaults = [
            SlideDefault(
                number=s["number"],
                title=s["title"],
                enabled=st.session_state.setup_slide_defaults.get(s["number"], True),
            )
            for s in st.session_state.setup_slides_loaded
        ]
        new_t = Template(
            id=editing.id if editing else new_template_id(),
            name=template_name.strip(),
            slides_id=slides_id,
            variable_label=variable_label.strip(),
            variable_hint=variable_hint.strip(),
            slides=slide_defaults,
        )
        # Replace or append
        updated = [new_t if t.id == new_t.id else t for t in templates]
        if new_t.id not in {t.id for t in templates}:
            updated.append(new_t)
        save_templates(updated)
        st.success(f"Template '{new_t.name}' saved.")
        # Reset form state
        st.session_state.setup_editing_id = None
        st.session_state.setup_slides_loaded = []
        st.session_state.setup_slide_defaults = {}
        st.rerun()
```

- [ ] **Step 3: Verify the page loads**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && POWER_USER_MODE=true streamlit run app.py --server.headless true &
sleep 3 && curl -s http://localhost:8501 | grep -o "Template Setup\|Streamlit" | head -3
```

Expected: Streamlit serving without import errors. Manually open `http://localhost:8501/Template_Setup` to verify the page renders.

- [ ] **Step 4: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add pages/ && git commit -m "feat: add power-user template setup page"
```

---

## Task 8: Rebuild app.py Input Screen

**Files:**
- Modify: `app.py`
- Modify: `styles.css`

- [ ] **Step 1: Add CSS for new components to `styles.css`**

Append to `styles.css`:

```css
/* ============================================================================
   26. TEMPLATE TILES & BANNER CARDS
   ============================================================================ */

/* Banner card — used for Quick Generate / Custom Build entry points */
.banner-card {
  padding: 1rem;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.banner-card:hover { opacity: 0.9; }
.banner-card-primary {
  background-color: var(--primary);
  color: white;
}
.banner-card-outline {
  background-color: var(--surface);
  border: 1.5px solid var(--primary);
  color: var(--primary);
}

/* Suggest panel — inline AI suggestion area */
.suggest-panel {
  background-color: rgba(30, 27, 75, 0.03);
  border: 1.5px solid var(--primary);
  padding: 1rem;
  margin-bottom: 0.5rem;
}

/* Suggestion result card */
.suggestion-card {
  background-color: rgba(5, 150, 105, 0.05);
  border: 1.5px solid var(--accent);
  padding: 1rem;
  margin-bottom: 0.5rem;
}

/* Auto-filled badge */
.auto-filled-badge {
  display: inline-block;
  background-color: rgba(5, 150, 105, 0.1);
  color: var(--accent);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
  margin-left: 8px;
  vertical-align: middle;
}

/* Active template status bar */
.template-status-bar {
  background-color: var(--primary);
  color: white;
  padding: 0.4rem 0.75rem;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

/* Section label */
.section-label {
  font-family: var(--sans-font);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
  margin-bottom: 0.4rem;
}
```

- [ ] **Step 2: Rebuild `app.py` input state**

Replace the entire `app.py` with:

```python
# app.py
import asyncio
import os
import pathlib
import streamlit as st

st.set_page_config(
    page_title="Document to Deck",
    page_icon="✨",
    layout="centered",
)

css_path = pathlib.Path(__file__).parent / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from core.config import get_config
from core.template_registry import load_templates, get_template_by_id, get_excluded_slide_numbers, REGISTRY_PATH
from core.suggest_template import suggest_template

config = get_config()

# ── Session state ──────────────────────────────────────────────────────────
defaults = {
    "app_state": "input",
    "final_url": None,
    "error_msg": None,
    "pdf_bytes": None,
    "pdf_filename": None,
    "target": "",
    "selected_template_id": None,
    "suggest_mode": False,
    "suggest_result": None,      # SuggestionResult or None
    "auto_filled_target": False,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Helpers ────────────────────────────────────────────────────────────────
def _select_template(template_id: str, target: str = None):
    st.session_state.selected_template_id = template_id
    st.session_state.suggest_mode = False
    st.session_state.suggest_result = None
    if target is not None:
        st.session_state.target = target
        st.session_state.auto_filled_target = True
    else:
        st.session_state.auto_filled_target = False


# ── State: INPUT ───────────────────────────────────────────────────────────
if st.session_state.app_state == "input":

    templates = load_templates()
    selected_template = get_template_by_id(templates, st.session_state.selected_template_id)

    # ── Hero ───────────────────────────────────────────────────────────────
    st.markdown(
        '<h1 style="font-family:\'Newsreader\',serif;font-size:2rem;font-weight:600;'
        'color:#111827;margin-bottom:0.25rem">Turn Research Into a Deck</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Upload your PDF, pick a template, and let AI do the rest.")
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Entry banners (Quick Generate / Custom Build) ──────────────────────
    if not selected_template:
        col_quick, col_custom = st.columns(2)

        with col_quick:
            st.markdown(
                '<div class="banner-card banner-card-primary">'
                '<div style="font-size:0.65rem;opacity:0.7;text-transform:uppercase;'
                'letter-spacing:0.08em;margin-bottom:4px">⚡ Quick Generate</div>'
                '<div style="font-size:0.9rem;font-weight:600;margin-bottom:4px">'
                'Describe your goal, AI handles the rest</div>'
                '<div style="font-size:0.75rem;opacity:0.75">'
                'AI suggests the right template and fills the details.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Click to start →", key="btn_quick", use_container_width=True):
                st.session_state.suggest_mode = True
                st.rerun()

        with col_custom:
            st.markdown(
                '<div class="banner-card banner-card-outline">'
                '<div style="font-size:0.65rem;opacity:0.6;text-transform:uppercase;'
                'letter-spacing:0.08em;margin-bottom:4px">🎛 Custom Build</div>'
                '<div style="font-size:0.9rem;font-weight:600;margin-bottom:4px">'
                'Pick a template, set your target, upload</div>'
                '<div style="font-size:0.75rem;opacity:0.65">'
                'Select from the library and configure before generating.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button("Browse templates →", key="btn_custom", use_container_width=True):
                # Just scroll focus to template row — no action needed, it's always visible
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

    else:
        # Slim status bar after template is selected
        path_label = "⚡ Quick Generate" if st.session_state.suggest_result else "🎛 Custom Build"
        col_bar, col_change = st.columns([5, 1])
        col_bar.markdown(
            f'<div class="template-status-bar">'
            f'<span style="opacity:0.7;font-size:0.7rem">{path_label}</span>'
            f'<span>·</span>'
            f'<span><strong>{selected_template.name}</strong></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if col_change.button("Change", key="btn_change"):
            st.session_state.selected_template_id = None
            st.session_state.suggest_mode = False
            st.session_state.suggest_result = None
            st.session_state.auto_filled_target = False
            st.rerun()

    # ── Suggest Template inline flow ───────────────────────────────────────
    if st.session_state.suggest_mode and not selected_template:
        st.markdown('<div class="suggest-panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-label">What do you need?</div>', unsafe_allow_html=True)
        description = st.text_area(
            label="description",
            label_visibility="collapsed",
            placeholder="e.g. I need a deck comparing BrowserStack to Sauce Labs for an enterprise fintech prospect...",
            height=80,
            key="suggest_description",
        )
        col_suggest_btn, col_cancel = st.columns([2, 1])
        suggest_clicked = col_suggest_btn.button("Suggest →", key="btn_suggest", type="primary")
        if col_cancel.button("Cancel", key="btn_cancel_suggest"):
            st.session_state.suggest_mode = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        if suggest_clicked and description.strip() and templates:
            with st.spinner("Finding the right template..."):
                result = suggest_template(
                    description=description.strip(),
                    templates=templates,
                    api_key=config.gemini_api_key,
                    model_id=config.model_id,
                )
            st.session_state.suggest_result = result
            st.rerun()

        # Show suggestion result card
        if st.session_state.suggest_result:
            r = st.session_state.suggest_result
            suggested_t = get_template_by_id(templates, r.template_id)
            if suggested_t:
                st.markdown(
                    f'<div class="suggestion-card">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                    f'<span style="background:#059669;color:#fff;font-size:0.65rem;font-weight:700;'
                    f'padding:2px 8px">✦ Suggested</span>'
                    f'<strong style="color:#111827">{suggested_t.name}</strong>'
                    f'</div>'
                    f'<p style="font-size:0.8rem;color:#6B7280;margin-bottom:0">{r.reason}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                col_use, col_pick = st.columns([3, 1])
                if col_use.button(f"Use {suggested_t.name} →", key="btn_use_suggestion", type="primary", use_container_width=True):
                    _select_template(r.template_id, r.extracted_target)
                    st.rerun()
                if col_pick.button("Pick another", key="btn_pick_another", use_container_width=True):
                    st.session_state.suggest_result = None
                    st.rerun()

    # ── Template row ───────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Template</div>', unsafe_allow_html=True)

    col_row_label, col_add = st.columns([5, 1])
    if config.power_user_mode:
        if col_add.button("+ Add", key="btn_add_template"):
            st.switch_page("pages/1_Template_Setup.py")

    if not templates:
        st.info("No templates yet. Add one with + Add Template." if config.power_user_mode
                else "No templates available. Contact your template manager.")
    else:
        suggest_cols = st.columns(min(len(templates) + 1, 5))
        # Suggest button first
        if suggest_cols[0].button("✦ Suggest", key="btn_suggest_row",
                                   type="primary" if not st.session_state.suggest_mode else "secondary"):
            st.session_state.suggest_mode = True
            st.rerun()
        # Template tiles
        for i, t in enumerate(templates):
            col = suggest_cols[i + 1] if i + 1 < len(suggest_cols) else suggest_cols[-1]
            is_selected = st.session_state.selected_template_id == t.id
            btn_type = "primary" if is_selected else "secondary"
            label = f"✓ {t.name}" if is_selected else t.name
            if col.button(label, key=f"tile_{t.id}", type=btn_type, use_container_width=True):
                _select_template(t.id)
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Variable field (appears after template selected) ───────────────────
    if selected_template:
        label_text = selected_template.variable_label
        if st.session_state.auto_filled_target:
            label_html = (
                f'<div class="section-label">{label_text}'
                f'<span class="auto-filled-badge">auto-filled</span></div>'
            )
            st.markdown(label_html, unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="section-label">{label_text}</div>', unsafe_allow_html=True)

        target = st.text_input(
            label=label_text,
            label_visibility="collapsed",
            value=st.session_state.target,
            placeholder=selected_template.variable_hint,
            key="target_input",
        )
        st.session_state.target = target

        st.markdown("<br>", unsafe_allow_html=True)

        # ── PDF Upload ─────────────────────────────────────────────────────
        st.markdown('<div class="section-label">Research PDF</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            label="PDF",
            label_visibility="collapsed",
            type=["pdf"],
        )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.session_state.error_msg:
            st.error(st.session_state.error_msg)
            st.session_state.error_msg = None

        if st.button("Generate Deck →", type="primary", use_container_width=True):
            if not uploaded_file:
                st.error("Please upload a PDF before generating.")
            elif not target.strip():
                st.error(f"Please enter {selected_template.variable_label}.")
            else:
                st.session_state.pdf_bytes = uploaded_file.read()
                st.session_state.pdf_filename = uploaded_file.name
                st.session_state.target = target.strip()
                st.session_state.app_state = "loading"
                st.rerun()


# ── State: LOADING ─────────────────────────────────────────────────────────
elif st.session_state.app_state == "loading":
    st.title("Generating Your Presentation")
    st.caption("This may take a few minutes. Do not close this tab.")
    st.markdown("<br>", unsafe_allow_html=True)

    status_label = st.empty()
    progress_bar = st.progress(0.0)
    sub_label = st.empty()

    def on_status(message: str, progress: float, sub: str = None):
        status_label.markdown(f"**{message}**")
        progress_bar.progress(min(progress, 1.0))
        if sub:
            sub_label.caption(sub)
        else:
            sub_label.empty()

    try:
        from core.formatter_pipeline import run_ai_content_population

        templates = load_templates()
        selected_template = get_template_by_id(templates, st.session_state.selected_template_id)

        slides_id = selected_template.slides_id if selected_template else config.original_slides_id
        excluded = get_excluded_slide_numbers(selected_template) if selected_template else []

        final_url = asyncio.run(
            run_ai_content_population(
                pdf_bytes=st.session_state.pdf_bytes,
                pdf_filename=st.session_state.pdf_filename,
                competitor=st.session_state.target,
                config=config,
                slides_id=slides_id,
                excluded_slide_numbers=excluded,
                on_status=on_status,
            )
        )

        progress_bar.progress(1.0)
        status_label.markdown("**Done!**")
        sub_label.empty()

        st.session_state.final_url = final_url
        st.session_state.app_state = "success"
        st.rerun()

    except Exception as e:
        st.session_state.error_msg = f"Pipeline failed: {e}"
        st.session_state.app_state = "input"
        st.rerun()


# ── State: SUCCESS ─────────────────────────────────────────────────────────
elif st.session_state.app_state == "success":
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;padding:2rem 0 1rem;">'
        '<div style="width:48px;height:48px;background:#059669;border-radius:50%;'
        'display:flex;align-items:center;justify-content:center;margin-bottom:1.5rem;">'
        '<span style="color:white;font-size:24px;">✓</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.title("Presentation Ready")
    st.markdown("<br>", unsafe_allow_html=True)

    final_url = st.session_state.final_url
    if final_url:
        st.markdown(
            f'<a href="{final_url}" target="_blank" '
            f'style="display:flex;align-items:center;justify-content:center;gap:8px;'
            f'width:100%;height:48px;background:#1E1B4B;color:#FFFFFF;'
            f'font-family:\'Switzer\',sans-serif;font-size:14px;font-weight:500;'
            f'text-decoration:none;border:none;transition:background 0.2s;">'
            f'View in Google Slides <span style="font-size:16px;">↗</span>'
            f'</a>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Generate Another"):
        for key in ["app_state", "final_url", "pdf_bytes", "pdf_filename",
                    "target", "selected_template_id", "suggest_mode",
                    "suggest_result", "auto_filled_target"]:
            st.session_state[key] = defaults[key]
        st.rerun()
```

- [ ] **Step 3: Run the full test suite**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Smoke-test the app**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && source .venv/bin/activate && streamlit run app.py
```

Verify manually:
- App loads without errors
- With no `templates.json`: info message shows (no crash)
- With `POWER_USER_MODE=true`: "+ Add" button appears in template row
- After adding a template via `Template_Setup` page: tile appears in main screen
- Quick Generate banner click opens suggest textarea
- Custom Build banner click does nothing harmful (template row is already visible)

- [ ] **Step 5: Commit**

```bash
cd /Users/harshvardhan/Desktop/Dev/ppt-automate && git add app.py styles.css pages/ && git commit -m "feat: rebuild input screen with template row, banners, and AI suggest flow"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Implemented in |
|---|---|
| Two entry banners (Quick Generate / Custom Build) | Task 8 — `app.py` |
| Banners are clickable entry points | Task 8 — Quick Generate sets `suggest_mode`, Custom Build is cosmetic |
| Template row with Suggest, tiles, + Add Template | Task 8 |
| + Add Template visible only to power users | Task 8 — gated on `config.power_user_mode` |
| Single dynamic variable field, label from template | Task 8 |
| No slide toggles for end users | Task 8 — only pipeline receives `excluded_slide_numbers` |
| Banners collapse to slim bar after selection | Task 8 |
| AI Suggest: natural language input inline | Task 8 |
| AI Suggest: shows reason | Task 6 + Task 8 |
| AI Suggest: auto-fills variable if target extracted | Task 8 — `auto_filled_target` badge |
| Template setup: Name, Slides URL, Load, variable, slide defaults | Task 7 |
| Slide names from slide titles in Google Slides | Task 3 |
| Slide defaults set at template setup, not generation | Task 7 (setup), Task 8 (generation — no toggles shown) |
| `POWER_USER_MODE` env flag | Task 2 |
| Pipeline accepts `slides_id` from template | Task 5 |
| Prompt supports non-battlecard context | Task 4 |

All spec requirements covered. ✓
