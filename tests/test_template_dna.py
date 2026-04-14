import io
import json
import pytest
from unittest.mock import MagicMock, patch, call
from core.template_registry import TemplateDNA


def _make_config():
    cfg = MagicMock()
    cfg.gemini_api_key = "key"
    cfg.pro_model_id = "gemini-1.5-pro"
    cfg.gdrive_credentials_path = "/fake/creds.json"
    return cfg


def test_export_slides_as_pdf_calls_drive_export():
    from core.template_dna import export_slides_as_pdf

    pdf_bytes = b"%PDF-fake"

    mock_service = MagicMock()
    mock_request = MagicMock()
    mock_service.files.return_value.export_media.return_value = mock_request

    # Simulate MediaIoBaseDownload: write bytes to buf and return done=True
    class FakeDownloader:
        def __init__(self, buf, request):
            buf.write(pdf_bytes)

        def next_chunk(self):
            return MagicMock(), True

    with patch("core.template_dna.build", return_value=mock_service), \
         patch("core.template_dna.get_credentials"), \
         patch("core.template_dna.MediaIoBaseDownload", FakeDownloader):
        result = export_slides_as_pdf("slides123", "/fake/creds.json")

    mock_service.files.return_value.export_media.assert_called_once_with(
        fileId="slides123", mimeType="application/pdf"
    )
    assert result == pdf_bytes


def test_generate_template_dna_returns_dataclass():
    from core.template_dna import generate_template_dna

    dna_json = json.dumps({
        "purpose": "Competitive battlecard",
        "dimensions": ["market positioning", "pricing"],
        "tone": "professional",
        "source_guidance": "competitor research",
    })

    processing_file = MagicMock()
    processing_file.state.name = "PROCESSING"
    processing_file.name = "files/abc123"
    processing_file.uri = "https://generativelanguage.googleapis.com/files/abc123"

    active_file = MagicMock()
    active_file.state.name = "ACTIVE"
    active_file.uri = processing_file.uri
    active_file.name = processing_file.name

    mock_client = MagicMock()
    mock_client.files.upload.return_value = processing_file
    mock_client.files.get.return_value = active_file

    mock_response = MagicMock()
    mock_response.text = dna_json
    mock_client.models.generate_content.return_value = mock_response

    config = _make_config()

    with patch("core.template_dna.export_slides_as_pdf", return_value=b"%PDF"), \
         patch("core.template_dna.genai.Client", return_value=mock_client), \
         patch("core.template_dna.time.sleep"):
        result = generate_template_dna("slides123", config)

    assert isinstance(result, TemplateDNA)
    assert result.purpose == "Competitive battlecard"
    assert result.dimensions == ["market positioning", "pricing"]
    assert result.tone == "professional"
    assert result.source_guidance == "competitor research"
    mock_client.files.delete.assert_called_once()


def test_generate_template_dna_raises_on_missing_keys():
    from core.template_dna import generate_template_dna

    incomplete_json = json.dumps({"purpose": "something"})  # missing dimensions, tone, source_guidance

    active_file = MagicMock()
    active_file.state.name = "ACTIVE"
    active_file.name = "files/abc"
    active_file.uri = "https://example.com/files/abc"

    mock_client = MagicMock()
    mock_client.files.upload.return_value = active_file
    mock_client.files.get.return_value = active_file
    mock_client.models.generate_content.return_value = MagicMock(text=incomplete_json)

    with patch("core.template_dna.export_slides_as_pdf", return_value=b"%PDF"), \
         patch("core.template_dna.genai.Client", return_value=mock_client), \
         patch("core.template_dna.time.sleep"):
        with pytest.raises(ValueError, match="missing keys"):
            generate_template_dna("slides123", _make_config())
