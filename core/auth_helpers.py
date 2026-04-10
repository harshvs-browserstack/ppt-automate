"""
Authentication helpers for Google APIs using service account credentials.
Replaces the google.colab auth flow from the original notebook.
"""
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_credentials(credentials_path: str):
    """Return service account credentials with Drive + Sheets scopes."""
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


def get_gspread_client(credentials_path: str) -> gspread.Client:
    """Return an authenticated gspread client."""
    creds = get_credentials(credentials_path)
    return gspread.authorize(creds)
