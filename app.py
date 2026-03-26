# ─────────────────────────────────────────────────────────────────────────────
#  app.py  –  AI Resume Tailor & Cover Letter Generator
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import io, os
from datetime import date
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

from ai_utils import (
    AVAILABLE_MODELS, generate_cover_letter, tailor_resume, validate_credentials,
)
from doc_utils import (
    apply_paragraph_replacements, apply_user_info, build_document_preview,
    extract_resume_text, get_template_context, load_docx, save_docx_to_bytes,
)

load_dotenv()

# ── Default bundled templates ─────────────────────────────────────────────────
_TEMPLATES_DIR        = Path(__file__).parent / "templates"
_DEFAULT_RESUME_BYTES = (_TEMPLATES_DIR / "default_resume_template.docx").read_bytes() \
                        if (_TEMPLATES_DIR / "default_resume_template.docx").exists() else None
_DEFAULT_CL_BYTES     = (_TEMPLATES_DIR / "default_cover_letter_template.docx").read_bytes() \
                        if (_TEMPLATES_DIR / "default_cover_letter_template.docx").exists() else None

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
    background: #eef6ff; border-left: 4px solid #1a73e8;
    padding: .75rem 1rem; border-radius: 4px; font-size: .9rem;
}
.preview-box {
    background: #fafafa; border: 1px solid #e0e0e0;
    border-radius: 6px; padding: 1.2rem 1.4rem;
    font-family: 'Georgia', serif; font-size: .88rem;
    line-height: 1.65; white-space: pre-wrap;
    max-height: 480px; overflow-y: auto;
}
.preview-box hr { border: none; border-top: 1px solid #ccc; margin: .5rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")
    st.divider()

    st.subheader("🤖 AI Model")
    selected_display = st.selectbox("Select model", list(AVAILABLE_MODELS.keys()), index=0)
    selected_model   = AVAILABLE_MODELS[selected_display]
    st.caption(f"Model ID: `{selected_model}`")

    st.divider()
    st.subheader("🔐 SAP AI Core")
    creds_ok, missing_vars = validate_credentials()
    if creds_ok:
        st.success("✅ All credentials found")
    else:
        st.error(
            "Missing:\n" + "\n".join(f"• `{v}`" for v in missing_vars)
            + "\n\nAdd to Streamlit Settings → Secrets."
        )

    st.divider()
    st.subheader("🛡️ Honesty Guardrail")
    st.markdown("""
    <div class="honesty-banner">
    The AI <strong>never invents</strong> skills, titles, degrees, or experience
    absent from your base resume.
    </div>
    """, unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📄 AI Resume Tailor & Cover Letter Generator")
st.caption(
    "Upload any .docx template — no placeholders needed. "
    "The AI reads the structure and fills it in with your real experience."
)
st.divider()

# ── Session state initialisation ─────────────────────────────────────────────
for k, default in [
    ("bytes_base_resume",            None),
    ("bytes_resume_template",        _DEFAULT_RESUME_BYTES),
    ("bytes_cover_letter_template",  _DEFAULT_CL_BYTES),
    ("tailored_resume_bytes",        None),
    ("tailored_resume_preview",      None),
    ("cover_letter_bytes",           None),
    ("cover_letter_preview",         None),
]:
    if k not in st.session_state:
        st.session_state[k] = default

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1 — Upload Documents
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 1 — Upload Your Documents")

col_l, col_r = st.columns(2, gap="large")

with col_l:
    st.subheader("📋 Base Resume")
    st.caption("Your master resume — the AI uses only facts from this file.")
    base_file = st.file_uploader("Upload Base Resume (.docx)", type=["docx"], key="base_resume")
    if base_file is not None:
        st.session_state["bytes_base_resume"] = base_file.read()

with col_r:
    st.subheader("📝 Resume Template")
    _def_r = st.session_state["bytes_resume_template"] == _DEFAULT_RESUME_BYTES and _DEFAULT_RESUME_BYTES
    st.caption("✅ Using **built-in template**" if _def_r else "✅ Using **your template**")
    rt_file = st.file_uploader("Upload Resume Template — optional", type=["docx"], key="resume_tpl")
    if rt_file is not None:
        st.session_state["bytes_resume_template"] = rt_file.read()

    st.subheader("✉️ Cover Letter Template")
    _def_cl = st.session_state["bytes_cover_letter_template"] == _DEFAULT_CL_BYTES and _DEFAULT_CL_BYTES
    st.caption("✅ Using **built-in template**" if _def_cl else "✅ Using **your template**")
    cl_file = st.file_uploader("Upload Cover Letter Template — optional", type=["docx"], key="cl_tpl")
    if cl_file is not None:
        st.session_state["bytes_cover_letter_template"] = cl_file.read()

_br  = st.session_state["bytes_base_resume"]
_rt  = st.session_state["bytes_resume_template"]
_clt = st.session_state["bytes_cover_letter_template"]

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2 — Your Details
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 2 — Your Details")
st.caption(
    "These replace the placeholder name, contact info, company details, and "
    "signature in your template. Leave blank to keep the template's original text."
)

with st.expander("👤 Personal & Contact Information", expanded=True):
    pi_col1, pi_col2 = st.columns(2, gap="large")
    with pi_col1:
        user_name     = st.text_input("Full Name",    placeholder="Jane Doe",              key="u_name")
        user_location = st.text_input("Location",     placeholder="New York, NY",           key="u_loc")
        user_email    = st.text_input("Email",        placeholder="jane@email.com",         key="u_email")
    with pi_col2:
        user_phone    = st.text_input("Phone",        placeholder="(555) 123-4567",         key="u_phone")
        user_linkedin = st.text_input("LinkedIn URL", placeholder="linkedin.com/in/janedoe",key="u_li")

with st.expander("🏢 Cover Letter — Company & Date", expanded=True):
    cl_col1, cl_col2 = st.columns(2, gap="large")
    with cl_col1:
        company_name  = st.text_input("Company Name",       placeholder="Acme Corp",              key="c_name")
        company_addr1 = st.text_input("Company Address",    placeholder="123 Main St (optional)", key="c_addr1")
    with cl_col2:
        company_addr2 = st.text_input("City, State ZIP",    placeholder="New York, NY 10001 (optional)", key="c_addr2")
        letter_date   = st.text_input(
            "Letter Date",
            value=date.today().strftime("%B %d, %Y"),
            key="c_date",
        )

# Bundle user info for injection
user_info = {
    "name":          user_name,
    "location":      user_location,
    "email":         user_email,
    "phone":         user_phone,
    "linkedin":      user_linkedin,
    "company":       company_name,
    "company_addr1": company_addr1,
    "company_addr2": company_addr2,
    "date":          letter_date,
}

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3 — Job Description
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 3 — Paste the Job Description")
job_desc = st.text_area(
    "Target Job Description",
    height=200,
    placeholder="Paste the full job posting — role title, responsibilities, requirements…",
)
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 4 — Preview Base Resume
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 4 — Preview Your Base Resume")
if _br:
    with st.expander("👁️ What the AI will read from your base resume", expanded=False):
        try:
            preview_doc = load_docx(io.BytesIO(_br))
            text = extract_resume_text(preview_doc)
            if text.strip():
                st.text_area("Extracted text (read-only)", value=text, height=260, disabled=True)
                st.caption(
                    f"{len(text.split())} words · "
                    f"{len(preview_doc.paragraphs)} paragraphs · "
                    f"{len(preview_doc.tables)} table(s)"
                )
            else:
                st.warning("No text extracted — your resume may use images or text boxes.")
        except Exception as e:
            st.error(f"Could not read base resume: {e}")
else:
    st.info("Upload your base resume in Step 1 to preview its content here.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 5 — Generate & Download
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 5 — Generate & Download")

col_res, col_cl = st.columns(2, gap="large")

# ── Resume ────────────────────────────────────────────────────────────────────
with col_res:
    st.subheader("📋 Tailored Resume")
    res_ready = bool(_br and _rt and job_desc.strip())
    if not _br:            st.warning("⬆️ Upload your **base resume** in Step 1.")
    if not job_desc.strip(): st.warning("✏️ Paste a **job description** in Step 3.")

    if st.button("✨ Tailor My Resume",
                 disabled=(not res_ready or not creds_ok),
                 use_container_width=True, type="primary"):
        with st.spinner(f"Tailoring with **{selected_display}**…"):
            try:
                # 1. Extract base resume text
                base_text = extract_resume_text(load_docx(io.BytesIO(_br)))
                if not base_text.strip():
                    st.error("No text found in base resume.")
                    st.stop()

                # 2. Get template structure and ask AI
                tpl_doc = load_docx(io.BytesIO(_rt))
                replacements = tailor_resume(
                    base_text, job_desc, get_template_context(tpl_doc), selected_model
                )
                if not replacements:
                    st.error("AI returned no replacements. Try a different model.")
                    st.stop()

                # 3. Apply AI replacements to a fresh template copy
                out_doc = load_docx(io.BytesIO(_rt))
                n = apply_paragraph_replacements(out_doc, replacements)

                # 4. Apply user info (name, contact, etc.) on top
                apply_user_info(out_doc, user_info)

                # 5. Save
                st.session_state["tailored_resume_bytes"]   = save_docx_to_bytes(out_doc)
                st.session_state["tailored_resume_preview"] = build_document_preview(out_doc)
                st.success(f"✅ Done — {n} section(s) tailored.")

            except ValueError as e:
                st.error(
                    f"The AI's response could not be parsed as JSON even after retry.\n\n{e}\n\n"
                    "Try a different model — GPT-4.1 and Claude 4.5 Sonnet are most reliable."
                )
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    if st.session_state["tailored_resume_preview"]:
        with st.expander("👁️ Preview — Tailored Resume", expanded=True):
            st.markdown(
                f'<div class="preview-box">{st.session_state["tailored_resume_preview"]}</div>',
                unsafe_allow_html=True,
            )

    if st.session_state["tailored_resume_bytes"]:
        st.download_button(
            "⬇️  Download Tailored Resume (.docx)",
            data=st.session_state["tailored_resume_bytes"],
            file_name="tailored_resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

# ── Cover Letter ──────────────────────────────────────────────────────────────
with col_cl:
    st.subheader("✉️ Cover Letter")
    cl_ready = bool(_br and _clt and job_desc.strip())
    if not _br:            st.warning("⬆️ Upload your **base resume** in Step 1.")
    if not job_desc.strip(): st.warning("✏️ Paste a **job description** in Step 3.")

    if st.button("✨ Generate Cover Letter",
                 disabled=(not cl_ready or not creds_ok),
                 use_container_width=True, type="primary"):
        with st.spinner(f"Writing with **{selected_display}**…"):
            try:
                base_text2 = extract_resume_text(load_docx(io.BytesIO(_br)))
                if not base_text2.strip():
                    st.error("No text found in base resume.")
                    st.stop()

                cl_tpl_doc = load_docx(io.BytesIO(_clt))
                replacements_cl = generate_cover_letter(
                    base_text2, job_desc, get_template_context(cl_tpl_doc), selected_model
                )
                if not replacements_cl:
                    st.error("AI returned no replacements.")
                    st.stop()

                out_cl = load_docx(io.BytesIO(_clt))
                n_cl = apply_paragraph_replacements(out_cl, replacements_cl)
                apply_user_info(out_cl, user_info)

                st.session_state["cover_letter_bytes"]   = save_docx_to_bytes(out_cl)
                st.session_state["cover_letter_preview"] = build_document_preview(out_cl)
                st.success(f"✅ Done — {n_cl} section(s) written.")

            except ValueError as e:
                st.error(
                    f"The AI's response could not be parsed as JSON even after retry.\n\n{e}\n\n"
                    "Try a different model — GPT-4.1 and Claude 3.5 Sonnet are most reliable."
                )
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    if st.session_state["cover_letter_preview"]:
        with st.expander("👁️ Preview — Cover Letter", expanded=True):
            st.markdown(
                f'<div class="preview-box">{st.session_state["cover_letter_preview"]}</div>',
                unsafe_allow_html=True,
            )

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
<div style="text-align:center;color:#888;font-size:.8rem">
Built with Streamlit · python-docx · SAP AI Core &nbsp;|&nbsp;
🛡️ Honesty guardrail prevents AI hallucination
</div>
""", unsafe_allow_html=True)