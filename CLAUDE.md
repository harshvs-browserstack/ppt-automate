# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

"Document-to-Deck" — an AI pipeline that converts PDF research documents into populated Google Slides presentations. Users upload PDFs, a Gemini model generates slide content, and a Google Apps Script backend clones a template and writes the content into Google Slides.

The project is being converted from a Google Colab notebook into a Streamlit web application.

## Architecture: The Three-System Pipeline

The pipeline spans three systems that communicate via REST and Google APIs:

1. **Python backend** (`core/formatter_pipeline.py`, refactored from `[Script]_Formatter_Release.ipynb`)
   - Uploads PDFs to the Gemini File API
   - Fetches a style map JSON from Google Drive (describes every text element per slide)
   - Sends batches of slides to Gemini for content generation (async, `SLIDES_BATCH_SIZE` at a time)
   - Merges AI output back into the style map DataFrame
   - Writes the final DataFrame to a Google Sheet

2. **Google Apps Script** (exported as `PPT Generator - Release .json`, contains 5 files: Main, New TemplateGenerator, New Populate, WebApp, appsscript)
   - Exposes a `doGet` web app endpoint (`GAS_WEB_APP_URL`)
   - Three modes triggered via `?action=run&mode=<mode>`:
     - `destructor` — clears script properties
     - `template` — clones the master slide deck and extracts a style map JSON + content sheet
     - `slides` — reads the content sheet and populates the cloned deck; returns the final Slides URL
   - Config is exchanged via Apps Script `ScriptProperties` (STYLEMAP_FILE_ID, CONTENT_SHEET_ID, etc.)

3. **Streamlit frontend** (`app.py`, to be built)
   - Three UI states managed via `st.session_state.app_state`: `input` → `loading` → `success`
   - Calls `run_ai_content_population()` during the loading state
   - Returns the final Google Slides URL on success

**Data flow:** PDF → Gemini File API → AI generates JSON per slide → DataFrame written to Google Sheet → Apps Script reads sheet → populates cloned Google Slides → returns URL.

## Key Configuration

Environment variables in `.env`:
- `GEMINI_API_KEY` / `GEMINI_MODEL_ID` / `GEMINI_PRO_MODEL_ID` — Gemini auth and model selection
- `GAS_WEB_APP_URL` — the deployed Google Apps Script web app endpoint
- `GDRIVE_CREDENTIALS_PATH` — service account JSON for Drive/Sheets access
- `GOOGLE_SHARED_DRIVE_ID` — shared drive for output files

The notebook also has inline config (cell-4): `ORIGINAL_SLIDES_ID` (template deck), `FOLDER_DRIVE_ID` (output folder), `MODEL_ID`, `API_KEY_NAME`, `SLIDES_BATCH_SIZE`.

## Commands

```bash
# Activate venv (Python 3.9)
source .venv/bin/activate

# Run the Streamlit app
streamlit run app.py

# Install dependencies (once requirements.txt exists)
pip install -r requirements.txt
```

No test suite or linter is configured yet.

## Design System

The `stitch/` folder contains Stitch-generated design screens and a design system. Key references:
- `stitch/editorial_enterprise_blend_prd.html` — PRD with color palette, typography, and screen flow
- `stitch/titanium_stack/DESIGN.md` — full design system spec (colors, typography, elevation, components)
- `stitch/{input_state,active_upload_state,loading_state,success_state,template_management}/` — screen PNGs + HTML code for each UI state

Design constants: primary `#1E1B4B` (deep indigo), background `#F9FAFB`, surface `#FFFFFF`, accent `#059669` (emerald for success). Headings use `Newsreader` (serif), body uses `Switzer` (sans-serif). Sharp 0px border-radius on the main card for editorial feel.

## Async Considerations

The core pipeline (`run_ai_content_population`) is `async`. When calling from Streamlit (which is synchronous), use `asyncio.run()` or manage the event loop explicitly. The notebook uses `await` directly because Colab runs an event loop at top level.

## Google Apps Script Interaction Pattern

The Python code communicates with Apps Script exclusively via HTTP GET requests with query parameters. The pattern for setting properties:
```
GET {GAS_WEB_APP_URL}?action=setProperty&key=KEY&value=VALUE
```
The pattern for running pipeline stages:
```
GET {GAS_WEB_APP_URL}?action=run&mode={destructor|template|slides}
```
The `slides` mode returns JSON with a `url` field containing the final Google Slides link.
