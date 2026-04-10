import pandas as pd
import json
import pytest
from core.formatter_pipeline import (
    contains_url,
    extract_id_from_url,
    _merge_ai_output_with_template,
)


def test_contains_url_true():
    assert contains_url("https://docs.google.com/presentation/d/abc/edit") is True


def test_contains_url_false():
    assert contains_url("just a plain string") is False


def test_extract_id_from_presentation_url():
    url = "https://docs.google.com/presentation/d/1Tk3hh6KvoyroIVAn90TfGPiYylMgKhbLqu6iEBOtS8E/edit"
    assert extract_id_from_url(url) == "1Tk3hh6KvoyroIVAn90TfGPiYylMgKhbLqu6iEBOtS8E"


def test_extract_id_returns_passthrough_if_not_url():
    assert extract_id_from_url("1Tk3hh6abc") == "1Tk3hh6abc"


def test_merge_ai_output_updates_matching_rows():
    original = pd.DataFrame([
        {"placeholderId": "p1", "slideNumber": 1, "type": "text",
         "originalContent": "Old", "contentRuns": [{"text": "Old"}]},
        {"placeholderId": "p2", "slideNumber": 1, "type": "text",
         "originalContent": "Keep", "contentRuns": [{"text": "Keep"}]},
    ])
    ai_data = [{"placeholderId": "p1", "contentRuns": [{"text": "New AI content"}]}]
    result = _merge_ai_output_with_template(original, ai_data)
    assert result.loc[result["placeholderId"] == "p1", "contentRuns"].iloc[0] == [{"text": "New AI content"}]
    assert result.loc[result["placeholderId"] == "p2", "contentRuns"].iloc[0] == [{"text": "Keep"}]


def test_merge_ai_output_returns_original_if_empty():
    original = pd.DataFrame([
        {"placeholderId": "p1", "slideNumber": 1, "type": "text",
         "originalContent": "Old", "contentRuns": [{"text": "Old"}]},
    ])
    result = _merge_ai_output_with_template(original, [])
    pd.testing.assert_frame_equal(result, original)


def test_merge_ai_output_last_wins_on_duplicate_placeholder():
    original = pd.DataFrame([
        {"placeholderId": "p1", "slideNumber": 1, "type": "text",
         "originalContent": "Old", "contentRuns": [{"text": "Old"}]},
    ])
    ai_data = [
        {"placeholderId": "p1", "contentRuns": [{"text": "First"}]},
        {"placeholderId": "p1", "contentRuns": [{"text": "Last"}]},
    ]
    result = _merge_ai_output_with_template(original, ai_data)
    assert result.loc[result["placeholderId"] == "p1", "contentRuns"].iloc[0] == [{"text": "Last"}]
