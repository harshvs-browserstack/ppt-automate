"""
Configuration module for Document-to-Deck application.
Loads environment variables and provides validated configuration.
Supports both local .env files and Streamlit Cloud secrets.
"""
import os
import json
import tempfile
from dataclasses import dataclass
from dotenv import load_dotenv


# Load .env file on module import (for local development)
load_dotenv()


def _create_credentials_file_from_json_string(json_string: str) -> str:
    """
    Create a temporary credentials file from a JSON string.
    Used for Streamlit Cloud deployments where credentials come as a secret string.

    Args:
        json_string: JSON credentials as a string

    Returns:
        Path to the temporary credentials file
    """
    try:
        # Parse to validate it's valid JSON
        credentials_dict = json.loads(json_string)

        # Create a temporary file that persists for the session
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            prefix='credentials_'
        )
        json.dump(credentials_dict, temp_file)
        temp_file.close()

        return temp_file.name
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in GDRIVE_CREDENTIALS_JSON: {e}")


@dataclass
class Config:
    """Configuration dataclass for the application.

    Note: original_slides_id is optional (defaults to empty string if not provided).
    """
    gemini_api_key: str
    model_id: str
    gas_web_app_url: str
    gdrive_credentials_path: str
    folder_drive_id: str
    slides_batch_size: int
    research_files_folder_id: str
    original_slides_id: str = ""
    power_user_mode: bool = False
    google_service_account_email: str = ""
    history_sheet_id: str = ""  # Optional: Google Sheet to log all generations
    pro_model_id: str = "gemini-1.5-pro"
    confluence_base_url: str = ""
    confluence_api_token: str = ""
    confluence_user_email: str = ""


def get_config() -> Config:
    """
    Load and validate configuration from environment variables.

    Supports both local .env files and Streamlit Cloud secrets.

    Required variables:
    - GEMINI_API_KEY
    - GAS_WEB_APP_URL
    - Either GDRIVE_CREDENTIALS_PATH (local) or GDRIVE_CREDENTIALS_JSON (Streamlit Cloud)
    - FOLDER_DRIVE_ID
    - RESEARCH_FILES_FOLDER_ID

    Optional variables (with defaults):
    - GEMINI_MODEL_ID (default: "gemini-2.5-flash")
    - SLIDES_BATCH_SIZE (default: 5)
    - ORIGINAL_SLIDES_ID (default: "")
    - POWER_USER_MODE (default: false)

    Returns:
        Config: Validated configuration dataclass

    Raises:
        EnvironmentError: If required variable is missing
    """
    def require(key: str) -> str:
        """Get required env var or raise EnvironmentError."""
        val = os.getenv(key)
        if not val:
            raise EnvironmentError(f"Required environment variable '{key}' is not set.")
        return val

    # Handle credentials: try GDRIVE_CREDENTIALS_PATH first (local), then GDRIVE_CREDENTIALS_JSON (Streamlit Cloud)
    credentials_path = os.getenv("GDRIVE_CREDENTIALS_PATH")
    if not credentials_path:
        credentials_json = os.getenv("GDRIVE_CREDENTIALS_JSON")
        if credentials_json:
            # We're running on Streamlit Cloud or similar, create temp file from JSON
            credentials_path = _create_credentials_file_from_json_string(credentials_json)
        else:
            raise EnvironmentError(
                "Either GDRIVE_CREDENTIALS_PATH or GDRIVE_CREDENTIALS_JSON must be set."
            )

    return Config(
        gemini_api_key=require("GEMINI_API_KEY"),
        model_id=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"),
        gas_web_app_url=require("GAS_WEB_APP_URL"),
        gdrive_credentials_path=credentials_path,
        folder_drive_id=require("FOLDER_DRIVE_ID"),
        slides_batch_size=int(os.getenv("SLIDES_BATCH_SIZE", "5")),
        research_files_folder_id=require("RESEARCH_FILES_FOLDER_ID"),
        original_slides_id=os.getenv("ORIGINAL_SLIDES_ID", ""),
        power_user_mode=os.getenv("POWER_USER_MODE", "").lower() == "true",
        google_service_account_email=os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", ""),
        history_sheet_id=os.getenv("HISTORY_SHEET_ID", ""),
        pro_model_id=os.getenv("GEMINI_PRO_MODEL_ID", "gemini-1.5-pro"),
        confluence_base_url=os.getenv("CONFLUENCE_BASE_URL", ""),
        confluence_api_token=os.getenv("CONFLUENCE_API_TOKEN", ""),
        confluence_user_email=os.getenv("CONFLUENCE_USER_EMAIL", ""),
    )
