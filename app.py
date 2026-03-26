# ─────────────────────────────────────────────────────────────────────────────
#  app.py  –  AI Resume Tailor & Cover Letter Generator
#  No placeholders required — the AI reads the template structure directly.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import io, os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

from ai_utils import (
    AVAILABLE_MODELS, generate_cover_letter, tailor_resume, validate_credentials,
)
from doc_utils import (
    apply_paragraph_replacements, extract_resume_text,
    get_template_context, load_docx, save_docx_to_bytes,
)

load_dotenv()

# ── Default (fallback) templates ──────────────────────────────────────────────
# Bundled in the repo under templates/.  Used automatically when the user
# does not upload their own template.
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DEFAULT_RESUME_TPL_PATH = _TEMPLATES_DIR / "default_resume_template.docx"
_DEFAULT_CL_TPL_PATH     = _TEMPLATES_DIR / "default_cover_letter_template.docx"

def _load_default_bytes(path: Path) -> bytes | None:
    """Read a bundled template file and return its raw bytes, or None if missing."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None

_DEFAULT_RESUME_BYTES = _load_default_bytes(_DEFAULT_RESUME_TPL_PATH)
_DEFAULT_CL_BYTES     = _load_default_bytes(_DEFAULT_CL_TPL_PATH)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Resume Tailor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
.honesty-banner {
    background:#eef6ff; border-left:4px solid #1a73e8;
    padding:0.75rem 1rem; border-radius:4px; font-size:0.9rem;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    st.divider()

    st.subheader("🤖 AI Model")
    selected_display = st.selectbox(
        "Select model",
        list(AVAILABLE_MODELS.keys()),
        index=0,
    )
    selected_model = AVAILABLE_MODELS[selected_display]
    st.caption(f"Deployment: `{selected_model}`")

    st.divider()

    st.subheader("🔐 SAP AI Core Credentials")
    creds_ok, missing_vars = validate_credentials()
    if creds_ok:
        st.success("✅ All credentials found")
    else:
        st.error(
            "Missing variables:\n" + "\n".join(f"• `{v}`" for v in missing_vars)
            + "\n\nCopy `.env.example` → `.env` and fill in your SAP AI Core credentials."
        )

    st.divider()
    st.subheader("🛡️ Honesty Guardrail")
    st.markdown("""
    <div class="honesty-banner">
    The AI is <strong>hardcoded</strong> to never invent skills, titles,
    degrees, or experiences not in your base resume.
    </div>
    """, unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("📄 AI Resume Tailor & Cover Letter Generator")
st.caption(
    "Upload your base resume + any template. "
    "The AI reads the template structure and fills it in — no placeholders needed."
)
st.divider()

# ── Step 1: uploads ───────────────────────────────────────────────────────────
st.header("Step 1 — Upload Your Documents")

# Byte-cache: read each file ONCE into session_state.
# Initialise template slots with the bundled defaults so they work immediately
# even if the user never uploads their own template.
if "bytes_base_resume" not in st.session_state:
    st.session_state["bytes_base_resume"] = None
if "bytes_resume_template" not in st.session_state:
    st.session_state["bytes_resume_template"] = _DEFAULT_RESUME_BYTES
if "bytes_cover_letter_template" not in st.session_state:
    st.session_state["bytes_cover_letter_template"] = _DEFAULT_CL_BYTES

col_l, col_r = st.columns(2, gap="large")

with col_l:
    st.subheader("📋 Base Resume")
    st.caption("Your master resume — the AI only uses facts from this file.")
    base_file = st.file_uploader("Upload Base Resume (.docx)", type=["docx"], key="base_resume")
    if base_file is not None:
        st.session_state["bytes_base_resume"] = base_file.read()

with col_r:
    st.subheader("📝 Resume Template")
    # Show whether the default or a custom template is active
    _using_default_resume = (
        st.session_state["bytes_resume_template"] == _DEFAULT_RESUME_BYTES
        and _DEFAULT_RESUME_BYTES is not None
    )
    if _using_default_resume:
        st.caption("✅ Using the **built-in Stony Brook template** — upload your own to override.")
    else:
        st.caption("✅ Using your **uploaded template**.")

    resume_tpl_file = st.file_uploader(
        "Upload Resume Template (.docx) — optional",
        type=["docx"],
        key="resume_template",
    )
    if resume_tpl_file is not None:
        st.session_state["bytes_resume_template"] = resume_tpl_file.read()

    st.subheader("✉️ Cover Letter Template")
    _using_default_cl = (
        st.session_state["bytes_cover_letter_template"] == _DEFAULT_CL_BYTES
        and _DEFAULT_CL_BYTES is not None
    )
    if _using_default_cl:
        st.caption("✅ Using the **built-in Stony Brook template** — upload your own to override.")
    else:
        st.caption("✅ Using your **uploaded template**.")

    cl_tpl_file = st.file_uploader(
        "Upload Cover Letter Template (.docx) — optional",
        type=["docx"],
        key="cl_template",
    )
    if cl_tpl_file is not None:
        st.session_state["bytes_cover_letter_template"] = cl_tpl_file.read()

_br  = st.session_state["bytes_base_resume"]
_rt  = st.session_state["bytes_resume_template"]
_clt = st.session_state["bytes_cover_letter_template"]

st.divider()

# ── Step 2: job description ───────────────────────────────────────────────────
st.header("Step 2 — Paste the Job Description")
job_desc = st.text_area(
    "Target Job Description",
    height=220,
    placeholder="Paste the full job posting here — role title, responsibilities, requirements…",
)
st.divider()

# ── Step 3: preview base resume ───────────────────────────────────────────────
st.header("Step 3 — Preview Base Resume Content")
if _br:
    with st.expander("👁️ View what the AI will read from your base resume", expanded=False):
        try:
            doc_preview = load_docx(io.BytesIO(_br))
            text = extract_resume_text(doc_preview)
            if text.strip():
                st.text_area("Extracted text (read-only)", value=text, height=280, disabled=True)
                st.caption(f"{len(text.split())} words · {len(doc_preview.paragraphs)} paragraphs · {len(doc_preview.tables)} table(s)")
            else:
                st.warning("No text found — your resume may use text boxes or images which cannot be read.")
        except Exception as e:
            st.error(f"Could not read base resume: {e}")
else:
    st.info("Upload your base resume above to preview its content.")

st.divider()

# ── Step 4: generate ──────────────────────────────────────────────────────────
st.header("Step 4 — Generate & Download")

for k in ("tailored_resume_bytes", "tailored_resume_text",
          "cover_letter_bytes", "cover_letter_text"):
    if k not in st.session_state:
        st.session_state[k] = None

col_res, col_cl = st.columns(2, gap="large")

# ── Resume column ─────────────────────────────────────────────────────────────
with col_res:
    st.subheader("📋 Tailored Resume")
    res_ready = bool(_br and _rt and job_desc.strip())
    if not _br:  st.warning("⬆️ Upload your **base resume**.")
    if not job_desc.strip(): st.warning("✏️ Paste a **job description**.")

    if st.button("✨ Tailor My Resume", disabled=(not res_ready or not creds_ok),
                 use_container_width=True, type="primary"):
        with st.spinner(f"Analysing template & tailoring with **{selected_display}**…"):
            try:
                # 1. Extract base resume text
                base_doc   = load_docx(io.BytesIO(_br))
                base_text  = extract_resume_text(base_doc)
                if not base_text.strip():
                    st.error("No text could be extracted from the base resume.")
                    st.stop()

                # 2. Load template and get its structure for the AI
                tpl_doc    = load_docx(io.BytesIO(_rt))
                tpl_ctx    = get_template_context(tpl_doc)

                # 3. Ask AI to fill in the template
                replacements = tailor_resume(base_text, job_desc, tpl_ctx, selected_model)

                if not replacements:
                    st.error("The AI returned no replacements. Try a different model or check your credentials.")
                    st.stop()

                # 4. Apply replacements to a fresh copy of the template
                tpl_doc2   = load_docx(io.BytesIO(_rt))
                n_applied  = apply_paragraph_replacements(tpl_doc2, replacements)

                st.session_state["tailored_resume_bytes"] = save_docx_to_bytes(tpl_doc2)
                st.session_state["tailored_resume_text"]  = "\n".join(
                    f"[{k}] {v}" for k, v in sorted(replacements.items(), key=lambda x: int(x[0]))
                )
                st.success(f"✅ Done — {n_applied} paragraph(s) updated in your template.")

            except ValueError as e:
                st.error(f"Could not parse AI response as JSON: {e}")
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    if st.session_state["tailored_resume_text"]:
        with st.expander("👁️ Preview AI replacements", expanded=True):
            st.text_area("AI-generated content (read-only)",
                         value=st.session_state["tailored_resume_text"],
                         height=280, disabled=True)

    if st.session_state["tailored_resume_bytes"]:
        st.download_button(
            "⬇️  Download Tailored Resume (.docx)",
            data=st.session_state["tailored_resume_bytes"],
            file_name="tailored_resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

# ── Cover letter column ───────────────────────────────────────────────────────
with col_cl:
    st.subheader("✉️ Cover Letter")
    cl_ready = bool(_br and _clt and job_desc.strip())
    if not _br:   st.warning("⬆️ Upload your **base resume**.")
    if not job_desc.strip(): st.warning("✏️ Paste a **job description**.")

    if st.button("✨ Generate Cover Letter", disabled=(not cl_ready or not creds_ok),
                 use_container_width=True, type="primary"):
        with st.spinner(f"Writing cover letter with **{selected_display}**…"):
            try:
                base_doc2  = load_docx(io.BytesIO(_br))
                base_text2 = extract_resume_text(base_doc2)
                if not base_text2.strip():
                    st.error("No text could be extracted from the base resume.")
                    st.stop()

                cl_doc     = load_docx(io.BytesIO(_clt))
                cl_ctx     = get_template_context(cl_doc)

                replacements_cl = generate_cover_letter(base_text2, job_desc, cl_ctx, selected_model)

                if not replacements_cl:
                    st.error("The AI returned no replacements.")
                    st.stop()

                cl_doc2    = load_docx(io.BytesIO(_clt))
                n_cl       = apply_paragraph_replacements(cl_doc2, replacements_cl)

                st.session_state["cover_letter_bytes"] = save_docx_to_bytes(cl_doc2)
                st.session_state["cover_letter_text"]  = "\n".join(
                    f"[{k}] {v}" for k, v in sorted(replacements_cl.items(), key=lambda x: int(x[0]))
                )
                st.success(f"✅ Done — {n_cl} paragraph(s) updated in your template.")

            except ValueError as e:
                st.error(f"Could not parse AI response as JSON: {e}")
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    if st.session_state["cover_letter_text"]:
        with st.expander("👁️ Preview AI replacements", expanded=True):
            st.text_area("AI-generated content (read-only)",
                         value=st.session_state["cover_letter_text"],
                         height=280, disabled=True)

    if st.session_state["cover_letter_bytes"]:
        st.download_button(
            "⬇️  Download Cover Letter (.docx)",
            data=st.session_state["cover_letter_bytes"],
            file_name="cover_letter.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

st.divider()
st.markdown("""
<div style="text-align:center;color:#888;font-size:0.8rem">
Built with Streamlit · python-docx · SAP Generative AI Hub SDK &nbsp;|&nbsp;
🛡️ Honesty guardrails prevent AI hallucination
</div>
""", unsafe_allow_html=True)