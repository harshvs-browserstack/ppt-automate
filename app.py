# app.py
import asyncio
import os
import pathlib
import streamlit as st

# Page config must be the first Streamlit call
st.set_page_config(
    page_title="Document to Deck",
    page_icon="✨",
    layout="centered",
)

# Inject CSS
css_path = pathlib.Path(__file__).parent / "styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "app_state" not in st.session_state:
    st.session_state.app_state = "input"
if "final_url" not in st.session_state:
    st.session_state.final_url = None
if "error_msg" not in st.session_state:
    st.session_state.error_msg = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = None
if "competitor" not in st.session_state:
    st.session_state.competitor = ""


# ---------------------------------------------------------------------------
# State: INPUT
# ---------------------------------------------------------------------------

if st.session_state.app_state == "input":
    st.title("Generate Your Presentation")
    st.caption("Upload your research and let AI map it directly to your master template.")

    st.markdown("<br>", unsafe_allow_html=True)

    competitor = st.text_input(
        "Target Client or Competitor Name",
        value=st.session_state.competitor,
        placeholder="e.g. Acme Corp",
    )

    uploaded_file = st.file_uploader(
        "Drop your Knowledge Document (PDF) here",
        type=["pdf"],
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.error_msg:
        st.error(st.session_state.error_msg)
        st.session_state.error_msg = None

    generate_clicked = st.button("Generate Deck ✨", type="primary")

    if generate_clicked:
        if not uploaded_file:
            st.error("Please upload a PDF before generating.")
        elif not competitor.strip():
            st.error("Please enter a target client or competitor name.")
        else:
            st.session_state.pdf_bytes = uploaded_file.read()
            st.session_state.pdf_filename = uploaded_file.name
            st.session_state.competitor = competitor.strip()
            st.session_state.app_state = "loading"
            st.rerun()


# ---------------------------------------------------------------------------
# State: LOADING
# ---------------------------------------------------------------------------

elif st.session_state.app_state == "loading":
    st.title("Generating Your Presentation")
    st.caption("This may take a few minutes. Do not close this tab.")

    st.markdown("<br>", unsafe_allow_html=True)

    status_container = st.empty()
    progress_bar = st.progress(0)

    steps = [
        (0.05, "Cleaning up previous run..."),
        (0.15, "Configuring template settings..."),
        (0.25, "Generating template structure..."),
        (0.35, "Fetching configuration IDs..."),
        (0.45, "Uploading PDF to AI..."),
        (0.55, "Loading style map..."),
        (0.65, "Generating slide content with AI..."),
        (0.85, "Uploading content to Google Sheets..."),
        (0.95, "Populating Google Slides..."),
    ]

    step_iter = iter(steps)

    def on_status(msg: str):
        try:
            progress, label = next(step_iter)
            progress_bar.progress(progress)
            status_container.markdown(f"**{label}**")
        except StopIteration:
            pass

    try:
        from core.config import get_config
        from core.formatter_pipeline import run_ai_content_population

        config = get_config()

        final_url = asyncio.run(
            run_ai_content_population(
                pdf_bytes=st.session_state.pdf_bytes,
                pdf_filename=st.session_state.pdf_filename,
                competitor=st.session_state.competitor,
                config=config,
                on_status=on_status,
            )
        )

        progress_bar.progress(1.0)
        status_container.markdown("**Done!**")

        st.session_state.final_url = final_url
        st.session_state.app_state = "success"
        st.rerun()

    except Exception as e:
        st.session_state.error_msg = f"Pipeline failed: {e}"
        st.session_state.app_state = "input"
        st.rerun()


# ---------------------------------------------------------------------------
# State: SUCCESS
# ---------------------------------------------------------------------------

elif st.session_state.app_state == "success":
    st.markdown(
        """
        <div style="display:flex;flex-direction:column;align-items:center;padding:2rem 0 1rem;">
            <div style="width:48px;height:48px;background:#059669;border-radius:50%;
                        display:flex;align-items:center;justify-content:center;margin-bottom:1.5rem;">
                <span style="color:white;font-size:24px;">✓</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.title("Presentation Ready")

    st.markdown("<br>", unsafe_allow_html=True)

    final_url = st.session_state.final_url
    if final_url:
        st.markdown(
            f"""
            <a href="{final_url}" target="_blank"
               style="display:flex;align-items:center;justify-content:center;gap:8px;
                      width:100%;height:48px;background:#1E1B4B;color:#FFFFFF;
                      font-family:'Switzer',sans-serif;font-size:14px;font-weight:500;
                      text-decoration:none;border:none;transition:background 0.2s;">
                View in Google Slides
                <span style="font-size:16px;">↗</span>
            </a>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Generate Another"):
        st.session_state.app_state = "input"
        st.session_state.final_url = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_filename = None
        st.session_state.competitor = ""
        st.rerun()
