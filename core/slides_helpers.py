"""
Google Slides API helpers.
Fetches slide structure (titles) from a presentation for template setup.
"""
from typing import List, Dict
from core.auth_helpers import get_slides_service


def fetch_slide_titles(credentials_path: str, slides_id: str) -> List[Dict]:
    """
    Fetch slide titles from a Google Slides presentation.

    Args:
        credentials_path: Path to service account JSON credentials
        slides_id: Google Slides presentation ID (not URL)

    Returns:
        List of {"number": int, "title": str} dicts, one per slide
    """
    service = get_slides_service(credentials_path)
    presentation = (
        service.presentations()
        .get(presentationId=slides_id, fields="slides")
        .execute()
    )
    return extract_slide_titles_from_presentation(presentation)


def extract_slide_titles_from_presentation(presentation: Dict) -> List[Dict]:
    """
    Parse a Slides API presentation response and return slide titles.
    Falls back to "Slide N" when a slide has no TITLE placeholder.

    Args:
        presentation: Raw dict from Slides API presentations.get()

    Returns:
        List of {"number": int, "title": str} dicts
    """
    results = []
    for i, slide in enumerate(presentation.get("slides", []), start=1):
        title = _extract_title_from_slide(slide) or f"Slide {i}"
        results.append({"number": i, "title": title})
    return results


def _extract_title_from_slide(slide: Dict) -> str:
    """Return the text of the TITLE placeholder, or empty string if not found."""
    for element in slide.get("pageElements", []):
        shape = element.get("shape", {})
        placeholder = shape.get("placeholder", {})
        if placeholder.get("type") == "TITLE":
            text_content = shape.get("text", {})
            parts = []
            for te in text_content.get("textElements", []):
                if "textRun" in te:
                    parts.append(te["textRun"]["content"])
            return "".join(parts).strip()
    return ""
