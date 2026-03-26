# 📄 AI Resume Tailor & Cover Letter Generator

An AI-powered Streamlit web application that tailors your resume and writes a
cover letter for any job posting — using **SAP AI Core** as the LLM backend
and **python-docx** for template injection, with a hardcoded **Honesty Guardrail**
that prevents the AI from fabricating any skills or experience.

**No template modifications needed.** Upload any `.docx` resume or cover letter
template as-is. The AI reads the document structure and fills in the right
paragraphs automatically. Built-in Stony Brook University templates are bundled
as defaults so the app works immediately with no uploads required.

---

## Project Structure

```
├── app.py                          # Streamlit UI — main entry point
├── ai_utils.py                     # SAP AI Core SDK calls + guardrail prompts
├── doc_utils.py                    # python-docx parsing & paragraph injection
├── requirements.txt                # Python dependencies
├── runtime.txt                     # Pins Python 3.12 for Streamlit Cloud
├── .env.example                    # Credential template (copy to .env)
├── README.md                       # This file
└── templates/
    ├── default_resume_template.docx       # Built-in fallback resume template
    └── default_cover_letter_template.docx # Built-in fallback cover letter template
```

---

## How It Works

The app takes a **no-placeholder** approach. Instead of requiring you to embed
special tokens in your template, it sends the AI a numbered map of every
paragraph in the document:

```
[0]  Wolfie Seawolf
[1]  Town, State | email | phone
[3]  EDUCATION
[10] PROFESSIONAL EXPERIENCE
[11] Organization/Company Name    Town, State
[12] Position Name    Start – End
[13] Skill based bullet #1
...
```

The AI reads this map alongside your base resume and the job description, then
returns a JSON object specifying exactly which paragraphs to rewrite:

```json
{
  "replacements": {
    "11": "Acme Corp    New York, NY",
    "12": "Software Engineer    Jun 2023 – Present",
    "13": "Built REST APIs serving 50k daily requests using Python and FastAPI",
    "14": "Reduced deployment time 60% by containerising services with Docker"
  }
}
```

The app applies those replacements surgically — untouched paragraphs (your name,
section headers, education, formatting) are never modified.

```
Base Resume (.docx)  ──┐
                        ├──► SAP AI Core LLM ──► JSON replacements ──► Modified template (.docx)
Job Description  ───────┘         │
                                  │ Honesty Guardrail
Template (.docx) ──► paragraph    │ (hardcoded, always on)
                     index map ───┘
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12 | 3.13 and 3.14 break `pydantic-core` on Streamlit Cloud |
| SAP BTP Account | Free tier works |
| SAP AI Core service instance | With at least one LLM deployment active |
| SAP AI Core service key | Download from BTP Cockpit |

---

## Installation & Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd <repo-folder>
```

### 2. Create a virtual environment

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

These are the **same variable names** your existing SAP chatbot uses — copy the
values directly from your chatbot's environment:

```env
SAP_AUTH_URL=https://yoursubdomain.authentication.eu10.hana.ondemand.com/oauth/token
SAP_CLIENT_ID=sb-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx!b12345|aicore!b123
SAP_CLIENT_SECRET=xxxx
SAP_AI_API_URL=https://api.ai.eu10.aws.ml.hana.ondemand.com
RESOURCE_GROUP=default
SAP_DEPLOYMENT_ID=dxxxxxxxxxxxxxxx
```

`SAP_DEPLOYMENT_ID` is the one new variable — grab it from
**SAP AI Launchpad → ML Operations → Deployments** and copy the ID of any
RUNNING deployment (the same one your chatbot uses works fine).

### 5. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Using the App

### Minimum required uploads

| Field | Required? | Default if skipped |
|---|---|---|
| Base Resume (.docx) | ✅ Always required | — |
| Resume Template (.docx) | Optional | Stony Brook template |
| Cover Letter Template (.docx) | Optional | Stony Brook template |

The app ships with built-in Stony Brook University resume and cover letter
templates. You only need to upload your own templates if you want a different
layout or design. The sidebar will show **"✅ Using the built-in Stony Brook
template"** when the default is active.

### Workflow

1. Upload your **base resume** (your master resume with all your experience)
2. Optionally upload custom **.docx templates** — or use the built-in defaults
3. Paste the **job description** you're targeting
4. Select a **model** from the sidebar
5. Click **✨ Tailor My Resume** and/or **✨ Generate Cover Letter**
6. Preview the AI-generated content, then download the populated `.docx`

### Template requirements

Your templates need no special modifications. The AI recognises placeholder
content like "Organization/Company Name", "Skill based bullet #1",
"Section One: Briefly introduce yourself…", etc. and replaces them with
real content from your base resume.

**What the AI will replace:** job entries, role names, dates, bullet points,
skills lines, and cover letter body paragraphs.

**What the AI will never touch:** your name, contact info, section headers
(EDUCATION, PROFESSIONAL EXPERIENCE, etc.), education details, blank spacer
paragraphs, and your cover letter salutation/sign-off.

---

## Available Models (47 total)

The sidebar dropdown lists all 47 models available through SAP AI Core:

| Provider | Models |
|---|---|
| **OpenAI** | GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-5.2, GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano, GPT-4o, GPT-4o Mini, o1, o3, o3-mini, o4-mini |
| **Anthropic** | Claude 4.6 Sonnet/Opus, Claude 4.5 Sonnet/Opus/Haiku, Claude 4 Sonnet/Opus, Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude 3 Haiku |
| **Google** | Gemini 3 Pro Preview, Gemini 2.5 Pro/Flash/Flash-Lite, Gemini 2.0 Flash/Flash-Lite |
| **Amazon** | Nova Premier, Nova Pro, Nova Lite, Nova Micro |
| **Mistral AI** | Mistral Large, Mistral Medium, Mistral Small |
| **Meta** | Llama 3 70B |
| **DeepSeek** | DeepSeek R1 0528, DeepSeek V3.2 |
| **Qwen (Alibaba)** | Qwen3 Max, Qwen3.5 Plus, Qwen Turbo, Qwen Flash |
| **Perplexity** | Sonar Pro, Sonar, Sonar Deep Research |
| **Cohere** | Command A Reasoning |

**Recommended models for this use case:** GPT-4.1, Claude 3.5 Sonnet,
Claude 4.5 Sonnet, or Gemini 2.5 Flash — all are fast, instruction-following,
and good at structured JSON output.

**Notes on specific models:**
- **o1 / o3 / o4-mini** — reasoning models that think before responding. May
  be slower and occasionally format JSON differently; if you see a parse error,
  switch to a non-reasoning model.
- **Sonar Deep Research** — performs live web searches before responding. Very
  slow and overkill for resume tailoring.
- **sap-abap-1** — SAP ABAP code model, intentionally excluded from the list.

To add or update a model, edit the `AVAILABLE_MODELS` dict in `ai_utils.py`:

```python
AVAILABLE_MODELS = {
    "My New Model  (Provider)": "exact-deployment-name",
    ...
}
```

---

## Honesty Guardrail

The system prompts in `ai_utils.py` are hardcoded constants — they cannot be
changed through the UI and are sent on every API call:

**Resume tailoring system prompt (abridged):**
> You are an ethical resume tailor. You are strictly forbidden from inventing,
> assuming, or adding any skills, metrics, job titles, degrees, or experiences
> not explicitly present in the Base Resume. Reframe and reorder bullets to
> match the job description keywords, but do not fabricate. If the job requires
> a skill the candidate lacks, do not add it.

**Cover letter system prompt (abridged):**
> Use ONLY facts from the Base Resume. Do not invent anecdotes, fabricate
> metrics, or use generic filler openings. Write exactly 3 body paragraphs.

Temperature is set to **0.2** for resume tailoring and **0.3** for cover
letters to minimise sampling randomness and further suppress hallucination.

---

## Live Demo

🚀 **[Try it here](https://ai-resume-cover-letter-reviewer-czvubpwu5qzozhypti4thk.streamlit.app/)**

---

## Deploying to Streamlit Community Cloud (free)

1. Push the full repo to GitHub — make sure `.env` is in `.gitignore`
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Point it at your repo, branch `main`, main file `app.py`
4. Go to **Settings → Secrets** and add your credentials in TOML format:

```toml
SAP_AUTH_URL = "https://yoursubdomain.authentication.eu10.hana.ondemand.com/oauth/token"
SAP_CLIENT_ID = "sb-xxxx"
SAP_CLIENT_SECRET = "xxxx"
SAP_AI_API_URL = "https://api.ai.eu10.aws.ml.hana.ondemand.com"
RESOURCE_GROUP = "default"
SAP_DEPLOYMENT_ID = "dxxxxxxxxxxxxxxx"
```

5. Deploy — Streamlit reads `runtime.txt` to use Python 3.12, which avoids
   the `pydantic-core` Rust build failure that occurs on Python 3.14.

> **Important:** The `templates/` folder must be committed to the repo.
> Streamlit Cloud has no persistent filesystem, so the bundled templates
> must ship with the code.

---

## Security Notes

- **Never commit `.env`** — it's already in `.gitignore`
- `.env.example` contains only placeholder values and is safe to commit
- The app does not log, store, or transmit your resume content anywhere
  beyond the SAP AI Core API call
- SAP AI Core processes data within the SAP BTP trust boundary
- File bytes are held only in Streamlit session state (in-memory, per-session)

---

## License

MIT — free to use, modify, and distribute.