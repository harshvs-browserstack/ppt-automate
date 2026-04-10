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
