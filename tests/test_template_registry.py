import json, pathlib, tempfile, pytest
from core.template_registry import (
    SlideDefault, Template, load_templates, save_templates,
    get_template_by_id, get_excluded_slide_numbers,
)


def _write_registry(path, data):
    path.write_text(json.dumps(data))


def test_load_returns_empty_list_when_file_missing(tmp_path):
    result = load_templates(str(tmp_path / "missing.json"))
    assert result == []


def test_save_and_load_roundtrip(tmp_path):
    reg = tmp_path / "templates.json"
    t = Template(
        id="t1", name="Battlecard",
        slides_id="abc123",
        variable_label="Competitor Name",
        variable_hint="e.g. Sauce Labs",
        slides=[
            SlideDefault(number=1, title="Cover", enabled=True),
            SlideDefault(number=3, title="Pricing", enabled=False),
        ],
    )
    save_templates([t], str(reg))
    loaded = load_templates(str(reg))
    assert len(loaded) == 1
    assert loaded[0].id == "t1"
    assert loaded[0].name == "Battlecard"
    assert loaded[0].slides[1].enabled is False


def test_get_template_by_id_found(tmp_path):
    reg = tmp_path / "templates.json"
    t = Template(id="x1", name="T", slides_id="s", variable_label="L", variable_hint="H", slides=[])
    save_templates([t], str(reg))
    templates = load_templates(str(reg))
    found = get_template_by_id(templates, "x1")
    assert found is not None
    assert found.name == "T"


def test_get_template_by_id_missing_returns_none():
    assert get_template_by_id([], "nope") is None


def test_get_excluded_slide_numbers():
    t = Template(
        id="t1", name="T", slides_id="s", variable_label="L", variable_hint="H",
        slides=[
            SlideDefault(number=1, title="Cover", enabled=True),
            SlideDefault(number=2, title="Overview", enabled=True),
            SlideDefault(number=3, title="Pricing", enabled=False),
            SlideDefault(number=4, title="FAQ", enabled=False),
        ],
    )
    assert get_excluded_slide_numbers(t) == [3, 4]


def test_get_excluded_slide_numbers_all_enabled():
    t = Template(
        id="t1", name="T", slides_id="s", variable_label="L", variable_hint="H",
        slides=[SlideDefault(number=1, title="Cover", enabled=True)],
    )
    assert get_excluded_slide_numbers(t) == []


def test_save_appends_new_template(tmp_path):
    reg = tmp_path / "templates.json"
    t1 = Template(id="t1", name="A", slides_id="s1", variable_label="L", variable_hint="H", slides=[])
    t2 = Template(id="t2", name="B", slides_id="s2", variable_label="L", variable_hint="H", slides=[])
    save_templates([t1], str(reg))
    save_templates([t1, t2], str(reg))
    loaded = load_templates(str(reg))
    assert len(loaded) == 2


def test_save_overwrites_on_id_collision(tmp_path):
    reg = tmp_path / "templates.json"
    t_old = Template(id="t1", name="Old Name", slides_id="s", variable_label="L", variable_hint="H", slides=[])
    t_new = Template(id="t1", name="New Name", slides_id="s", variable_label="L", variable_hint="H", slides=[])
    save_templates([t_old], str(reg))
    templates = load_templates(str(reg))
    updated = [t_new if t.id == "t1" else t for t in templates]
    save_templates(updated, str(reg))
    loaded = load_templates(str(reg))
    assert len(loaded) == 1
    assert loaded[0].name == "New Name"


# --- TemplateDNA and new Template fields ---

from core.template_registry import TemplateDNA


def _base_template() -> Template:
    return Template(
        id="abc123",
        name="Test Template",
        slides_id="slides_id",
        variable_label="Competitor",
        variable_hint="Acme",
        slides=[SlideDefault(number=1, title="Intro", enabled=True)],
    )


def test_template_dna_stored_on_template():
    dna = TemplateDNA(
        purpose="A competitive battlecard",
        dimensions=["market positioning", "pricing"],
        tone="professional",
        source_guidance="competitor research",
    )
    t = _base_template()
    t.template_dna = dna
    assert t.template_dna.purpose == "A competitive battlecard"
    assert len(t.template_dna.dimensions) == 2


def test_new_template_fields_default():
    t = _base_template()
    assert t.template_dna is None
    assert t.confluence_spaces == []
    assert t.search_labels == []
    assert t.research_drive_folder_id == ""


def test_save_and_load_preserves_new_fields(tmp_path):
    registry = tmp_path / "templates.json"
    dna = TemplateDNA(
        purpose="Test purpose",
        dimensions=["dim1", "dim2"],
        tone="formal",
        source_guidance="docs",
    )
    t = _base_template()
    t.template_dna = dna
    t.confluence_spaces = ["CI", "PROD"]
    t.search_labels = ["battlecard"]
    t.research_drive_folder_id = "folder123"

    save_templates([t], str(registry))
    loaded = load_templates(str(registry))

    assert loaded[0].confluence_spaces == ["CI", "PROD"]
    assert loaded[0].search_labels == ["battlecard"]
    assert loaded[0].research_drive_folder_id == "folder123"
    assert loaded[0].template_dna is not None
    assert loaded[0].template_dna.purpose == "Test purpose"
    assert loaded[0].template_dna.dimensions == ["dim1", "dim2"]


def test_load_templates_backward_compat_without_new_fields(tmp_path):
    """Existing templates.json without new fields must load without error."""
    registry = tmp_path / "templates.json"
    registry.write_text(json.dumps([{
        "id": "old1",
        "name": "Old Template",
        "slides_id": "slides1",
        "variable_label": "Competitor",
        "variable_hint": "Acme",
        "slides": [{"number": 1, "title": "Intro", "enabled": True}],
    }]))

    loaded = load_templates(str(registry))

    assert loaded[0].id == "old1"
    assert loaded[0].template_dna is None
    assert loaded[0].confluence_spaces == []
