import pytest
from unittest.mock import MagicMock, patch
from core.template_registry import TemplateDNA
from core.research_agent import build_cql_query, run_search, ContentBundle, PageResult


def _make_dna():
    return TemplateDNA(
        purpose="Competitive battlecard",
        dimensions=["market positioning", "pricing models", "customer proof points"],
        tone="professional",
        source_guidance="research docs",
    )


def test_build_cql_query_basic():
    cql = build_cql_query(
        spaces=["CI", "PROD"],
        target="Sauce Labs",
        dimension_keyword="pricing",
        labels=[],
    )
    assert 'space IN ("CI", "PROD")' in cql
    assert 'text ~ "Sauce Labs"' in cql
    assert 'text ~ "pricing"' in cql
    assert "label" not in cql


def test_build_cql_query_with_labels():
    cql = build_cql_query(
        spaces=["CI"],
        target="Sauce Labs",
        dimension_keyword="market positioning",
        labels=["battlecard", "competitor"],
    )
    assert 'label IN ("battlecard", "competitor")' in cql


def test_run_search_returns_content_bundle():
    dna = _make_dna()
    mock_client = MagicMock()

    page_stub = {
        "id": "p1",
        "title": "Sauce Labs Q1 Analysis",
        "url": "https://mysite.atlassian.net/wiki/spaces/CI/pages/1",
        "space": "Competitive Intel",
    }
    mock_client.search.return_value = [page_stub]
    mock_client.get_page_content.return_value = {
        "title": "Sauce Labs Q1 Analysis",
        "url": "https://mysite.atlassian.net/wiki/spaces/CI/pages/1",
        "last_updated": "2026-03-01",
        "author": "Alice",
        "content": "Sauce Labs has 23% market share. Pricing starts at $99/month.",
    }

    bundle = run_search(
        template_dna=dna,
        target="Sauce Labs",
        confluence_spaces=["CI"],
        search_labels=[],
        confluence_client=mock_client,
        results_per_dim=5,
    )

    assert isinstance(bundle, ContentBundle)
    assert bundle.target == "Sauce Labs"
    assert bundle.template_dna == dna
    assert len(bundle.pages) >= 1
    assert bundle.pages[0].title == "Sauce Labs Q1 Analysis"
    assert "market positioning" in bundle.pages[0].matched_dimensions


def test_run_search_deduplicates_pages():
    """Same page returned by multiple dimension queries → appears once in bundle."""
    dna = _make_dna()
    mock_client = MagicMock()

    same_page = {
        "id": "p1",
        "title": "Big Analysis",
        "url": "https://mysite.atlassian.net/wiki/spaces/CI/pages/1",
        "space": "Competitive Intel",
    }
    mock_client.search.return_value = [same_page]
    mock_client.get_page_content.return_value = {
        "title": "Big Analysis",
        "url": "https://mysite.atlassian.net/wiki/spaces/CI/pages/1",
        "last_updated": "2026-03-01",
        "author": "Bob",
        "content": "Comprehensive content covering everything.",
    }

    bundle = run_search(
        template_dna=dna,
        target="Sauce Labs",
        confluence_spaces=["CI"],
        search_labels=[],
        confluence_client=mock_client,
        results_per_dim=5,
    )

    assert len(bundle.pages) == 1
    assert len(bundle.pages[0].matched_dimensions) == len(dna.dimensions)


def test_run_search_flags_unfilled_dimensions():
    dna = _make_dna()
    mock_client = MagicMock()
    mock_client.search.return_value = []

    bundle = run_search(
        template_dna=dna,
        target="Sauce Labs",
        confluence_spaces=["CI"],
        search_labels=[],
        confluence_client=mock_client,
        results_per_dim=5,
    )

    assert bundle.pages == []
    assert set(bundle.unfilled_dimensions) == set(dna.dimensions)


# --- Synthesis and upload tests ---

from core.research_agent import synthesise_research, build_research_markdown, upload_research_file


def _make_bundle():
    dna = TemplateDNA(
        purpose="Competitive battlecard",
        dimensions=["market positioning", "pricing models"],
        tone="professional",
        source_guidance="research docs",
    )
    return ContentBundle(
        target="Sauce Labs",
        template_name="Competitor Comparison",
        template_dna=dna,
        pages=[
            PageResult(
                id="p1",
                title="Sauce Labs Analysis",
                url="https://mysite.atlassian.net/wiki/spaces/CI/pages/1",
                space="Competitive Intel",
                last_updated="2026-03-01",
                author="Alice",
                content="Sauce Labs holds 23% market share. Pricing starts at $99.",
                matched_dimensions=["market positioning", "pricing models"],
            )
        ],
        unfilled_dimensions=["customer proof points"],
    )


def test_synthesise_research_calls_gemini_once():
    mock_config = MagicMock()
    mock_config.gemini_api_key = "key"
    mock_config.model_id = "gemini-flash"

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "## Market Positioning\n\nSauce Labs holds 23% share [Sauce Labs Analysis](https://...).\n\n## Pricing Models\n\nStarts at $99 [Sauce Labs Analysis](https://...)."
    mock_client.models.generate_content.return_value = mock_response

    bundle = _make_bundle()

    with patch("core.research_agent.genai.Client", return_value=mock_client):
        body = synthesise_research(bundle, mock_config)

    mock_client.models.generate_content.assert_called_once()
    assert "Market Positioning" in body or "market positioning" in body.lower()


def test_build_research_markdown_contains_frontmatter():
    bundle = _make_bundle()
    body = "## Market Positioning\n\nContent here."
    md = build_research_markdown(body, bundle)

    assert md.startswith("---")
    assert 'target: "Sauce Labs"' in md
    assert 'template: "Competitor Comparison"' in md
    assert "dimensions_covered: 1" in md
    assert "dimensions_unfilled: 1" in md
    assert "Sauce Labs Analysis" in md
    assert "## Market Positioning" in md


def test_build_research_markdown_unfilled_in_frontmatter():
    bundle = _make_bundle()
    body = "## Market Positioning\n\nContent."
    md = build_research_markdown(body, bundle)
    assert "customer proof points" in md


def test_upload_research_file_calls_drive_create():
    mock_service = MagicMock()
    mock_service.files.return_value.create.return_value.execute.return_value = {"id": "file123"}

    with patch("core.research_agent.build", return_value=mock_service), \
         patch("core.research_agent.get_credentials"):
        url = upload_research_file(
            content="# Research\n\nContent",
            filename="Sauce_Labs_2026-04-14.md",
            folder_id="folder123",
            credentials_path="/fake/creds.json",
        )

    assert url == "https://drive.google.com/file/d/file123/view"
    mock_service.files.return_value.create.assert_called_once()
    call_kwargs = mock_service.files.return_value.create.call_args[1]
    assert call_kwargs["body"]["name"] == "Sauce_Labs_2026-04-14.md"
    assert call_kwargs["body"]["parents"] == ["folder123"]
