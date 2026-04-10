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
