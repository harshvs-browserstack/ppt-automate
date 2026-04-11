# Streamlit Cloud Setup Guide

This document explains how to configure the Document-to-Deck app on Streamlit Cloud using the Secrets management feature.

## Overview

Streamlit Cloud provides a built-in secrets manager to securely store environment variables and configuration. Instead of using a local `.env` file, you'll use a web interface to upload secrets.

## Quick Setup

### Step 1: Copy Your Secrets

Use the provided `.streamlit/secrets.toml` file as a template. It contains all the configuration variables your app needs.

**Local file location:**
```
.streamlit/secrets.toml
```

### Step 2: Access Streamlit Cloud Secrets Manager

1. Go to your app's settings in Streamlit Cloud
2. Click **Secrets** in the left sidebar
3. You'll see a text area with the label "Provide environment variables and other secrets to your app using TOML format"

### Step 3: Copy and Paste Secrets

1. Open the `.streamlit/secrets.toml` file
2. Copy the entire content
3. Paste it into the Streamlit Cloud Secrets editor
4. Click **Save**

Changes take around 1 minute to propagate to your running app.

## Secrets File Format

The `.streamlit/secrets.toml` file uses TOML format. Key points:

- **Simple values** use `KEY = "value"` format
- **Multi-line strings** use triple quotes: `"""..."""`
- **Numbers** don't need quotes: `SLIDES_BATCH_SIZE = 5`
- **Booleans** are lowercase: `POWER_USER_MODE = true`

### Example Structure

```toml
# API Keys
GEMINI_API_KEY = "your-api-key-here"
GOOGLE_API_KEY = "your-api-key-here"

# IDs
GOOGLE_SHARED_DRIVE_ID = "drive-id-here"
FOLDER_DRIVE_ID = "folder-id-here"

# Google Service Account JSON (for Streamlit Cloud)
GDRIVE_CREDENTIALS_JSON = """
{
  "type": "service_account",
  "project_id": "your-project",
  ...
}
"""
```

## What to Fill In

### Required API Keys & URLs
- `GEMINI_API_KEY` - Your Gemini API key
- `GOOGLE_API_KEY` - Your Google API key
- `GAS_WEB_APP_URL` - Your Google Apps Script web app endpoint

### Required IDs
- `FOLDER_DRIVE_ID` - Google Drive folder where generated slides are saved
- `RESEARCH_FILES_FOLDER_ID` - Google Drive folder with research PDFs
- `GOOGLE_SHARED_DRIVE_ID` - Shared Drive ID for generated slides

### Optional but Recommended
- `HISTORY_SHEET_ID` - Google Sheet for logging all generations (history tracking)
- `ORIGINAL_SLIDES_ID` - Template slide deck ID

### Template Configuration
- `GEMINI_MODEL_ID` - Gemini model to use (default: "gemini-flash-lite-latest")
- `SLIDES_BATCH_SIZE` - Number of slides to process in parallel (default: 5)
- `POWER_USER_MODE` - Enable template management UI (true/false)

### Service Account
- `GOOGLE_SERVICE_ACCOUNT_EMAIL` - Service account email (info only)
- `GDRIVE_CREDENTIALS_JSON` - **Full JSON content** from your service account JSON file

## Important: Service Account Credentials

The `.streamlit/secrets.toml` file includes the **complete JSON content** of your service account credentials as a multi-line string under `GDRIVE_CREDENTIALS_JSON`.

**DO NOT commit the `.streamlit/secrets.toml` file to your repository** - it contains sensitive credentials. It's already in `.gitignore` for local development.

### How to Get Your Service Account JSON

1. Go to Google Cloud Console
2. Navigate to **Service Accounts**
3. Find your service account
4. Go to **Keys** tab
5. Download the JSON key file
6. Open it in a text editor
7. Copy the **entire JSON content**
8. Paste it into the `GDRIVE_CREDENTIALS_JSON` field in `secrets.toml`

## Troubleshooting

### "Required environment variable 'X' is not set"
- Check that all required variables are in your secrets
- Wait 1-2 minutes for changes to propagate
- Restart your app (redeploy or refresh)

### "Invalid JSON in GDRIVE_CREDENTIALS_JSON"
- Make sure the JSON is properly formatted
- Check that newline characters are escaped (`\n` in the JSON)
- Remove any trailing commas in JSON objects
- Use a JSON validator to check for syntax errors

### App can't access Google Drive
- Verify `GDRIVE_CREDENTIALS_JSON` is set
- Check that the service account email is shared with your Drive/Shared Drive
- Verify IDs (folder, drive, sheet) are correct

## Testing After Setup

Once secrets are configured:

1. Restart your Streamlit Cloud app
2. Try uploading a PDF and generating a presentation
3. Check the Generation History page to verify logging works
4. Check your Google Shared Drive to verify slides are being shared

## Local Development

For local development, use the existing `.env` file:

```bash
# .env (local only, not committed)
GEMINI_API_KEY="your-key"
GDRIVE_CREDENTIALS_PATH="credentials.json"
...
```

The app automatically uses `.env` for local development and `secrets.toml` for Streamlit Cloud.

## Reference: All Available Configuration Variables

| Variable | Required | Local | Cloud | Purpose |
|----------|----------|-------|-------|---------|
| `GEMINI_API_KEY` | Yes | ✓ | ✓ | Gemini API authentication |
| `GEMINI_MODEL_ID` | No | ✓ | ✓ | Model selection (default: gemini-flash-lite-latest) |
| `GOOGLE_API_KEY` | Yes | ✓ | ✓ | Google API authentication |
| `GAS_WEB_APP_URL` | Yes | ✓ | ✓ | Google Apps Script endpoint |
| `GDRIVE_CREDENTIALS_PATH` | Yes (local) | ✓ | ✗ | Path to credentials JSON (local only) |
| `GDRIVE_CREDENTIALS_JSON` | Yes (cloud) | ✗ | ✓ | Full JSON credentials (Streamlit Cloud only) |
| `GOOGLE_SHARED_DRIVE_ID` | Yes | ✓ | ✓ | Shared Drive for generated slides |
| `FOLDER_DRIVE_ID` | Yes | ✓ | ✓ | Output folder in Google Drive |
| `RESEARCH_FILES_FOLDER_ID` | Yes | ✓ | ✓ | Folder containing research PDFs |
| `HISTORY_SHEET_ID` | No | ✓ | ✓ | Google Sheet for generation history |
| `ORIGINAL_SLIDES_ID` | No | ✓ | ✓ | Default template slide deck ID |
| `SLIDES_BATCH_SIZE` | No | ✓ | ✓ | Pipeline batch size (default: 5) |
| `POWER_USER_MODE` | No | ✓ | ✓ | Enable template management |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | No | ✓ | ✓ | Service account email (info only) |

## Questions?

If you encounter issues:
1. Check the app logs in Streamlit Cloud (View logs button)
2. Verify all IDs and keys are correct
3. Ensure the service account has proper permissions
4. Check that secrets have propagated (wait 1-2 minutes)
