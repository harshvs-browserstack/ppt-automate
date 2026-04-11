"""
Generation history tracking.
Logs all slide generations to a Google Sheet for audit trail.
"""
from datetime import datetime
from typing import Optional, Callable
from core.auth_helpers import get_sheets_service
import logging

logger = logging.getLogger(__name__)


def log_generation(
    sheets_service_or_creds_path,
    history_sheet_id: str,
    slide_url: str,
    template_name: Optional[str] = None,
    target_value: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    on_logged: Optional[Callable] = None,
) -> None:
    """
    Log a slide generation to the history sheet.

    Args:
        sheets_service_or_creds_path: Either a Google Sheets service object or path to credentials JSON
        history_sheet_id: The Google Sheet ID to log to
        slide_url: The URL of the generated Google Slide
        template_name: Name of the template used (optional)
        target_value: The target variable value (optional)
        pdf_filename: Name of the uploaded PDF (optional)
        on_logged: Optional callback function called after successful log (takes no args)
    """
    if not history_sheet_id or history_sheet_id == "-":
        logger.debug("History sheet not configured, skipping generation log.")
        return

    try:
        # Get sheets service if we received credentials path
        if isinstance(sheets_service_or_creds_path, str):
            service = get_sheets_service(sheets_service_or_creds_path)
        else:
            service = sheets_service_or_creds_path

        # Extract slide ID from URL
        slide_id = ""
        if "/d/" in slide_url:
            slide_id = slide_url.split("/d/")[1].split("/")[0]

        # Get or create the Generations sheet
        spreadsheet = service.spreadsheets().get(spreadsheetId=history_sheet_id).execute()
        sheets = spreadsheet.get("sheets", [])
        generations_sheet = next(
            (s for s in sheets if s["properties"]["title"] == "Generations"), None
        )

        if not generations_sheet:
            # Create Generations sheet with headers
            request = {
                "addSheet": {
                    "properties": {
                        "title": "Generations",
                        "gridProperties": {"rowCount": 1, "columnCount": 6},
                    }
                }
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=history_sheet_id, body={"requests": [request]}
            ).execute()

            # Add headers
            header_row = [
                [
                    "Timestamp",
                    "Template",
                    "Target Value",
                    "PDF Filename",
                    "Slide URL",
                    "Slide ID",
                ]
            ]
            service.spreadsheets().values().update(
                spreadsheetId=history_sheet_id,
                range="Generations!A1:F1",
                valueInputOption="RAW",
                body={"values": header_row},
            ).execute()

        # Append generation record
        timestamp = datetime.now().isoformat()
        row = [
            [
                timestamp,
                template_name or "N/A",
                target_value or "N/A",
                pdf_filename or "N/A",
                slide_url,
                slide_id,
            ]
        ]

        service.spreadsheets().values().append(
            spreadsheetId=history_sheet_id,
            range="Generations!A:F",
            valueInputOption="RAW",
            body={"values": row},
        ).execute()

        logger.info(f"Generation logged: {slide_id}")

        if on_logged:
            on_logged()

    except Exception as e:
        logger.warning(f"Could not log generation to history: {e}")
