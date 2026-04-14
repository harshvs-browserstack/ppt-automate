"""
Research Agent (B-Lite).
Runs deterministic CQL searches against Confluence, extracts page content,
synthesises an attributed Markdown research file, and uploads it to Drive.
"""
import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from core.config import Config
    from core.confluence_client import ConfluenceClient
    from core.template_registry import TemplateDNA


_MAX_CHARS_PER_PAGE = 4000  # keeps synthesis prompt manageable


@dataclass
class PageResult:
    """A single Confluence page retrieved during research."""
    id: str
    title: str
    url: str
    space: str
    last_updated: str
    author: str
    content: str
    matched_dimensions: List[str] = field(default_factory=list)


@dataclass
class ContentBundle:
    """All retrieved pages plus metadata, ready for synthesis."""
    target: str
    template_name: str
    template_dna: "TemplateDNA"
    pages: List[PageResult]
    unfilled_dimensions: List[str]


def build_cql_query(
    spaces: List[str],
    target: str,
    dimension_keyword: str,
    labels: List[str],
) -> str:
    """
    Construct a CQL query for one research dimension.

    Args:
        spaces: Confluence space keys to restrict search to.
        target: The subject being researched (e.g. "Sauce Labs").
        dimension_keyword: Leading keyword for this dimension (e.g. "pricing").
        labels: Optional Confluence page labels to further restrict results.

    Returns:
        CQL query string.
    """
    space_filter = ", ".join(f'"{s}"' for s in spaces)
    parts = [
        f"space IN ({space_filter})",
        'type = "page"',
        f'text ~ "{target}"',
        f'text ~ "{dimension_keyword}"',
    ]
    if labels:
        label_filter = ", ".join(f'"{l}"' for l in labels)
        parts.append(f"label IN ({label_filter})")
    return " AND ".join(parts)


def _leading_keyword(dimension: str) -> str:
    """Extract the first substantive word from a dimension string."""
    stop = {"&", "and", "vs", "of", "the", "a", "an"}
    for word in dimension.lower().split():
        if word not in stop:
            return word
    return dimension.split()[0].lower()


def run_search(
    template_dna: "TemplateDNA",
    target: str,
    confluence_spaces: List[str],
    search_labels: List[str],
    confluence_client: "ConfluenceClient",
    results_per_dim: int = 5,
    template_name: str = "",
) -> ContentBundle:
    """
    Execute CQL searches for each DNA dimension and build a ContentBundle.

    One CQL query per dimension. Pages deduplicated across dimensions.
    Dimensions returning zero results are recorded in unfilled_dimensions.

    Args:
        template_dna: Template DNA providing research dimensions.
        target: The research subject (e.g. "Sauce Labs").
        confluence_spaces: Space keys to search within.
        search_labels: Optional Confluence labels to filter by.
        confluence_client: Authenticated ConfluenceClient instance.
        results_per_dim: Max pages to fetch per dimension query.
        template_name: Template display name for bundle metadata.

    Returns:
        ContentBundle with all unique pages and unfilled dimension flags.
    """
    seen: dict = {}  # page_id -> PageResult (dedup accumulator)
    unfilled: List[str] = []

    for dimension in template_dna.dimensions:
        keyword = _leading_keyword(dimension)
        cql = build_cql_query(confluence_spaces, target, keyword, search_labels)

        search_results = confluence_client.search(cql, limit=results_per_dim)
        if not search_results:
            unfilled.append(dimension)
            continue

        for result in search_results:
            page_id = result["id"]
            if page_id not in seen:
                page_content = confluence_client.get_page_content(page_id)
                truncated = page_content["content"][:_MAX_CHARS_PER_PAGE]
                seen[page_id] = PageResult(
                    id=page_id,
                    title=result["title"],
                    url=result["url"],
                    space=result["space"],
                    last_updated=page_content["last_updated"],
                    author=page_content["author"],
                    content=truncated,
                    matched_dimensions=[dimension],
                )
            else:
                if dimension not in seen[page_id].matched_dimensions:
                    seen[page_id].matched_dimensions.append(dimension)

    return ContentBundle(
        target=target,
        template_name=template_name,
        template_dna=template_dna,
        pages=list(seen.values()),
        unfilled_dimensions=unfilled,
    )


# ============================================================================
# Synthesis and Upload
# ============================================================================

from google import genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from core.auth_helpers import get_credentials


_SYNTHESIS_PROMPT = """
You are a research analyst compiling a briefing document.

Template purpose: {purpose}
Target: {target}
Information dimensions needed:
{dimensions}

Source pages retrieved from Confluence:
{pages_section}

Instructions:
- Organise the output by information dimension using ## headers matching the dimension names above.
- Every factual claim MUST include an inline citation formatted as: [Page Title](url)
- If multiple sources support a point, cite all of them.
- If a dimension has no coverage, write its ## header followed by:
  "⚠ No sources found for this dimension."
- Do not fabricate information. Only use what the source pages contain.
- Preserve specific numbers, quotes, and data points exactly as they appear.
- Write in a neutral, analytical tone.
- Output only the section content (## headers + body text). Do not include YAML frontmatter.
"""


def _build_synthesis_prompt(bundle: ContentBundle) -> str:
    dimensions_list = "\n".join(
        f"{i + 1}. {d}" for i, d in enumerate(bundle.template_dna.dimensions)
    )
    page_sections = []
    for page in bundle.pages:
        page_sections.append(
            f"--- {page.title} ---\n"
            f"URL: {page.url}\n"
            f"Relevant dimensions: {', '.join(page.matched_dimensions)}\n\n"
            f"{page.content}"
        )
    pages_section = "\n\n".join(page_sections) if page_sections else "No pages retrieved."
    return _SYNTHESIS_PROMPT.format(
        purpose=bundle.template_dna.purpose,
        target=bundle.target,
        dimensions=dimensions_list,
        pages_section=pages_section,
    )


def synthesise_research(bundle: ContentBundle, config: "Config") -> str:
    """
    Call Gemini once to synthesise the content bundle into attributed research sections.

    Args:
        bundle: ContentBundle from run_search.
        config: Application config.

    Returns:
        Markdown body string (sections only, no frontmatter).
    """
    client = genai.Client(api_key=config.gemini_api_key)
    prompt = _build_synthesis_prompt(bundle)
    response = client.models.generate_content(
        model=config.model_id,
        contents=[prompt],
        config={"temperature": 0.2},
    )
    return response.text


def build_research_markdown(body: str, bundle: ContentBundle) -> str:
    """
    Wrap the synthesis body with YAML frontmatter to produce the final research file.

    Args:
        body: Markdown body returned by synthesise_research.
        bundle: ContentBundle (provides metadata for frontmatter).

    Returns:
        Complete Markdown string with frontmatter.
    """
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    covered = len(bundle.template_dna.dimensions) - len(bundle.unfilled_dimensions)

    sources_yaml = "\n".join(
        f'  - title: "{p.title}"\n'
        f'    url: "{p.url}"\n'
        f'    space: "{p.space}"\n'
        f'    last_updated: "{p.last_updated}"'
        for p in bundle.pages
    )
    unfilled_yaml = (
        "\n".join(f'  - "{d}"' for d in bundle.unfilled_dimensions)
        if bundle.unfilled_dimensions
        else "  []"
    )

    frontmatter = (
        f"---\n"
        f'title: "Research Brief: {bundle.target}"\n'
        f'template: "{bundle.template_name}"\n'
        f'generated: "{now}"\n'
        f'target: "{bundle.target}"\n'
        f"dimensions_covered: {covered}\n"
        f"dimensions_unfilled: {len(bundle.unfilled_dimensions)}\n"
        f"unfilled_dimensions:\n{unfilled_yaml}\n"
        f"sources:\n{sources_yaml if sources_yaml else '  []'}\n"
        f"---"
    )
    return f"{frontmatter}\n\n# Research Brief: {bundle.target}\n\n{body}"


def upload_research_file(
    content: str,
    filename: str,
    folder_id: str,
    credentials_path: str,
) -> str:
    """
    Upload the research Markdown file to a Google Drive folder.

    Args:
        content: Markdown file content as a string.
        filename: Filename to use in Drive.
        folder_id: Google Drive folder ID to upload into.
        credentials_path: Path to service account credentials JSON.

    Returns:
        Google Drive view URL for the uploaded file.
    """
    creds = get_credentials(credentials_path)
    service = build("drive", "v3", credentials=creds)
    media = MediaInMemoryUpload(
        content.encode("utf-8"),
        mimetype="text/markdown",
        resumable=False,
    )
    file_metadata = {"name": filename, "parents": [folder_id]}
    result = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()
    return f"https://drive.google.com/file/d/{result['id']}/view"


def research_filename(target: str, template_name: str) -> str:
    """
    Build a consistent filename for the research file.

    Returns e.g. "Sauce_Labs_Competitor_Comparison_2026-04-14.md"
    """
    date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    safe_target = target.replace(" ", "_")
    safe_template = template_name.replace(" ", "_")
    return f"{safe_target}_{safe_template}_{date}.md"
