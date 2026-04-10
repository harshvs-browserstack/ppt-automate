"""
Prompt templates for Gemini slide content generation.
Builds the prompt that instructs Gemini to generate competitive battlecard content.
"""
import json
from typing import Any, Dict, List


def create_slide_generation_prompt(
    slide_elements_json: List[Dict[str, Any]],
    competitor: str,
    template_view_pdf_name: str,
) -> str:
    """
    Build the Gemini prompt for a single slide's content generation.

    This prompt instructs Gemini to:
    1. Generate competitive battlecard content comparing BrowserStack vs competitor
    2. Preserve the JSON structure and styling of the template
    3. Replace only the text content, not structure/IDs
    4. Return valid JSON output

    Args:
        slide_elements_json: List of text element dicts with placeholderId, originalContent, contentRuns
        competitor: Name of competitor or target client
        template_view_pdf_name: Name of the template PDF for reference

    Returns:
        A complete prompt string for Gemini
    """
    return f"""
You are a helpful assistant tasked with generating a competitive battlecard in JSON format, comparing BrowserStack and {competitor}.
Use the provided JSON template structure as a guide for the output format.
Replace the existing content in the template with new content comparing "BrowserStack vs {competitor}", drawing from the provided source documents.

**CONTEXT:**
The presentation is a competitive battlecard comparing BrowserStack to {competitor}.
Use the attached research documents to inform the content you generate.
Use the document named {template_view_pdf_name} for context on what the presentation should look like.

**INPUT SLIDE JSON:**
```json
{json.dumps(slide_elements_json, indent=2)}
```

**INSTRUCTIONS:**
1. **Prioritize Document Context:** Generate content based primarily on the information in the uploaded documents. Avoid hallucinations.
2. **Fill Information Gaps:** If specific information is missing from the documents, use your search tool to find current details.
3. **Scope of Comparison:** Cover both platform-level and product-level aspects.
4. **JSON Output Requirements:**
   - Return a single valid JSON array of the text elements for this slide.
   - Never change objectIds, placeholderIds, or any style objects.
   - Only replace text within the "text" fields inside "contentRuns" arrays.
   - Preserve all escape characters like \\n.
5. **Content:** Keep texts between 95-105% of the original character count. Maintain a professional, comparative tone with a bias toward BrowserStack.
6. **References:** Only add references in speaker notes, in Chicago MLA format.

Generate the JSON battlecard comparing BrowserStack and {competitor}:
"""
