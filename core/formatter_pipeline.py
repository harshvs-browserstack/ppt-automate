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
        client_httpx.get(f"{script_url}?action=getProperty&key={k}", timeout=30.0)
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
    r = await client_httpx.get(script_url, params=params, timeout=30.0)
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
) -> Tuple[int, List[Dict], pd.DataFrame]:
    """Generate content for a single slide asynchronously using Gemini."""
    prompt_text = create_slide_generation_prompt(
        slide_elements_json=slide_df.to_dict("records"),
        competitor=competitor,
        template_view_pdf_name=template_view_pdf_name,
    )
    response = await client_genai.aio.models.generate_content(
        model=model_id,
        contents=context_files + [prompt_text],
        config={"response_mime_type": "application/json", "temperature": 0.3},
    )
    return (slide_number, json.loads(response.text), slide_df)


# ============================================================================
# Main Orchestrator
# ============================================================================


async def run_ai_content_population(
    pdf_bytes: bytes,
    pdf_filename: str,
    competitor: str,
    config: Config,
    excluded_slide_numbers: Optional[List[int]] = None,
    template_view_pdf_name: Optional[str] = None,
    on_status: Optional[Callable] = None,
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
        excluded_slide_numbers: List of slide numbers to skip (default: None)
        template_view_pdf_name: Name of the template PDF for reference (default: pdf_filename)
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
        async with httpx.AsyncClient() as client_httpx:

            # Step 1: Run destructor to reset Apps Script properties
            if on_status:
                on_status("Running destructor...")
            print("\n[1/6] Running destructor...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=run&mode=destructor",
                timeout=60.0
            )
            if r.status_code != 200:
                raise Exception(f"Destructor failed. Status: {r.status_code}")

            # Step 2: Run template generation
            if on_status:
                on_status("Generating template...")
            print("[2/6] Generating template...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=run&mode=template",
                timeout=60.0
            )
            if r.status_code != 200:
                raise Exception(f"Template generation failed. Status: {r.status_code}")
            template_response = r.json()
            cloned_slides_url = template_response.get("url")
            print(f"   -> Cloned slides: {cloned_slides_url}")

            # Step 3: Fetch Apps Script config properties
            if on_status:
                on_status("Fetching configuration...")
            print("[3/6] Fetching configuration...")
            configs = await _fetch_apps_script_configs(client_httpx, config.gas_web_app_url)
            stylemap_file_id = configs.get("STYLEMAP_FILE_ID")
            content_sheet_id = configs.get("CONTENT_SHEET_ID")
            stylemap_file_address = configs.get("STYLEMAP_FILE_ADDRESS")

            if not all([stylemap_file_id, content_sheet_id, stylemap_file_address]):
                raise Exception(f"Missing config from Apps Script: {configs}")
            print(f"   -> StyleMap File ID: {stylemap_file_id}")
            print(f"   -> Content Sheet ID: {content_sheet_id}")

            # Step 4: Upload PDF to Gemini and load style map
            if on_status:
                on_status("Uploading documents...")
            print("[4/6] Uploading documents and loading style map...")
            uploaded_files = _upload_and_wait_for_files(client_genai, [temp_pdf])
            context_files = [
                types.Part.from_uri(
                    uri=f.uri,
                    mime_type="application/pdf"
                ) for f in uploaded_files
            ]
            print("   -> Files uploaded and ACTIVE.")

            # Load style map from Drive
            print("   -> Loading style map...")
            stylemap_data = _read_json_from_drive(stylemap_file_id, config.gdrive_credentials_path)
            stylemap_df = pd.DataFrame(stylemap_data)

            # Step 5: Generate slide content asynchronously
            if on_status:
                on_status("Generating content...")
            print("[5/6] Generating slide content (async batches)...")

            # Group by slide number and generate in batches
            slide_groups = stylemap_df.groupby("slideNumber")
            unique_slides = sorted(slide_groups.groups.keys())

            # Filter out excluded slides
            slides_to_generate = [s for s in unique_slides if s not in excluded_slide_numbers]

            all_ai_results = {}
            with tqdm(total=len(slides_to_generate), desc="Slides generated") as pbar:
                for i in range(0, len(slides_to_generate), config.slides_batch_size):
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

                    batch_results = await asyncio.gather(*tasks)
                    for slide_num, ai_output, _ in batch_results:
                        all_ai_results[slide_num] = ai_output
                        pbar.update(1)

            print(f"   -> Generated content for {len(all_ai_results)} slides")

            # Step 6: Merge results and write to sheet
            if on_status:
                on_status("Writing to sheet...")
            print("[6/6] Writing results to Google Sheet...")

            # Flatten all AI results for merging
            all_ai_data = []
            for slide_num, results in all_ai_results.items():
                if isinstance(results, list):
                    all_ai_data.extend(results)
                else:
                    all_ai_data.append(results)

            # Merge with original style map
            merged_df = _merge_ai_output_with_template(stylemap_df, all_ai_data)

            # Write to the content sheet
            _write_dataframe_to_sheet(
                sheet_id=content_sheet_id,
                range_name=stylemap_file_address,
                df=merged_df,
                credentials_path=config.gdrive_credentials_path
            )

            # Step 7: Run final generation to populate slides
            if on_status:
                on_status("Populating slides...")
            print("\n[7/7] Running final population...")
            r = await client_httpx.get(
                f"{config.gas_web_app_url}?action=run&mode=slides",
                timeout=120.0
            )
            if r.status_code != 200:
                raise Exception(f"Final population failed. Status: {r.status_code}")
            final_response = r.json()
            final_url = final_response.get("url")

            if on_status:
                on_status("Complete!")
            print(f"\n✓ Pipeline complete!")
            print(f"   -> Final URL: {final_url}")

            return final_url

    finally:
        # Clean up temp file
        if temp_pdf and os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            print(f"   -> Cleaned up temp file: {temp_pdf}")
