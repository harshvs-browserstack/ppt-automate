import os
import pytest
from unittest.mock import patch, MagicMock


def test_config_loads_required_vars():
    """Test that Config loads and validates all required environment variables."""
    env = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL_ID": "gemini-2.5-flash",
        "GAS_WEB_APP_URL": "https://script.google.com/macros/s/ABC/exec",
        "GDRIVE_CREDENTIALS_PATH": "creds.json",
        "ORIGINAL_SLIDES_ID": "1abc123",
        "FOLDER_DRIVE_ID": "1folder456",
        "SLIDES_BATCH_SIZE": "5",
        "RESEARCH_FILES_FOLDER_ID": "1research789",
        "POWER_USER_MODE": "true",
    }
    with patch("dotenv.load_dotenv"):
        with patch.dict(os.environ, env, clear=True):
            from importlib import reload
            import core.config as config_module
            reload(config_module)
            cfg = config_module.get_config()
            assert cfg.gemini_api_key == "test-key"
            assert cfg.model_id == "gemini-2.5-flash"
            assert cfg.gas_web_app_url == "https://script.google.com/macros/s/ABC/exec"
            assert cfg.gdrive_credentials_path == "creds.json"
            assert cfg.original_slides_id == "1abc123"
            assert cfg.folder_drive_id == "1folder456"
            assert cfg.slides_batch_size == 5
            assert isinstance(cfg.slides_batch_size, int)
            assert cfg.power_user_mode is True
            assert cfg.research_files_folder_id == "1research789"


def test_config_raises_on_missing_required_var():
    """Test that Config raises EnvironmentError if required var is missing."""
    with patch("dotenv.load_dotenv"):
        with patch.dict(os.environ, {}, clear=True):
            from importlib import reload
            import core.config as config_module
            reload(config_module)
            with pytest.raises(EnvironmentError, match="Required environment variable"):
                config_module.get_config()


def test_config_optional_vars_have_defaults():
    """Test that optional variables use default values when not set."""
    env = {
        "GEMINI_API_KEY": "test-key",
        "GAS_WEB_APP_URL": "https://script.google.com/macros/s/ABC/exec",
        "GDRIVE_CREDENTIALS_PATH": "creds.json",
        "FOLDER_DRIVE_ID": "1folder456",
        "RESEARCH_FILES_FOLDER_ID": "1research789",
    }
    with patch("dotenv.load_dotenv"):
        with patch.dict(os.environ, env, clear=True):
            from importlib import reload
            import core.config as config_module
            reload(config_module)
            cfg = config_module.get_config()
            assert cfg.original_slides_id == ""
            assert cfg.power_user_mode is False
            assert cfg.model_id == "gemini-2.5-flash"
            assert cfg.slides_batch_size == 5
