"""
Template DNA generation.
Exports a Google Slides deck as PDF, sends it to Gemini Pro,
and returns a structured TemplateDNA describing the presentation's purpose,
information needs, and tone. Generated once per template at creation time.
"""
import io
import json
import os
import tempfile
import time
from typing import TYPE_CHECKING

from google import genai
from google.genai import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from core.auth_helpers import get_credentials
from core.template_registry import TemplateDNA

if TYPE_CHECKING:
    from core.config import Config


_DNA_PROMPT = """
Analyze this presentation template and return a JSON object with exactly these keys:
- "purpose": one sentence describing the overall purpose and theme of this presentation
- "dimensions": a list of 4 to 7 strings, each naming a distinct information dimension
  the presentation needs (e.g. "market positioning", "pricing models", "customer proof points")
- "tone": a brief description of the style (e.g. "professional, persuasive, data-backed")
- "source_guidance": what kind of source material would best populate this presentation

Return only valid JSON. No markdown fences. No explanation outside the JSON object.
"""


def export_slides_as_pdf(slides_id: str, credentials_path: str) -> bytes:
    """
    Export a Google Slides deck as a PDF using the Drive API.

    Args:
        slides_id: The Google Slides file ID.
        credentials_path: Path to service account JSON credentials.

    Returns:
        PDF content as bytes.
    """
    creds = get_credentials(credentials_path)
    service = build("drive", "v3", credentials=creds)
    request = service.files().export_media(fileId=slides_id, mimeType="application/pdf")
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def generate_template_dna(slides_id: str, config: "Config") -> TemplateDNA:
    """
    Generate Template DNA by analysing the slide deck's PDF export with Gemini Pro.

    Exports the deck as PDF, uploads to the Gemini File API, calls Gemini Pro
    with a structured analysis prompt, and parses the JSON response.

    Args:
        slides_id: The Google Slides file ID to analyse.
        config: Application config (needs gemini_api_key, pro_model_id, gdrive_credentials_path).

    Returns:
        TemplateDNA dataclass populated from Gemini's response.

    Raises:
        ValueError: If Gemini returns invalid JSON or missing required keys.
    """
    pdf_bytes = export_slides_as_pdf(slides_id, config.gdrive_credentials_path)

    tmp_path = None
    uploaded_file = None
    client = genai.Client(api_key=config.gemini_api_key)

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name

        uploaded_file = client.files.upload(
            file=tmp_path,
            config={"mime_type": "application/pdf"},
        )

        # Wait for Gemini to finish processing the uploaded file
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)

        response = client.models.generate_content(
            model=config.pro_model_id,
            contents=[
                types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type="application/pdf",
                ),
                _DNA_PROMPT,
            ],
            config={"response_mime_type": "application/json", "temperature": 0.1},
        )

        data = json.loads(response.text)
        required = {"purpose", "dimensions", "tone", "source_guidance"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Gemini DNA response missing keys: {missing}")

        return TemplateDNA(
            purpose=data["purpose"],
            dimensions=data["dimensions"],
            tone=data["tone"],
            source_guidance=data["source_guidance"],
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass
