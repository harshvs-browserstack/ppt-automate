"""
AI-powered template suggestion using Gemini.
Given a natural language description, returns the best matching template
and optionally the extracted target value (competitor name, industry, etc.).
"""
import json
from dataclasses import dataclass
from typing import List, Optional

from google import genai

from core.template_registry import Template


@dataclass
class SuggestionResult:
    template_id: str
    reason: str
    extracted_target: Optional[str]


def suggest_template(
    description: str,
    templates: List[Template],
    api_key: str,
    model_id: str = "gemini-2.5-flash",
) -> SuggestionResult:
    """
    Use Gemini to suggest the best template for the given description.

    Args:
        description: Natural language description of what the user needs
        templates: Available templates to choose from
        api_key: Gemini API key
        model_id: Gemini model to use

    Returns:
        SuggestionResult with template_id, reason, and optional extracted_target
    """
    if not templates:
        raise ValueError("No templates available to suggest from.")

    template_list = "\n".join(
        f'- id: "{t.id}", name: "{t.name}", variable: "{t.variable_label}"'
        for t in templates
    )

    prompt = f"""You are helping a user pick the right presentation template.

Available templates:
{template_list}

User description: "{description}"

Pick the best template for this description. Also try to extract the specific target value
(e.g. the competitor name, industry name, or client name) from the description if it's mentioned.

Respond with ONLY valid JSON in this exact format:
{{
  "template_id": "<id of the best matching template>",
  "reason": "<one sentence explaining why this template fits>",
  "extracted_target": "<the extracted target value, or null if not mentioned>"
}}"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
    )
    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return parse_suggestion_response(raw.strip(), templates)


def parse_suggestion_response(raw: str, templates: List[Template]) -> SuggestionResult:
    """
    Parse a raw Gemini JSON response string into a SuggestionResult.
    Falls back to the first template if parsing fails or template_id is unknown.

    Args:
        raw: Raw JSON string from Gemini
        templates: Available templates (must not be empty)
    """
    if not templates:
        raise ValueError("No templates provided to parse_suggestion_response.")

    fallback_id = templates[0].id
    valid_ids = {t.id for t in templates}

    try:
        data = json.loads(raw)
        template_id = data.get("template_id", fallback_id)
        if template_id not in valid_ids:
            template_id = fallback_id
        return SuggestionResult(
            template_id=template_id,
            reason=data.get("reason", ""),
            extracted_target=data.get("extracted_target") or None,
        )
    except (json.JSONDecodeError, AttributeError):
        return SuggestionResult(
            template_id=fallback_id,
            reason="Could not parse suggestion — defaulting to first template.",
            extracted_target=None,
        )
