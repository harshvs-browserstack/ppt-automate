"""
Configuration module for Document-to-Deck application.
Loads environment variables and provides validated configuration.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv


# Load .env file on module import
load_dotenv()


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


def get_config() -> Config:
    """
    Load and validate configuration from environment variables.

    Required variables:
    - GEMINI_API_KEY
    - GAS_WEB_APP_URL
    - GDRIVE_CREDENTIALS_PATH
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

    return Config(
        gemini_api_key=require("GEMINI_API_KEY"),
        model_id=os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash"),
        gas_web_app_url=require("GAS_WEB_APP_URL"),
        gdrive_credentials_path=require("GDRIVE_CREDENTIALS_PATH"),
        folder_drive_id=require("FOLDER_DRIVE_ID"),
        slides_batch_size=int(os.getenv("SLIDES_BATCH_SIZE", "5")),
        research_files_folder_id=require("RESEARCH_FILES_FOLDER_ID"),
        original_slides_id=os.getenv("ORIGINAL_SLIDES_ID", ""),
        power_user_mode=os.getenv("POWER_USER_MODE", "").lower() == "true",
        google_service_account_email=os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL", ""),
        history_sheet_id=os.getenv("HISTORY_SHEET_ID", ""),
    )
