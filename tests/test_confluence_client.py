import pytest
from unittest.mock import MagicMock, patch
from core.confluence_client import ConfluenceClient, _extract_text


def _make_client():
    return ConfluenceClient(
        base_url="https://mysite.atlassian.net",
        email="user@example.com",
        token="mytoken",
    )


def test_auth_header_is_basic():
    client = _make_client()
    import base64
    expected = base64.b64encode(b"user@example.com:mytoken").decode()
    assert client._headers["Authorization"] == f"Basic {expected}"


def test_list_spaces_returns_key_name_pairs():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"key": "CI", "name": "Competitive Intel"},
            {"key": "PROD", "name": "Product Docs"},
        ]
    }
    with patch.object(client._http, "get", return_value=mock_response) as mock_get:
        spaces = client.list_spaces()

    assert spaces == [
        {"key": "CI", "name": "Competitive Intel"},
        {"key": "PROD", "name": "Product Docs"},
    ]
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "/wiki/api/v2/spaces" in call_url


def test_search_returns_page_list():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [{
            "id": "123",
            "title": "Sauce Labs Analysis",
            "space": {"name": "Competitive Intel", "key": "CI"},
            "_links": {"webui": "/spaces/CI/pages/123"},
        }]
    }
    with patch.object(client._http, "get", return_value=mock_response):
        results = client.search('space IN ("CI") AND text ~ "Sauce Labs"', limit=5)

    assert len(results) == 1
    assert results[0]["id"] == "123"
    assert results[0]["title"] == "Sauce Labs Analysis"
    assert results[0]["url"] == "https://mysite.atlassian.net/wiki/spaces/CI/pages/123"
    assert results[0]["space"] == "Competitive Intel"


def test_get_page_content_extracts_text():
    client = _make_client()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "id": "123",
        "title": "Sauce Labs Analysis",
        "_links": {"webui": "/spaces/CI/pages/123"},
        "body": {
            "storage": {
                "value": "<p>Market share is <strong>23%</strong></p><ac:macro ac:name='note'/>",
            }
        },
        "version": {"when": "2026-03-20T10:00:00Z", "by": {"displayName": "Alice"}},
    }
    with patch.object(client._http, "get", return_value=mock_response):
        result = client.get_page_content("123")

    assert result["title"] == "Sauce Labs Analysis"
    assert "Market share is" in result["content"]
    assert "23%" in result["content"]
    assert "ac:macro" not in result["content"]
    assert result["last_updated"] == "2026-03-20T10:00:00Z"
    assert result["author"] == "Alice"


def test_extract_text_strips_macros():
    xml = """
    <p>Hello <strong>world</strong></p>
    <ac:structured-macro ac:name="note"><ac:parameter>ignored</ac:parameter></ac:structured-macro>
    <ul><li>Item one</li><li>Item two</li></ul>
    """
    text = _extract_text(xml)
    assert "Hello" in text
    assert "world" in text
    assert "Item one" in text
    assert "ac:structured-macro" not in text
    assert "ignored" not in text
