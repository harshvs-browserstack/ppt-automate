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
import pathlib

st.set_page_config(page_title="Template Setup", layout="centered")

# Load CSS for dark mode support
css_path = pathlib.Path(__file__).parent.parent / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

config = get_config()

# ── Session state ──────────────────────────────────────────────────────────
if "setup_slides_loaded" not in st.session_state:
    st.session_state.setup_slides_loaded = []  # list of {"number": int, "title": str}
if "setup_slide_defaults" not in st.session_state:
    st.session_state.setup_slide_defaults = {}  # {number: bool}
if "setup_editing_id" not in st.session_state:
    st.session_state.setup_editing_id = None  # template id being edited, or None for new
if "show_success_banner" not in st.session_state:
    st.session_state.show_success_banner = False
if "template_name_input" not in st.session_state:
    st.session_state.template_name_input = ""
if "slides_url_input" not in st.session_state:
    st.session_state.slides_url_input = ""
if "var_label_input" not in st.session_state:
    st.session_state.var_label_input = ""
if "var_hint_input" not in st.session_state:
    st.session_state.var_hint_input = ""


# ── Helpers ────────────────────────────────────────────────────────────────
def _extract_slides_id(value: str) -> str:
    """Extract presentation ID from a Google Slides URL or return as-is."""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", value)
    return match.group(1) if match else value.strip()


# ── Page ───────────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="font-family:\'Newsreader\',serif;font-size:2.25rem;margin-bottom:0.25rem">Editorial Template Setup</h1>',
    unsafe_allow_html=True,
)
st.caption("Create and manage presentation templates.")
st.markdown("<br>", unsafe_allow_html=True)

# Success banner placeholder (shown at top when template is saved)
success_banner = st.empty()

templates = load_templates(REGISTRY_PATH)

# ── Existing templates list ────────────────────────────────────────────────
if templates:
    st.markdown('<div class="section-label">Existing Templates</div>', unsafe_allow_html=True)
    for t in templates:
        col_info, col_edit, col_delete = st.columns([3.2, 0.4, 0.4])
        col_info.markdown(
            f'<div style="padding:0.75rem;border:1px solid #334155;background:#1E293B;border-radius:0">'
            f'<div style="font-weight:600;margin-bottom:0.25rem;color:#F1F5F9">{t.name}</div>'
            f'<div style="font-size:0.875rem;color:#94A3B8">{t.variable_label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if col_edit.button("✏️", key=f"edit_{t.id}", use_container_width=True):
            st.session_state.setup_editing_id = t.id
            # Pre-populate slides from saved defaults
            st.session_state.setup_slides_loaded = [
                {"number": s.number, "title": s.title} for s in t.slides
            ]
            st.session_state.setup_slide_defaults = {
                s.number: s.enabled for s in t.slides
            }
            # Clear input widget state so new values can be loaded
            st.session_state.template_name_input = t.name
            st.session_state.slides_url_input = t.slides_id
            st.session_state.var_label_input = t.variable_label
            st.session_state.var_hint_input = t.variable_hint
            st.rerun()
        if col_delete.button("🗑️", key=f"delete_{t.id}", use_container_width=True):
            # Remove template and save
            updated = [x for x in templates if x.id != t.id]
            save_templates(updated, REGISTRY_PATH)
            st.rerun()
    st.divider()

# ── Form: create or edit ───────────────────────────────────────────────────
editing = get_template_by_id(templates, st.session_state.setup_editing_id) if st.session_state.setup_editing_id else None
form_title = f"Edit: {editing.name}" if editing else "New Template"

col_title, col_new = st.columns([4.5, 1.5])
with col_title:
    st.markdown(f'<div style="font-size:0.875rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#94A3B8;margin-bottom:1rem">{form_title}</div>', unsafe_allow_html=True)
with col_new:
    if editing:
        st.markdown('<div style="height:0.25rem"></div>', unsafe_allow_html=True)
        if st.button("New →", use_container_width=True):
            st.session_state.setup_editing_id = None
            st.session_state.setup_slides_loaded = []
            st.session_state.setup_slide_defaults = {}
            st.session_state.template_name_input = ""
            st.session_state.slides_url_input = ""
            st.session_state.var_label_input = ""
            st.session_state.var_hint_input = ""
            st.rerun()

template_name = st.text_input(
    label="Template Name",
    placeholder="e.g. Industry Targeted Comparison",
    key="template_name_input",
)

st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)

col_slides, col_btn = st.columns([5.5, 1.2])
with col_slides:
    slides_url = st.text_input(
        label="Google Slides Template",
        placeholder="Paste Google Slides URL or ID",
        key="slides_url_input",
    )
with col_btn:
    st.markdown('<div style="height:1.75rem"></div>', unsafe_allow_html=True)
    load_clicked = st.button("Load Slides →", use_container_width=True, key="load_slides_btn")

st.caption("Fetches slide structure from your template deck.")

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

st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

col_lbl, col_hint_input = st.columns(2)
with col_lbl:
    variable_label = st.text_input(
        label="Label shown to users",
        placeholder="e.g. Competitor Name",
        key="var_label_input",
    )
with col_hint_input:
    variable_hint = st.text_input(
        label="Placeholder hint",
        placeholder="e.g. Sauce Labs",
        key="var_hint_input",
    )

# ── Slide defaults ─────────────────────────────────────────────────────────
if st.session_state.setup_slides_loaded:
    st.markdown('<div class="section-label">Slides — Set Defaults</div>', unsafe_allow_html=True)
    st.caption("Toggle off slides that should be excluded by default. Keep enabled the slides that appear in every generation.")
    for slide in st.session_state.setup_slides_loaded:
        num = slide["number"]
        default_val = st.session_state.setup_slide_defaults.get(num, True)
        enabled = st.toggle(
            f"Slide {num}: {slide['title']}",
            value=default_val,
            key=f"slide_toggle_{num}",
        )
        st.session_state.setup_slide_defaults[num] = enabled

st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)

# ── Save ───────────────────────────────────────────────────────────────────
_, col_save = st.columns([1, 4])  # Right-align the button
with col_save:
    if st.button("Save Template", type="primary", use_container_width=True):
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

            # Show success banner at top
            success_banner.markdown(
                f'<div style="background:rgba(16,185,129,0.1);border:1.5px solid #10B981;padding:1rem;'
                f'border-radius:0;margin-bottom:1rem">'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span style="font-size:20px;color:#10B981">✓</span>'
                f'<span style="color:#10B981;font-weight:600">Template Saved!</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            # Reset form state
            st.session_state.setup_editing_id = None
            st.session_state.setup_slides_loaded = []
            st.session_state.setup_slide_defaults = {}
            st.session_state.template_name_input = ""
            st.session_state.slides_url_input = ""
            st.session_state.var_label_input = ""
            st.session_state.var_hint_input = ""

            # Clear banner after 2 seconds
            import time
            time.sleep(2)
            success_banner.empty()
            st.rerun()
