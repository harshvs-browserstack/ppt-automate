"""Template registry system with JSON persistence for Document-to-Deck."""

import json
import pathlib
import secrets
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class SlideDefault:
    """Represents a slide in a template with its default configuration."""
    number: int
    title: str
    enabled: bool


@dataclass
class Template:
    """Represents a reusable presentation template."""
    id: str
    name: str
    slides_id: str
    variable_label: str
    variable_hint: str
    slides: List[SlideDefault]


REGISTRY_PATH = pathlib.Path(__file__).parent.parent / "templates.json"


def load_templates(registry_path: str) -> List[Template]:
    """
    Load templates from a JSON registry file.

    Returns an empty list if the file does not exist.

    Args:
        registry_path: Path to the JSON registry file.

    Returns:
        List of Template objects, or empty list if file missing.
    """
    path = pathlib.Path(registry_path)
    if not path.exists():
        return []

    with open(path, "r") as f:
        data = json.load(f)

    templates = []
    for item in data:
        slides = [SlideDefault(**slide) for slide in item["slides"]]
        template = Template(
            id=item["id"],
            name=item["name"],
            slides_id=item["slides_id"],
            variable_label=item["variable_label"],
            variable_hint=item["variable_hint"],
            slides=slides,
        )
        templates.append(template)

    return templates


def save_templates(templates: List[Template], registry_path: str) -> None:
    """
    Save templates to a JSON registry file.

    Args:
        templates: List of Template objects to persist.
        registry_path: Path to the JSON registry file.
    """
    path = pathlib.Path(registry_path)

    data = []
    for template in templates:
        item = {
            "id": template.id,
            "name": template.name,
            "slides_id": template.slides_id,
            "variable_label": template.variable_label,
            "variable_hint": template.variable_hint,
            "slides": [asdict(slide) for slide in template.slides],
        }
        data.append(item)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_template_by_id(templates: List[Template], template_id: str) -> Optional[Template]:
    """
    Find a template by its ID.

    Args:
        templates: List of templates to search.
        template_id: The ID to search for.

    Returns:
        The Template object if found, None otherwise.
    """
    for template in templates:
        if template.id == template_id:
            return template
    return None


def get_excluded_slide_numbers(template: Template) -> List[int]:
    """
    Get the slide numbers that are disabled in a template.

    Args:
        template: The template to inspect.

    Returns:
        List of slide numbers where enabled=False, sorted in ascending order.
    """
    return [slide.number for slide in template.slides if not slide.enabled]


def new_template_id() -> str:
    """
    Generate a unique 8-character template ID.

    Returns:
        A random 8-character hexadecimal string.
    """
    return secrets.token_hex(4)
