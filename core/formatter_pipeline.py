"""
Document-to-Deck pipeline.
Refactored from [Script]_Formatter_Release.ipynb — all Colab-specific code removed.
"""
import asyncio, io, json, os, re, tempfile, time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import httpx, pandas as pd
from google import genai
from google.genai import types
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from tqdm import tqdm

from core.auth_helpers import get_drive_service, get_sheets_service
from core.config import Config
from core.prompt_templates import create_slide_generation_prompt
from core.history import log_generation


def contains_url(text: str) -> bool:
    """Return True if the string contains an HTTP/HTTPS URL."""
    url_pattern = re.compile(r"https?://(?:www\.)?\S+\.\S+")
    return bool(url_pattern.search(text))


def extract_id_from_url(value: str) -> str:
    """
    Extract a Google resource ID from a URL like .../d/<ID>/...
    Returns the value unchanged if it is not a URL.
    """
    if not contains_url(value):
        return value
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", value)
    return match.group(1) if match else value


def _merge_ai_output_with_template(
    original_df: pd.DataFrame, ai_data_list: List[Dict]
) -> pd.DataFrame:
    """
    Merge AI-generated contentRuns into the original style-map DataFrame.
    Rows are matched on placeholderId. Last occurrence wins on duplicates.
    """
    if not ai_data_list:
        return original_df.copy()
    ai_df = pd.DataFrame(ai_data_list)
    if not {"placeholderId", "contentRuns"}.issubset(ai_df.columns):
        return original_df.copy()
    ai_df_unique = ai_df.drop_duplicates(subset=["placeholderId"], keep="last")
    ai_mapping = ai_df_unique.set_index("placeholderId")["contentRuns"]
    merged = original_df.copy()
    mapped = merged["placeholderId"].map(ai_mapping)
    merged["contentRuns"] = mapped.where(mapped.notna(), merged["contentRuns"])
    return merged


# ============================================================================
# I/O Helper Functions
# ============================================================================


def _read_json_from_drive(file_id: str, credentials_path: str) -> dict:
    """Download a JSON file from Google Drive by file ID."""
    service = get_drive_service(credentials_path)
    file_metadata = service.files().get(
        fileId=file_id, fields="name", supportsAllDrives=True
    ).execute()
    print(f"   -> Downloading '{file_metadata.get('name')}' (ID: {file_id})...")
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return json.loads(fh.read().decode("utf-8"))


def _write_dataframe_to_sheet(
    sheet_id: str, range_name: str, df: pd.DataFrame, credentials_path: str
) -> None:
    """Write a DataFrame to a Google Sheet, clearing existing content first."""
    service = get_sheets_service(credentials_path)
    df_clean = df.fillna("")
    values = [df_clean.columns.tolist()] + df_clean.values.tolist()
    body = {"values": values}
    service.spreadsheets().values().clear(
        spreadsheetId=sheet_id, range=range_name
    ).execute()
    result = service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body,
    ).execute()
    print(f"   -> Updated {result.get('updatedCells')} cells in Sheet ID: {sheet_id}")


def _get_file_id_by_name(filename: str, credentials_path: str) -> Optional[str]:
    """Search Google Drive for a file by name, return its ID or None."""
    try:
        service = get_drive_service(credentials_path)
        query = f"name = '{filename}' and trashed = false"
        results = service.files().list(
            q=query, spaces="drive", fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None
    except Exception:
        return None


def _upload_and_wait_for_files(
    client_genai: Any, file_paths: List[str]
) -> List[Any]:
    """Upload local PDF paths to the Gemini File API and wait until ACTIVE."""
    uploaded = []
    print(f"   -> Uploading {len(file_paths)} files to Gemini...")
    for path in file_paths:
        f = client_genai.files.upload(
            file=path, config={"mime_type": "application/pdf"}
        )
        uploaded.append(f)
    print("   -> Waiting for files to become ACTIVE...")
    for i, f in enumerate(uploaded):
        while f.state.name == "PROCESSING":
            time.sleep(2)
            f = client_genai.files.get(name=f.name)
        if f.state.name != "ACTIVE":
            raise ValueError(f"File {f.name} failed to process. State: {f.state.name}")
        uploaded[i] = f
    return uploaded


# ============================================================================
# Async Helper Functions
# ============================================================================


async def _fetch_apps_script_configs(
    client_httpx: httpx.AsyncClient, script_url: str
) -> Dict[str, str]:
    """Fetch configuration properties from Google Apps Script asynchronously."""
    keys = ["STYLEMAP_FILE_ID", "CONTENT_SHEET_ID", "STYLEMAP_FILE_ADDRESS"]
    tasks = [
        client_httpx.get(f"{script_url}?action=getProperty&key={k}", timeout=60.0)
        for k in keys
    ]
    responses = await asyncio.gather(*tasks)
    return {
        k: (r.json().get("value") if r.status_code == 200 else None)
        for k, r in zip(keys, responses)
    }


async def _set_apps_script_property(
    client_httpx: httpx.AsyncClient, script_url: str, key: str, value: str
) -> None:
    """Set a configuration property in Google Apps Script asynchronously."""
    params = {"action": "setProperty", "key": key, "value": value}
    print(f"   -> Setting Script Property '{key}'...")
    r = await client_httpx.get(script_url, params=params, timeout=60.0)
    if r.status_code != 200:
        raise Exception(
            f"Failed to set property '{key}'. Status: {r.status_code}, Body: {r.text}"
        )


async def _generate_for_slide_async(
    slide_number: int,
    slide_df: pd.DataFrame,
    context_files: List[Any],
    client_genai: Any,
    model_id: str,
    competitor: str,
    template_view_pdf_name: str,
    max_retries: int = 3,
) -> Tuple[int, List[Dict], pd.DataFrame]:
    """Generate content for a single slide asynchronously using Gemini.
    Retries on transient 503/429 errors with exponential backoff.
    """
    prompt_text = create_slide_generation_prompt(
        slide_elements_json=slide_df.to_dict("records"),
        competitor=competitor,
        template_view_pdf_name=template_view_pdf_name,
    )
    last_exc = None
    for attempt in range(max_retries):
        try:
            response = await client_genai.aio.models.generate_content(
                model=model_id,
                contents=context_files + [prompt_text],
                config={"response_mime_type": "application/json", "temperature": 0.3},
            )
            return (slide_number, json.loads(response.text), slide_df)
        except Exception as e:
            last_exc = e
            msg = str(e)
            # Retry only on transient overload / rate-limit errors
            if "503" in msg or "429" in msg or "UNAVAILABLE" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(f"   -> Slide {slide_number} transient error (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {e}")
                await asyncio.sleep(wait)
            else:
                raise  # Non-transient error — propagate immediately
    raise last_exc


# ============================================================================
# Main Orchestrator
# ============================================================================


async def run_ai_content_population(
    pdf_bytes: bytes,
    pdf_filename: str,
    competitor: str,
    config: Config,
    slides_id: Optional[str] = None,
    excluded_slide_numbers: Optional[List[int]] = None,
    template_view_pdf_name: Optional[str] = None,
    template_name: Optional[str] = None,
    on_status: Optional[Callable[[str, float, Optional[str]], None]] = None,
) -> str:
    """
    Main async orchestrator for the entire pipeline.

    Takes a PDF (as bytes), uploads it to Gemini, fetches the style map from Apps Script,
    generates slide content, writes to Google Sheet, triggers final generation, and returns
    the final Google Slides URL.

    Args:
        pdf_bytes: Raw PDF data
        pdf_filename: Name of the PDF file
        competitor: Competitor name for content generation
        config: Config dataclass with API keys and service IDs
        slides_id: Optional Google Slides deck ID to clone. If not provided, falls back to ORIGINAL_SLIDES_ID env var
        excluded_slide_numbers: List of slide numbers to skip (default: None)
        template_view_pdf_name: Name of the template PDF for reference (default: pdf_filename)
        template_name: Name of the template used (for history logging, default: None)
        on_status: Optional callback for status updates (receives status string)

    Returns:
        str: Final Google Slides URL

    Raises:
        Exception: If any stage of the pipeline fails
    """
    if excluded_slide_numbers is None:
        excluded_slide_numbers = []
    if template_view_pdf_name is None:
        template_view_pdf_name = pdf_filename

    # Create temp file for PDF
    temp_pdf = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            temp_pdf = tmp.name

        # Initialize clients
        client_genai = genai.Client(api_key=config.gemini_api_key)
        async with httpx.AsyncClient(follow_redirects=True) as client_httpx:

            # Step 1: Run destructor to reset Apps Script properties
            if on_status:
                on_status("Setting up...", 0.05)
            print("\n[1/7] Running destructor...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=run&mode=destructor",
                timeout=120.0
            )
            if r.status_code != 200:
                raise Exception(f"Destructor failed. Status: {r.status_code}")

            # Step 1b: Set ORIGINAL_SLIDES_ID, FOLDER_DRIVE_ID, and SERVICE_ACCOUNT_EMAIL in Apps Script
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

            # Step 2: Run template generation
            if on_status:
                on_status("Generating template...", 0.10)
            print("[2/7] Generating template...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=run&mode=template",
                timeout=120.0
            )
            if r.status_code != 200:
                raise Exception(f"Template generation failed. Status: {r.status_code}")
            template_response = r.json()
            cloned_slides_url = template_response.get("url")
            print(f"   -> Cloned slides: {cloned_slides_url}")

            # Step 3: Fetch Apps Script config properties (with retries — properties may not be ready immediately)
            if on_status:
                on_status("Fetching configuration...", 0.25)
            print("[3/7] Fetching configuration...")
            stylemap_file_id = None
            content_sheet_id = None
            stylemap_file_address = None
            for attempt in range(6):
                configs = await _fetch_apps_script_configs(client_httpx, config.gas_web_app_url)
                stylemap_file_id = configs.get("STYLEMAP_FILE_ID")
                content_sheet_id = configs.get("CONTENT_SHEET_ID")
                stylemap_file_address = configs.get("STYLEMAP_FILE_ADDRESS")
                if all([stylemap_file_id, content_sheet_id, stylemap_file_address]):
                    break
                print(f"   -> Attempt {attempt + 1}/6: properties not ready, retrying in 4s...")
                await asyncio.sleep(4)

            if not content_sheet_id:
                raise Exception("Timed out waiting for CONTENT_SHEET_ID from Apps Script.")
            if not stylemap_file_id:
                raise Exception("Timed out waiting for STYLEMAP_FILE_ID from Apps Script.")
            print(f"   -> StyleMap File ID: {stylemap_file_id}")
            print(f"   -> Content Sheet ID: {content_sheet_id}")

            # Step 4: Upload PDF to Gemini and load style map
            if on_status:
                on_status("Uploading & preparing...", 0.32)
            print("[4/6] Uploading documents and loading style map...")
            uploaded_files = _upload_and_wait_for_files(client_genai, [temp_pdf])
            context_files = [
                types.Part.from_uri(
                    file_uri=f.uri,
                    mime_type="application/pdf"
                ) for f in uploaded_files
            ]
            print("   -> Files uploaded and ACTIVE.")

            # Load style map via GAS proxy (avoids service account Drive permission requirement)
            print("   -> Loading style map via GAS proxy...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=getStyleMap",
                timeout=60.0
            )
            if r.status_code != 200:
                raise Exception(f"Failed to fetch style map. Status: {r.status_code}, Body: {r.text}")
            stylemap_data = r.json()
            stylemap_df = pd.DataFrame(stylemap_data)

            # Step 5: Generate slide content asynchronously
            print("[5/6] Generating slide content (async batches)...")

            # Group by slide number and generate in batches
            slide_groups = stylemap_df.groupby("slideNumber")
            unique_slides = sorted(slide_groups.groups.keys())

            # Filter out excluded slides
            slides_to_generate = [s for s in unique_slides if s not in excluded_slide_numbers]
            total_slides = len(slides_to_generate)
            GENERATION_START = 0.45
            GENERATION_END = 0.85

            all_ai_results = {}
            completed = 0
            with tqdm(total=total_slides, desc="Slides generated") as pbar:
                for i in range(0, total_slides, config.slides_batch_size):
                    batch = slides_to_generate[i:i + config.slides_batch_size]
                    tasks = []
                    for slide_num in batch:
                        slide_df = slide_groups.get_group(slide_num)
                        task = _generate_for_slide_async(
                            slide_number=slide_num,
                            slide_df=slide_df,
                            context_files=context_files,
                            client_genai=client_genai,
                            model_id=config.model_id,
                            competitor=competitor,
                            template_view_pdf_name=template_view_pdf_name,
                        )
                        tasks.append(task)

                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for slide_num, result in zip(batch, batch_results):
                        if isinstance(result, Exception):
                            print(f"   -> Slide {slide_num} failed after retries, using original content: {result}")
                            all_ai_results[slide_num] = slide_groups.get_group(slide_num).to_dict("records")
                        else:
                            _, ai_output, _ = result
                            all_ai_results[slide_num] = ai_output
                        completed += 1
                        pbar.update(1)
                        if on_status:
                            frac = GENERATION_START + (completed / total_slides) * (GENERATION_END - GENERATION_START)
                            on_status("Generating slides...", frac, f"Slide {completed} / {total_slides}")

            print(f"   -> Generated content for {len(all_ai_results)} slides")

            # Step 6: Merge results and write to sheet via GAS proxy
            if on_status:
                on_status("Writing to sheet...", 0.87)
            print("[6/6] Writing results to Google Sheet via GAS proxy...")

            # Flatten all AI results for merging
            all_ai_data = []
            for slide_num, results in all_ai_results.items():
                if isinstance(results, list):
                    all_ai_data.extend(results)
                else:
                    all_ai_data.append(results)

            # Merge with original style map
            merged_df = _merge_ai_output_with_template(stylemap_df, all_ai_data)

            # Prepare the DataFrame exactly as GAS expects:
            # required columns: placeholderId, slideNumber, type, originalContent, contentRuns, newContent
            def _safe_json(v):
                return json.dumps(v) if isinstance(v, (list, dict)) else (v if isinstance(v, str) else "[]")

            def _safe_text(v):
                if isinstance(v, list):
                    return "".join(r.get("text", "") for r in v if isinstance(r, dict))
                return ""

            df_out = merged_df.copy()
            for col in ["placeholderId", "slideNumber", "type", "originalContent"]:
                if col not in df_out.columns:
                    df_out[col] = ""
            if "contentRuns" not in df_out.columns:
                df_out["contentRuns"] = [[] for _ in range(len(df_out))]

            df_out["newContent"] = df_out["contentRuns"].apply(_safe_text)
            df_out["contentRuns"] = df_out["contentRuns"].apply(_safe_json)
            df_out = df_out[
                ["placeholderId", "slideNumber", "type", "originalContent", "contentRuns", "newContent"]
            ].fillna("")

            rows = [df_out.columns.tolist()] + df_out.values.tolist()

            r = await client_httpx.post(
                config.gas_web_app_url,
                json={"action": "setContent", "rows": rows},
                timeout=120.0,
            )
            if r.status_code != 200:
                raise Exception(f"Sheet write failed. Status: {r.status_code}, Body: {r.text}")
            print(f"   -> Sheet write response: {r.json()}")

            # Step 7: Run final generation to populate slides
            if on_status:
                on_status("Populating slides...", 0.93)
            print("\n[7/7] Running final population...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=run&mode=slides",
                timeout=300.0
            )
            if r.status_code != 200:
                raise Exception(f"Final population failed. Status: {r.status_code}")
            final_response = r.json()

            # GAS always returns HTTP 200 — check the body for errors
            if "error" in final_response:
                raise Exception(f"GAS slides error: {final_response.get('error')} — {final_response.get('details', '')}")

            final_url = final_response.get("url")
            if not final_url:
                raise Exception(f"GAS returned no URL. Full response: {final_response}")

            if on_status:
                on_status("Complete!", 1.0)
            print(f"\n✓ Pipeline complete!")
            print(f"   -> Final URL: {final_url}")

            # Log generation to history sheet
            try:
                if config.history_sheet_id:
                    log_generation(
                        config.gdrive_credentials_path,
                        config.history_sheet_id,
                        final_url,
                        template_name=template_name,
                        target_value=competitor,
                        pdf_filename=pdf_filename,
                    )
            except Exception as e:
                print(f"   -> Warning: Could not log generation: {e}")

            return final_url

    finally:
        # Clean up temp file
        if temp_pdf and os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            print(f"   -> Cleaned up temp file: {temp_pdf}")
