# pages/1_Template_Setup.py
"""
Template Setup — power user page for creating and editing templates.
Only accessible when POWER_USER_MODE=true.
"""
import streamlit as st
from core.config import get_config
from core.template_registry import (
    Template, SlideDefault, load_templates, save_templates,
    get_template_by_id, new_template_id, REGISTRY_PATH,
)
from core.slides_helpers import fetch_slide_titles
import re

st.set_page_config(page_title="Template Setup", layout="centered")

config = get_config()

if not config.power_user_mode:
    st.error("Template setup requires POWER_USER_MODE=true.")
    st.stop()

# ── Session state ──────────────────────────────────────────────────────────
if "setup_slides_loaded" not in st.session_state:
    st.session_state.setup_slides_loaded = []  # list of {"number": int, "title": str}
if "setup_slide_defaults" not in st.session_state:
    st.session_state.setup_slide_defaults = {}  # {number: bool}
if "setup_editing_id" not in st.session_state:
    st.session_state.setup_editing_id = None  # template id being edited, or None for new


# ── Helpers ────────────────────────────────────────────────────────────────
def _extract_slides_id(value: str) -> str:
    """Extract presentation ID from a Google Slides URL or return as-is."""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", value)
    return match.group(1) if match else value.strip()


# ── Page ───────────────────────────────────────────────────────────────────
st.title("Template Setup")
st.caption("Create and manage presentation templates.")

templates = load_templates(REGISTRY_PATH)

# ── Existing templates list ────────────────────────────────────────────────
if templates:
    st.subheader("Existing Templates")
    for t in templates:
        col1, col2 = st.columns([5, 1])
        col1.write(f"**{t.name}** — {t.variable_label}")
        if col2.button("Edit", key=f"edit_{t.id}"):
            st.session_state.setup_editing_id = t.id
            # Pre-populate slides from saved defaults
            st.session_state.setup_slides_loaded = [
                {"number": s.number, "title": s.title} for s in t.slides
            ]
            st.session_state.setup_slide_defaults = {
                s.number: s.enabled for s in t.slides
            }
            st.rerun()

st.divider()

# ── Form: create or edit ───────────────────────────────────────────────────
editing = get_template_by_id(templates, st.session_state.setup_editing_id) if st.session_state.setup_editing_id else None
form_title = f"Edit: {editing.name}" if editing else "New Template"
st.subheader(form_title)

template_name = st.text_input(
    "Template Name",
    value=editing.name if editing else "",
    placeholder="e.g. Industry Targeted Comparison",
)

slides_url = st.text_input(
    "Google Slides Template",
    value=editing.slides_id if editing else "",
    placeholder="Paste Google Slides URL or ID",
)

col_load, col_hint = st.columns([2, 5])
load_clicked = col_load.button("Load Slides →")
col_hint.caption("Fetches slide structure from your template deck.")

if load_clicked and slides_url.strip():
    slides_id = _extract_slides_id(slides_url.strip())
    with st.spinner("Fetching slides..."):
        try:
            titles = fetch_slide_titles(config.gdrive_credentials_path, slides_id)
            st.session_state.setup_slides_loaded = titles
            st.session_state.setup_slide_defaults = {s["number"]: True for s in titles}
            st.success(f"Loaded {len(titles)} slides.")
        except Exception as e:
            st.error(f"Could not load slides: {e}")

col_lbl, col_hint_input = st.columns(2)
variable_label = col_lbl.text_input(
    "Label shown to users",
    value=editing.variable_label if editing else "",
    placeholder="e.g. Competitor Name",
)
variable_hint = col_hint_input.text_input(
    "Placeholder hint",
    value=editing.variable_hint if editing else "",
    placeholder="e.g. Sauce Labs",
)

# ── Slide defaults ─────────────────────────────────────────────────────────
if st.session_state.setup_slides_loaded:
    st.markdown("**Slides — Set Defaults**")
    st.caption("Toggle off slides that should be hidden by default.")
    for slide in st.session_state.setup_slides_loaded:
        num = slide["number"]
        default_val = st.session_state.setup_slide_defaults.get(num, True)
        enabled = st.toggle(
            f"Slide {num}: {slide['title']}",
            value=default_val,
            key=f"slide_toggle_{num}",
        )
        st.session_state.setup_slide_defaults[num] = enabled

# ── Save ───────────────────────────────────────────────────────────────────
if st.button("Save Template", type="primary"):
    if not template_name.strip():
        st.error("Template name is required.")
    elif not slides_url.strip():
        st.error("Google Slides URL or ID is required.")
    elif not variable_label.strip():
        st.error("Variable label is required.")
    elif not st.session_state.setup_slides_loaded:
        st.error("Please load slides before saving.")
    else:
        slides_id = _extract_slides_id(slides_url.strip())
        slide_defaults = [
            SlideDefault(
                number=s["number"],
                title=s["title"],
                enabled=st.session_state.setup_slide_defaults.get(s["number"], True),
            )
            for s in st.session_state.setup_slides_loaded
        ]
        new_t = Template(
            id=editing.id if editing else new_template_id(),
            name=template_name.strip(),
            slides_id=slides_id,
            variable_label=variable_label.strip(),
            variable_hint=variable_hint.strip(),
            slides=slide_defaults,
        )
        # Replace or append
        updated = [new_t if t.id == new_t.id else t for t in templates]
        if new_t.id not in {t.id for t in templates}:
            updated.append(new_t)
        save_templates(updated, REGISTRY_PATH)
        st.success(f"Template '{new_t.name}' saved.")
        # Reset form state
        st.session_state.setup_editing_id = None
        st.session_state.setup_slides_loaded = []
        st.session_state.setup_slide_defaults = {}
        st.rerun()
