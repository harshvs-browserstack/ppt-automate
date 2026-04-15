# app.py
import asyncio
import json
import os
import pathlib
import streamlit as st

st.set_page_config(
    page_title="Document to Deck",
    page_icon="✨",
    layout="wide",
)

css_path = pathlib.Path(__file__).parent / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from core.config import get_config
from core.template_registry import load_templates, get_template_by_id, get_excluded_slide_numbers, REGISTRY_PATH
from core.suggest_template import suggest_template
from core.cache import invalidate_history_cache

config = get_config()

# ── Session state ──────────────────────────────────────────────────────────
defaults = {
    "app_state": "input",
    "final_url": None,
    "error_msg": None,
    "pdf_bytes": None,
    "pdf_filename": None,
    "target": "",
    "selected_template_id": None,
    "suggest_mode": False,
    "suggest_result": None,      # SuggestionResult or None
    "auto_filled_target": False,
    "research_md": None,         # Research Markdown content from the research agent
    "research_drive_url": None,  # Drive URL of the uploaded research file
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Helpers ────────────────────────────────────────────────────────────────
def _select_template(template_id: str, target: str = None):
    st.session_state.selected_template_id = template_id
    st.session_state.suggest_mode = False
    st.session_state.suggest_result = None
    if target is not None:
        st.session_state.target = target
        st.session_state.auto_filled_target = True
    else:
        st.session_state.auto_filled_target = False


def _run_research_step(template, target: str) -> tuple:
    """Run the B-Lite research agent synchronously. Returns (md_content, drive_url)."""
    from core.confluence_client import ConfluenceClient
    from core.research_agent import run_search, synthesise_research, build_research_markdown, upload_research_file, research_filename

    if not config.confluence_base_url or not config.confluence_api_token:
        raise ValueError("CONFLUENCE_BASE_URL and CONFLUENCE_API_TOKEN must be set.")

    with ConfluenceClient(config.confluence_base_url, config.confluence_user_email, config.confluence_api_token) as client:
        bundle = run_search(
            template_dna=template.template_dna,
            target=target,
            confluence_spaces=template.confluence_spaces,
            search_labels=template.search_labels,
            confluence_client=client,
            template_name=template.name,
        )

    body = synthesise_research(bundle, config)
    md_content = build_research_markdown(body, bundle)

    drive_url = ""
    if template.research_drive_folder_id:
        filename = research_filename(target, template.name)
        drive_url = upload_research_file(
            content=md_content,
            filename=filename,
            folder_id=template.research_drive_folder_id,
            credentials_path=config.gdrive_credentials_path,
        )
    return md_content, drive_url, bundle


# ── State: INPUT ───────────────────────────────────────────────────────────
if st.session_state.app_state == "input":

    templates = load_templates(REGISTRY_PATH)
    selected_template = get_template_by_id(templates, st.session_state.selected_template_id)

    # ── Hero ───────────────────────────────────────────────────────────────
    st.markdown(
        '<h1 style="font-family:\'Newsreader\',serif;font-size:2rem;font-weight:600;'
        'color:#A78BFA;margin-bottom:0.25rem">Turn Research Into a Deck</h1>',
        unsafe_allow_html=True,
    )
    st.caption("Pick a template below, upload your PDF, and let AI do the rest.")
    st.markdown("<br>", unsafe_allow_html=True)

    if selected_template:
        # Breadcrumb: "← All templates  ›  Template Name"
        col_back, col_crumb = st.columns([1.2, 8])
        with col_back:
            st.markdown('<div class="btn-link">', unsafe_allow_html=True)
            if st.button("← All templates", key="btn_change"):
                st.session_state.selected_template_id = None
                st.session_state.suggest_mode = False
                st.session_state.suggest_result = None
                st.session_state.auto_filled_target = False
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        col_crumb.markdown(
            f'<div class="breadcrumb">'
            f'<span class="breadcrumb-sep">›</span>'
            f'<span class="breadcrumb-current">{selected_template.name}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Suggest Template inline flow (disabled) ────────────────────────────
    # if st.session_state.suggest_mode and not selected_template:
    #     st.markdown('<div class="suggest-panel">', unsafe_allow_html=True)
    #     st.markdown('<div class="section-label">What do you need?</div>', unsafe_allow_html=True)
    #     description = st.text_area(
    #         label="",
    #         placeholder="e.g. I need a deck comparing BrowserStack to Sauce Labs for an enterprise fintech prospect...",
    #         height=80,
    #         key="suggest_description",
    #     )
    #     col_suggest_btn, col_cancel = st.columns([2, 1])
    #     suggest_clicked = col_suggest_btn.button("Suggest →", key="btn_suggest", type="primary")
    #     if col_cancel.button("Cancel", key="btn_cancel_suggest"):
    #         st.session_state.suggest_mode = False
    #         st.rerun()
    #     st.markdown("</div>", unsafe_allow_html=True)
    #
    #     if suggest_clicked and description.strip() and templates:
    #         with st.spinner("Finding the right template..."):
    #             result = suggest_template(
    #                 description=description.strip(),
    #                 templates=templates,
    #                 api_key=config.gemini_api_key,
    #                 model_id=config.model_id,
    #             )
    #         st.session_state.suggest_result = result
    #         st.rerun()
    #
    #     # Show suggestion result card
    #     if st.session_state.suggest_result:
    #         r = st.session_state.suggest_result
    #         suggested_t = get_template_by_id(templates, r.template_id)
    #         if suggested_t:
    #             st.markdown(
    #                 f'<div class="suggestion-card">'
    #                 f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
    #                 f'<span style="background:#059669;color:#fff;font-size:0.65rem;font-weight:700;'
    #                 f'padding:2px 8px">✦ Suggested</span>'
    #                 f'<strong style="color:#111827">{suggested_t.name}</strong>'
    #                 f'</div>'
    #                 f'<p style="font-size:0.8rem;color:#6B7280;margin-bottom:0">{r.reason}</p>'
    #                 f'</div>',
    #                 unsafe_allow_html=True,
    #             )
    #             col_use, col_pick = st.columns([3, 1])
    #             if col_use.button(f"Use {suggested_t.name} →", key="btn_use_suggestion", type="primary", use_container_width=True):
    #                 _select_template(r.template_id, r.extracted_target)
    #                 st.rerun()
    #             if col_pick.button("Pick another", key="btn_pick_another", use_container_width=True):
    #                 st.session_state.suggest_result = None
    #                 st.rerun()

    # ── Template row ───────────────────────────────────────────────────────
    col_template_label, col_add = st.columns([5, 1])
    col_template_label.markdown(
        '<div class="section-label">'
        + ("Step 1 — Pick a template" if not selected_template else "Template")
        + '</div>',
        unsafe_allow_html=True,
    )
    if col_add.button("+ Add", key="btn_add_template"):
        st.switch_page("pages/1_🎨_Template_Setup.py")

    if not templates:
        st.info("No templates yet. Click + Add to create one.")
    else:
        suggest_cols = st.columns(min(len(templates), 5))
        # # ── Suggest button disabled ────────────────────────────────────────
        # if suggest_cols[0].button("✦ Suggest", key="btn_suggest_row",
        #                            type="primary" if not st.session_state.suggest_mode else "secondary"):
        #     st.session_state.suggest_mode = True
        #     st.rerun()
        # Template tiles
        for i, t in enumerate(templates):
            col = suggest_cols[i] if i < len(suggest_cols) else suggest_cols[-1]
            is_selected = st.session_state.selected_template_id == t.id
            btn_type = "primary" if is_selected else "secondary"
            label = f"✓ {t.name}" if is_selected else t.name
            if col.button(label, key=f"tile_{t.id}", type=btn_type, use_container_width=True):
                _select_template(t.id)
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Variable field (appears after template selected) ───────────────────
    if selected_template:
        label_text = selected_template.variable_label
        if st.session_state.auto_filled_target:
            label_html = (
                f'<div class="section-label">{label_text}'
                f'<span class="auto-filled-badge">auto-filled</span></div>'
            )
            st.markdown(label_html, unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="section-label">{label_text}</div>', unsafe_allow_html=True)

        target = st.text_input(
            label="",
            value=st.session_state.target,
            placeholder=selected_template.variable_hint,
            key="target_input",
        )
        st.session_state.target = target

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Research preview (shown if research was already run) ───────────
        has_research = bool(st.session_state.research_md)
        if has_research:
            with st.expander("Research File Preview", expanded=False):
                st.markdown(st.session_state.research_md)
                if st.session_state.research_drive_url:
                    st.markdown(f"[View in Google Drive]({st.session_state.research_drive_url})")

        # ── PDF Upload ─────────────────────────────────────────────────────
        pdf_label = "Supplementary PDF (optional)" if has_research else "Research PDF"
        st.markdown(f'<div class="section-label">{pdf_label}</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            label="",
            type=["pdf"],
        )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.session_state.error_msg:
            st.error(st.session_state.error_msg)
            st.session_state.error_msg = None

        can_generate = bool(target.strip()) and (uploaded_file is not None or has_research)

        # Research button — shown when template has DNA + Confluence spaces configured
        has_confluence = (
            selected_template and
            selected_template.template_dna and
            selected_template.confluence_spaces
        )
        if has_confluence:
            if st.button("Search Confluence →", use_container_width=True):
                if not target.strip():
                    st.error(f"Please enter {selected_template.variable_label} before searching.")
                else:
                    with st.spinner("Searching Confluence for research..."):
                        try:
                            md_content, drive_url, bundle = _run_research_step(selected_template, target.strip())
                            st.session_state.research_md = md_content
                            st.session_state.research_drive_url = drive_url
                            # Surface gap warnings
                            if bundle.unfilled_dimensions:
                                st.warning(f"No sources found for: {', '.join(bundle.unfilled_dimensions)}. Consider uploading a supplementary PDF.")
                            else:
                                st.success(f"Research complete — {len(bundle.pages)} pages found across {len(bundle.template_dna.dimensions)} dimensions.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Research failed: {e}")

        if st.button("Generate Deck →", type="primary", use_container_width=True):
            if not target.strip():
                st.error(f"Please enter {selected_template.variable_label}.")
            elif not can_generate:
                st.error("Please upload a PDF or run the Confluence research before generating.")
            else:
                if uploaded_file:
                    st.session_state.pdf_bytes = uploaded_file.read()
                    st.session_state.pdf_filename = uploaded_file.name
                st.session_state.target = target.strip()
                st.session_state.app_state = "loading"
                st.rerun()


# ── State: LOADING ─────────────────────────────────────────────────────────
elif st.session_state.app_state == "loading":
    st.title("Generating Your Presentation")
    st.caption("This may take a few minutes. Do not close this tab.")
    st.markdown("<br>", unsafe_allow_html=True)

    status_label = st.empty()
    progress_bar = st.progress(0.0)
    sub_label = st.empty()

    def on_status(message: str, progress: float, sub: str = None):
        status_label.markdown(f"**{message}**")
        progress_bar.progress(min(progress, 1.0))
        if sub:
            sub_label.caption(sub)
        else:
            sub_label.empty()

    try:
        from core.formatter_pipeline import run_ai_content_population

        templates = load_templates(REGISTRY_PATH)
        selected_template = get_template_by_id(templates, st.session_state.selected_template_id)

        slides_id = selected_template.slides_id if selected_template else config.original_slides_id
        excluded = get_excluded_slide_numbers(selected_template) if selected_template else []

        dna_context = ""
        if selected_template and selected_template.template_dna:
            dna = selected_template.template_dna
            dna_context = f"{dna.purpose} Tone: {dna.tone}"

        final_url = asyncio.run(
            run_ai_content_population(
                competitor=st.session_state.target,
                config=config,
                pdf_bytes=st.session_state.pdf_bytes,
                pdf_filename=st.session_state.pdf_filename,
                research_md_content=st.session_state.research_md,
                slides_id=slides_id,
                excluded_slide_numbers=excluded,
                template_name=selected_template.name if selected_template else None,
                template_dna_context=dna_context,
                on_status=on_status,
            )
        )

        progress_bar.progress(1.0)
        status_label.markdown("**Done!**")
        sub_label.empty()

        st.session_state.final_url = final_url
        st.session_state.app_state = "success"
        st.session_state.research_md = None
        st.session_state.research_drive_url = None
        invalidate_history_cache()  # Clear history cache so next view gets fresh data
        st.rerun()

    except Exception as e:
        raw = str(e)
        try:
            # Try to surface just the human-readable message from API error JSON
            parsed = json.loads(raw)
            display = parsed.get("error", {}).get("message") or raw
        except (json.JSONDecodeError, AttributeError):
            display = raw
        st.session_state.error_msg = display
        st.session_state.app_state = "input"
        st.rerun()


# ── State: SUCCESS ─────────────────────────────────────────────────────────
elif st.session_state.app_state == "success":
    st.markdown(
        '<div style="display:flex;flex-direction:column;align-items:center;padding:2rem 0 1rem;">'
        '<div style="width:48px;height:48px;background:#059669;border-radius:50%;'
        'display:flex;align-items:center;justify-content:center;margin-bottom:1.5rem;">'
        '<span style="color:white;font-size:24px;">✓</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.title("Presentation Ready")
    st.markdown("<br>", unsafe_allow_html=True)

    final_url = st.session_state.final_url
    if final_url:
        st.markdown(
            f'<a href="{final_url}" target="_blank" '
            f'style="display:flex;align-items:center;justify-content:center;gap:8px;'
            f'width:100%;height:48px;background:#1E1B4B;color:#FFFFFF;'
            f'font-family:\'Switzer\',sans-serif;font-size:14px;font-weight:500;'
            f'text-decoration:none;border:none;transition:background 0.2s;">'
            f'View in Google Slides <span style="font-size:16px;">↗</span>'
            f'</a>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Generate Another"):
        for key in ["app_state", "final_url", "pdf_bytes", "pdf_filename",
                    "target", "selected_template_id", "suggest_mode",
                    "suggest_result", "auto_filled_target"]:
            st.session_state[key] = defaults[key]
        st.rerun()
