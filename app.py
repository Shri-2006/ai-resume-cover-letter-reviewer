# ─────────────────────────────────────────────────────────────────────────────
#  app.py  –  AI Resume Tailor & Cover Letter Generator
#  Supports multiple job applications in a single session.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import io
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

# ── Bundled default templates ─────────────────────────────────────────────────
_TPL_DIR              = Path(__file__).parent / "templates"
_DEFAULT_RESUME_BYTES = (_TPL_DIR / "default_resume_template.docx").read_bytes() \
                        if (_TPL_DIR / "default_resume_template.docx").exists() else None
_DEFAULT_CL_BYTES     = (_TPL_DIR / "default_cover_letter_template.docx").read_bytes() \
                        if (_TPL_DIR / "default_cover_letter_template.docx").exists() else None

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
    background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px;
    padding: 1.2rem 1.4rem; font-family: Georgia, serif; font-size: .88rem;
    line-height: 1.65; white-space: pre-wrap;
    max-height: 400px; overflow-y: auto;
}
.job-card {
    border: 1px solid #e0e0e0; border-radius: 8px;
    padding: 1.2rem 1.4rem; margin-bottom: 1rem;
    background: #ffffff;
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
        index=0,   # GPT-5.2 is first in the dict
    )
    selected_model = AVAILABLE_MODELS[selected_display]
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

# ── Page header ───────────────────────────────────────────────────────────────
st.title("📄 AI Resume Tailor & Cover Letter Generator")
st.caption(
    "Upload your base resume once — generate tailored documents for as many "
    "jobs as you want in a single session."
)
st.divider()

# ── Session state setup ───────────────────────────────────────────────────────
for k, default in [
    ("bytes_base_resume",           None),
    ("bytes_resume_template",       _DEFAULT_RESUME_BYTES),
    ("bytes_cover_letter_template", _DEFAULT_CL_BYTES),
]:
    if k not in st.session_state:
        st.session_state[k] = default

# Jobs list: each job is a dict with a unique id.
# All widget state (labels, descriptions, outputs) lives in session_state
# under keys scoped by the job id (e.g. "jlabel_3", "jdesc_3").
if "jobs" not in st.session_state:
    st.session_state["jobs"]         = [{"id": 0}]
    st.session_state["next_job_id"]  = 1

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1 — Documents
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 1 — Upload Your Documents")

col_l, col_r = st.columns(2, gap="large")

with col_l:
    st.subheader("📋 Base Resume")
    st.caption("Your master resume — AI uses only facts from this file.")
    bf = st.file_uploader("Upload Base Resume (.docx)", type=["docx"], key="base_resume")
    if bf is not None:
        st.session_state["bytes_base_resume"] = bf.read()

    # Inline preview
    if st.session_state["bytes_base_resume"]:
        with st.expander("👁️ Preview extracted resume text", expanded=False):
            try:
                pdoc = load_docx(io.BytesIO(st.session_state["bytes_base_resume"]))
                ptxt = extract_resume_text(pdoc)
                if ptxt.strip():
                    st.text_area("Extracted text", value=ptxt, height=220, disabled=True)
                    st.caption(f"{len(ptxt.split())} words")
                else:
                    st.warning("No text found — resume may use images or text boxes.")
            except Exception as e:
                st.error(f"Could not read resume: {e}")

with col_r:
    st.subheader("📝 Resume Template")
    _dr = st.session_state["bytes_resume_template"] == _DEFAULT_RESUME_BYTES and _DEFAULT_RESUME_BYTES
    st.caption("✅ Using **built-in template**" if _dr else "✅ Using **your template**")
    rtf = st.file_uploader("Upload Resume Template — optional", type=["docx"], key="rtpl")
    if rtf is not None:
        st.session_state["bytes_resume_template"] = rtf.read()

    st.subheader("✉️ Cover Letter Template")
    _dc = st.session_state["bytes_cover_letter_template"] == _DEFAULT_CL_BYTES and _DEFAULT_CL_BYTES
    st.caption("✅ Using **built-in template**" if _dc else "✅ Using **your template**")
    clf = st.file_uploader("Upload Cover Letter Template — optional", type=["docx"], key="cltpl")
    if clf is not None:
        st.session_state["bytes_cover_letter_template"] = clf.read()

_br  = st.session_state["bytes_base_resume"]
_rt  = st.session_state["bytes_resume_template"]
_clt = st.session_state["bytes_cover_letter_template"]
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2 — Your Details (filled once, applied to every job)
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 2 — Your Details")
st.caption("Filled in once — applied to every job you generate.")

with st.expander("👤 Personal & Contact Information", expanded=True):
    c1, c2 = st.columns(2, gap="large")
    with c1:
        user_name     = st.text_input("Full Name",    placeholder="Jane Doe",               key="u_name")
        user_location = st.text_input("Location",     placeholder="New York, NY",            key="u_loc")
        user_email    = st.text_input("Email",        placeholder="jane@email.com",          key="u_email")
    with c2:
        user_phone    = st.text_input("Phone",        placeholder="(555) 123-4567",          key="u_phone")
        user_linkedin = st.text_input("LinkedIn URL", placeholder="linkedin.com/in/janedoe", key="u_li")
        user_github   = st.text_input("GitHub URL",   placeholder="github.com/janedoe (optional)", key="u_gh")

with st.expander("🏢 Cover Letter — Company & Date", expanded=True):
    cc1, cc2 = st.columns(2, gap="large")
    with cc1:
        # Note: company name / address are per-job, but we put global defaults here.
        # Users can override per job below.
        default_company  = st.text_input("Default Company Name",    placeholder="Leave blank to fill per job", key="def_company")
        default_addr1    = st.text_input("Company Address",         placeholder="123 Main St (optional)",      key="def_addr1")
    with cc2:
        default_addr2    = st.text_input("City, State ZIP",         placeholder="New York, NY 10001 (optional)", key="def_addr2")
        default_date     = st.text_input(
            "Letter Date",
            value=date.today().strftime("%B %d, %Y"),
            key="def_date",
        )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Helper: error message for JSON parse failures
# ─────────────────────────────────────────────────────────────────────────────
_JSON_ERR_HINT = (
    "Try a different model — **GPT-4.1**, **GPT-4.1 Mini**, and "
    "**Claude 3.5 Sonnet** are the most reliable for structured output."
)

def _gen_error(label: str, exc: Exception) -> None:
    if isinstance(exc, ValueError):
        st.error(f"AI response could not be parsed as JSON (even after retry).\n\n{_JSON_ERR_HINT}")
    elif isinstance(exc, RuntimeError):
        st.error(str(exc))
    else:
        st.error(f"Unexpected error: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: run one generation (resume or cover letter) for a given job
# ─────────────────────────────────────────────────────────────────────────────
def _generate(
    job_id: int,
    kind: str,          # "resume" or "cl"
    job_desc: str,
    company_override: str,
    spinner_label: str,
) -> None:
    """
    Generate a tailored document for one job and store results in session_state.
    kind="resume" → uses resume template
    kind="cl"     → uses cover letter template
    """
    bytes_key   = f"j{kind}_bytes_{job_id}"
    preview_key = f"j{kind}_preview_{job_id}"

    tpl_bytes = _rt if kind == "resume" else _clt
    if not tpl_bytes:
        st.error("No template loaded.")
        return

    with st.spinner(spinner_label):
        try:
            base_text = extract_resume_text(load_docx(io.BytesIO(_br)))
            if not base_text.strip():
                st.error("No text found in base resume.")
                return

            tpl_doc = load_docx(io.BytesIO(tpl_bytes))
            tpl_ctx = get_template_context(tpl_doc)

            if kind == "resume":
                replacements = tailor_resume(base_text, job_desc, tpl_ctx, selected_model)
            else:
                replacements = generate_cover_letter(base_text, job_desc, tpl_ctx, selected_model)

            if not replacements:
                st.error("AI returned no replacements. Try a different model.")
                return

            out_doc = load_docx(io.BytesIO(tpl_bytes))
            apply_paragraph_replacements(out_doc, replacements)

            # Build per-job user info (override company name if provided)
            job_user_info = {
                "name":          user_name,
                "location":      user_location,
                "email":         user_email,
                "phone":         user_phone,
                "linkedin":      user_linkedin,
                "github":        user_github,
                "company":       company_override or default_company,
                "company_addr1": default_addr1,
                "company_addr2": default_addr2,
                "date":          default_date,
            }
            apply_user_info(out_doc, job_user_info)

            st.session_state[bytes_key]   = save_docx_to_bytes(out_doc)
            st.session_state[preview_key] = build_document_preview(out_doc)

        except Exception as exc:
            _gen_error(kind, exc)


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3 — Job Applications
# ─────────────────────────────────────────────────────────────────────────────
st.header("Step 3 — Job Applications")
st.caption(
    "Add one application per job. Each gets its own tailored resume and cover letter."
)

if not _br:
    st.warning("⬆️ Upload your **base resume** in Step 1 to enable generation.")

jobs = st.session_state["jobs"]

for i, job in enumerate(jobs):
    job_id = job["id"]

    # Per-job session state keys
    res_bytes_key   = f"jresume_bytes_{job_id}"
    res_preview_key = f"jresume_preview_{job_id}"
    cl_bytes_key    = f"jcl_bytes_{job_id}"
    cl_preview_key  = f"jcl_preview_{job_id}"
    for k in [res_bytes_key, res_preview_key, cl_bytes_key, cl_preview_key]:
        if k not in st.session_state:
            st.session_state[k] = None

    # ── Job card ──────────────────────────────────────────────────────────────
    with st.container(border=True):

        # Header row: job label + delete button
        hc1, hc2 = st.columns([6, 1])
        with hc1:
            label_val = st.text_input(
                "Job Title & Company  (for your reference)",
                placeholder="e.g. Software Engineer @ Acme Corp",
                key=f"jlabel_{job_id}",
            )
        with hc2:
            st.write("")  # vertical alignment nudge
            st.write("")
            if st.button("🗑️", key=f"jdel_{job_id}", help="Remove this application",
                         disabled=(len(jobs) == 1)):
                st.session_state["jobs"] = [j for j in jobs if j["id"] != job_id]
                # Clean up state for deleted job
                for k in [res_bytes_key, res_preview_key, cl_bytes_key, cl_preview_key,
                          f"jlabel_{job_id}", f"jdesc_{job_id}", f"jcompany_{job_id}"]:
                    st.session_state.pop(k, None)
                st.rerun()

        # Company override for cover letter
        company_val = st.text_input(
            "Company Name  (overrides default above)",
            placeholder="Leave blank to use default",
            key=f"jcompany_{job_id}",
        )

        # Job description
        desc_val = st.text_area(
            "Job Description",
            placeholder="Paste the full job posting — role title, responsibilities, requirements…",
            height=180,
            key=f"jdesc_{job_id}",
        )

        job_ready = bool(_br and _rt and _clt and desc_val.strip())

        # Generate buttons
        gc1, gc2 = st.columns(2, gap="medium")

        with gc1:
            if st.button(
                "✨ Tailor Resume",
                key=f"jbtn_res_{job_id}",
                disabled=(not job_ready or not creds_ok),
                use_container_width=True,
                type="primary",
            ):
                _generate(
                    job_id, "resume", desc_val, company_val,
                    f"Tailoring resume with **{selected_display}**…",
                )

        with gc2:
            if st.button(
                "✨ Cover Letter",
                key=f"jbtn_cl_{job_id}",
                disabled=(not job_ready or not creds_ok),
                use_container_width=True,
                type="primary",
            ):
                _generate(
                    job_id, "cl", desc_val, company_val,
                    f"Writing cover letter with **{selected_display}**…",
                )

        # ── Outputs ───────────────────────────────────────────────────────────
        has_resume = st.session_state[res_bytes_key] is not None
        has_cl     = st.session_state[cl_bytes_key]  is not None

        if has_resume or has_cl:
            out_c1, out_c2 = st.columns(2, gap="medium")

            with out_c1:
                if has_resume:
                    # Derive a sensible filename from the label
                    slug = (label_val or f"job_{job_id}").replace(" ", "_").replace("/", "-")[:40]
                    with st.expander("👁️ Resume Preview", expanded=False):
                        st.markdown(
                            f'<div class="preview-box">'
                            f'{st.session_state[res_preview_key]}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.download_button(
                        "⬇️ Download Resume",
                        data=st.session_state[res_bytes_key],
                        file_name=f"resume_{slug}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"jdl_res_{job_id}",
                    )

            with out_c2:
                if has_cl:
                    slug = (label_val or f"job_{job_id}").replace(" ", "_").replace("/", "-")[:40]
                    with st.expander("👁️ Cover Letter Preview", expanded=False):
                        st.markdown(
                            f'<div class="preview-box">'
                            f'{st.session_state[cl_preview_key]}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.download_button(
                        "⬇️ Download Cover Letter",
                        data=st.session_state[cl_bytes_key],
                        file_name=f"cover_letter_{slug}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"jdl_cl_{job_id}",
                    )

# ── Add job button ────────────────────────────────────────────────────────────
st.write("")
if st.button("➕ Add Another Job Application", use_container_width=False):
    new_id = st.session_state["next_job_id"]
    st.session_state["jobs"].append({"id": new_id})
    st.session_state["next_job_id"] = new_id + 1
    st.rerun()

st.divider()
st.markdown("""
<div style="text-align:center;color:#888;font-size:.8rem">
Built with Streamlit · python-docx · SAP AI Core &nbsp;|&nbsp;
🛡️ Honesty guardrail prevents AI hallucination
</div>
""", unsafe_allow_html=True)