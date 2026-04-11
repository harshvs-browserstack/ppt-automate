import pytest
from core.template_registry import Template
from core.suggest_template import parse_suggestion_response, SuggestionResult


TEMPLATES = [
    Template(id="t1", name="Competitor Battlecard", slides_id="s1",
             variable_label="Competitor Name", variable_hint="e.g. Sauce Labs", slides=[]),
    Template(id="t2", name="Industry Pitch Deck", slides_id="s2",
             variable_label="Client Industry", variable_hint="e.g. Fintech", slides=[]),
]


def test_parse_valid_response():
    raw = '{"template_id": "t1", "reason": "Looks like a comparison.", "extracted_target": "Sauce Labs"}'
    result = parse_suggestion_response(raw, TEMPLATES)
    assert result.template_id == "t1"
    assert result.reason == "Looks like a comparison."
    assert result.extracted_target == "Sauce Labs"


def test_parse_null_extracted_target():
    raw = '{"template_id": "t2", "reason": "Looks like a pitch.", "extracted_target": null}'
    result = parse_suggestion_response(raw, TEMPLATES)
    assert result.extracted_target is None


def test_parse_unknown_template_id_falls_back_to_first():
    raw = '{"template_id": "unknown", "reason": "Not sure.", "extracted_target": null}'
    result = parse_suggestion_response(raw, TEMPLATES)
    assert result.template_id == "t1"


def test_parse_malformed_json_falls_back_to_first():
    result = parse_suggestion_response("this is not json", TEMPLATES)
    assert result.template_id == "t1"
    assert "could not" in result.reason.lower()


def test_parse_empty_templates_list_raises():
    with pytest.raises(ValueError, match="No templates"):
        parse_suggestion_response('{"template_id": "t1", "reason": "x", "extracted_target": null}', [])
