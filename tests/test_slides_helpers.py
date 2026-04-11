from unittest.mock import MagicMock, patch
from core.slides_helpers import extract_slide_titles_from_presentation


def _make_presentation(slides_data):
    """Build a mock Slides API presentation response."""
    slides = []
    for i, title in enumerate(slides_data, start=1):
        if title is None:
            # Slide with no title placeholder
            page = {"pageElements": []}
        else:
            page = {
                "pageElements": [
                    {
                        "shape": {
                            "placeholder": {"type": "TITLE"},
                            "text": {
                                "textElements": [
                                    {"textRun": {"content": title}}
                                ]
                            },
                        }
                    }
                ]
            }
        slides.append(page)
    return {"slides": slides}


def test_extracts_titles_in_order():
    presentation = _make_presentation(["Cover", "Overview", "Pricing"])
    result = extract_slide_titles_from_presentation(presentation)
    assert result == [
        {"number": 1, "title": "Cover"},
        {"number": 2, "title": "Overview"},
        {"number": 3, "title": "Pricing"},
    ]


def test_falls_back_to_slide_n_when_no_title():
    presentation = _make_presentation(["Cover", None, "Pricing"])
    result = extract_slide_titles_from_presentation(presentation)
    assert result[1] == {"number": 2, "title": "Slide 2"}


def test_empty_presentation_returns_empty_list():
    result = extract_slide_titles_from_presentation({"slides": []})
    assert result == []


def test_strips_trailing_newline_from_title():
    presentation = _make_presentation(["Cover Slide\n"])
    result = extract_slide_titles_from_presentation(presentation)
    assert result[0]["title"] == "Cover Slide"
