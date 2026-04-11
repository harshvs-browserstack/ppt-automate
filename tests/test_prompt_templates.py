from core.prompt_templates import create_slide_generation_prompt


def test_prompt_contains_competitor_name():
    """Test that prompt includes the competitor name."""
    elements = [{"placeholderId": "t1", "originalContent": "Title", "contentRuns": []}]
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="Perfecto",
        template_view_pdf_name="template.pdf",
    )
    assert "Perfecto" in prompt
    assert "BrowserStack" in prompt


def test_prompt_contains_slide_json():
    """Test that prompt includes the slide elements JSON."""
    elements = [{"placeholderId": "t1", "originalContent": "Hello", "contentRuns": []}]
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="Acme",
        template_view_pdf_name="ref.pdf",
    )
    assert '"placeholderId": "t1"' in prompt
    assert '"originalContent": "Hello"' in prompt


def test_prompt_contains_json_output_instruction():
    """Test that prompt instructs the model to return valid JSON."""
    elements = []
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="X",
        template_view_pdf_name="t.pdf",
    )
    assert "json" in prompt.lower()


def test_custom_template_context_replaces_battlecard_context():
    """When template_context is provided, it replaces the hardcoded battlecard context."""
    elements = [{"placeholderId": "t1", "originalContent": "Title", "contentRuns": []}]
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="Fintech",
        template_view_pdf_name="ref.pdf",
        template_context="This is an industry pitch deck for the Fintech sector.",
    )
    assert "Fintech" in prompt
    assert "This is an industry pitch deck" in prompt


def test_default_context_is_battlecard():
    """Without template_context, prompt defaults to battlecard language."""
    elements = []
    prompt = create_slide_generation_prompt(
        slide_elements_json=elements,
        competitor="Acme",
        template_view_pdf_name="ref.pdf",
    )
    assert "battlecard" in prompt.lower()
