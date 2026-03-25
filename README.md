# 📄 AI Resume Tailor & Cover Letter Generator
Live Demo:https://ai-resume-cover-letter-reviewer-czvubpwu5qzozhypti4thk.streamlit.app/  

An AI-powered Streamlit web application that tailors your resume and writes a
cover letter for any job posting — using **SAP AI Core** as the LLM backend
and **python-docx** for template injection, with a hardcoded **"Honesty
Guardrail"** that prevents the AI from fabricating any skills or experience.

---

## Project Structure

```
resume_tailor/
├── app.py              # Streamlit UI – main entry point
├── ai_utils.py         # SAP AI Core SDK calls + guardrail prompts
├── doc_utils.py        # python-docx parse & template injection utilities
├── requirements.txt    # All Python dependencies
├── .env.example        # Credential template (copy to .env)
└── README.md           # This file
```

---

## How It Works

```
User uploads                  AI reads                  AI writes
┌───────────────┐    text     ┌───────────┐   tailored  ┌────────────────┐
│  Base Resume  │ ──────────► │ SAP AI    │ ──────────► │ Resume Body    │
│  (.docx)      │             │ Core LLM  │             │ (plain text)   │
└───────────────┘             │           │             └────────┬───────┘
                              │  Honesty  │                      │ inject
User uploads                  │ Guardrail │                      ▼
┌───────────────┐    text     │ (always   │             ┌────────────────┐
│Resume Template│ ──────────► │ on)       │             │{{TAILORED_EXP}}│
│ (.docx)       │             │           │             │ → replaced in  │
└───────────────┘             └───────────┘             │   template     │
                                                        └────────┬───────┘
                                                                 │
                                                        ┌────────▼───────┐
                                                        │ Download .docx │
                                                        └────────────────┘
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | Tested on 3.11 |
| SAP BTP Account | Free tier works |
| SAP AI Core service instance | With at least one LLM deployment |
| SAP AI Core service key | Download from BTP Cockpit |

---

## Installation & Setup

### 1. Clone / download the project

```bash
git clone <your-repo-url>
cd resume_tailor
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows (cmd)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure SAP AI Core credentials

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in the five values from your SAP AI
Core **service key** JSON (downloadable from BTP Cockpit):

```
BTP Cockpit
  └── Services → Instances & Subscriptions
        └── AI Core instance
              └── Service Keys → your-key.json
```

The JSON looks like this:

```json
{
  "clientid":     "sb-xxxx!bxxxx|aicore!bxxx",     → AICORE_CLIENT_ID
  "clientsecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", → AICORE_CLIENT_SECRET
  "url":          "https://xxx.authentication.eu10.hana.ondemand.com", → base of AICORE_AUTH_URL
  "serviceurls": {
    "AI_API_URL": "https://api.ai.eu10.aws.ml.hana.ondemand.com"  → AICORE_BASE_URL
  }
}
```

> **AICORE_AUTH_URL** = `url` field + `/oauth/token`
>
> Example: `https://mysubdomain.authentication.eu10.hana.ondemand.com/oauth/token`

Your completed `.env` should look like:

```env
AICORE_AUTH_URL=https://mysubdomain.authentication.eu10.hana.ondemand.com/oauth/token
AICORE_CLIENT_ID=sb-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx!b12345|aicore!b123
AICORE_CLIENT_SECRET=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789==
AICORE_BASE_URL=https://api.ai.eu10.aws.ml.hana.ondemand.com
AICORE_RESOURCE_GROUP=default
```

### 5. Verify your AI Core deployments

The model names in the sidebar dropdown must match the **deployment names**
configured in your SAP AI Core resource group.  Check them via:

```bash
# Using the AI Core Python SDK
python - <<'EOF'
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
client = get_proxy_client('gen-ai-hub')
# List available deployments through your resource group
EOF
```

Or check the **SAP AI Launchpad** → ML Operations → Deployments.

Default model IDs in the app:

| UI Label | Deployment ID |
|---|---|
| GPT-4o | `gpt-4o` |
| GPT-4o Mini | `gpt-4o-mini` |
| Claude 3.5 Sonnet | `claude-3-5-sonnet` |
| Claude 3 Opus | `claude-3-opus` |
| Gemini 1.5 Pro | `gemini-1.5-pro` |
| Mistral Large | `mistral-large-instruct` |
| Qwen 2.5 72B | `qwen2-5-72b-instruct` |

To add or change a model, edit the `AVAILABLE_MODELS` dict in `ai_utils.py`.

### 6. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Preparing Your .docx Templates

### Resume Template

Create a `.docx` file with your preferred formatting (fonts, header with your
name/contact info, section titles, etc.).  Place the token:

```
{{TAILORED_EXPERIENCE}}
```

exactly where you want the AI-generated professional summary + experience
bullets + skills section to appear.  The app will replace this token with the
tailored content while leaving everything else in the document untouched.

**Example layout:**

```
[Your Name]                          [Phone | Email | LinkedIn]
────────────────────────────────────────────────────────────────

{{TAILORED_EXPERIENCE}}

EDUCATION
  Bachelor of Science in Computer Science, XYZ University, 20XX
```

### Cover Letter Template

Same idea — include your letterhead, date, addressee block, salutation
("Dear Hiring Team,"), and sign-off.  Place:

```
{{COVER_LETTER_BODY}}
```

between the salutation and the closing.

**Example layout:**

```
[Your Name]
[Address | Date]

Hiring Team
[Company Name]

Dear Hiring Team,

{{COVER_LETTER_BODY}}

Sincerely,
[Your Name]
```

---

## Honesty Guardrail (Anti-Hallucination)

The following system prompts are **hardcoded** in `ai_utils.py` and cannot be
overridden by the user interface:

**For resumes:**
> "You are an ethical resume tailor. You are strictly forbidden from inventing,
> assuming, or adding any skills, metrics, job titles, degrees, or experiences
> not explicitly stated in the Base Resume. Reframe and reorder bullets to match
> the Target Job Description keywords, but do not fabricate. If the job requires
> a skill the candidate lacks, do not add it."

**For cover letters:**
> "Write a 3-paragraph cover letter for the Target Job Description using ONLY
> facts from the Base Resume. Do not use filler or robotic AI openings. Do not
> invent anecdotes."

Additionally, `temperature` is set to **0.2** for resume tailoring and **0.35**
for cover letters to reduce sampling randomness and further suppress fabrication.

---

## Extending the App

### Adding a new model

```python
# ai_utils.py  →  AVAILABLE_MODELS dict
AVAILABLE_MODELS = {
    ...
    "Llama 3 70B  (Meta)": "meta-llama3-70b-instruct",   # add this line
}
```

### Adding a new placeholder

```python
# In app.py, after calling replace_placeholder for existing tokens:
replace_placeholder(doc, "{{EDUCATION}}", ai_generated_education)
```

### Deploying to Streamlit Community Cloud (free)

1. Push this repo to GitHub (make sure `.env` is in `.gitignore`).
2. Go to https://share.streamlit.io → "New app".
3. Add your SAP AI Core credentials as **Secrets** in the Streamlit dashboard
   (Settings → Secrets) using the same key names as in `.env`.
   The `load_dotenv()` call gracefully no-ops when env vars are already set.

---

## Security Notes

- **Never commit `.env`** to version control.
- The `.env.example` file contains only placeholder values — it is safe to commit.
- The app does **not** log, cache, or transmit your resume content anywhere
  beyond the SAP AI Core API call.
- SAP AI Core processes data within the SAP BTP trust boundary.

---

## License

MIT — free to use, modify, and distribute.
