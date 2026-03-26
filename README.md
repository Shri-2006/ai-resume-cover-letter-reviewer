# 📄 AI Resume Tailor & Cover Letter Generator

An AI-powered Streamlit web application that tailors your resume and writes
cover letters for any job posting — using **SAP AI Core** as the LLM backend
and **python-docx** for template injection, with a hardcoded **Honesty
Guardrail** that prevents the AI from fabricating any skills or experience.

**No template modifications needed.** Upload any `.docx` resume or cover
letter template as-is. The AI reads the document structure and fills in the
right paragraphs automatically. Built-in Stony Brook University templates are
bundled as defaults so the app works immediately with no template uploads
required.

**Multiple job applications per session.** Fill in your details once and
generate tailored resumes and cover letters for as many jobs as you want
without re-uploading anything.

---
Known Problems: It is horrible at creating resumes based on the template I have provided. 

## Live Demo

🚀 **[Try it here](https://ai-resume-cover-letter-reviewer-czvubpwu5qzozhypti4thk.streamlit.app/)**

---

## Project Structure

```
├── app.py                                   # Streamlit UI — main entry point
├── ai_utils.py                              # SAP AI Core REST calls + guardrail prompts
├── doc_utils.py                             # python-docx parsing & injection utilities
├── requirements.txt                         # Python dependencies
├── runtime.txt                              # Pins Python 3.12 for Streamlit Cloud
├── .env.example                             # Credential template (copy to .env)
├── README.md                                # This file
└── templates/
    ├── default_resume_template.docx         # Built-in Stony Brook resume template
    └── default_cover_letter_template.docx   # Built-in Stony Brook cover letter template
```

---

## How It Works

The app uses a **no-placeholder** approach. Instead of requiring special tokens
in your template, it sends the AI a numbered map of every paragraph:

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

The app applies those changes surgically — your name, section headers,
education, and all formatting are left untouched. After the AI pass, your
personal details (name, contact info, company, date, signature) are injected
via a second text-matching pass.

If the AI returns malformed JSON, the app **automatically retries once** with
a stricter JSON-only prompt before surfacing an error.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12 | 3.13 and 3.14 break `pydantic-core` on Streamlit Cloud |
| SAP BTP Account | Free tier works |
| SAP AI Core service instance | Orchestration scenario with at least one deployment |
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

### 4. Configure credentials

```bash
cp .env.example .env
```

These are the **same variable names** as your existing SAP AI Core chatbot.
Copy the values directly from your chatbot's environment:

```env
SAP_AUTH_URL=https://yoursubdomain.authentication.eu10.hana.ondemand.com/oauth/token
SAP_CLIENT_ID=sb-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx!b12345|aicore!b123
SAP_CLIENT_SECRET=xxxx
SAP_AI_API_URL=https://api.ai.eu10.aws.ml.hana.ondemand.com
RESOURCE_GROUP=default
SAP_DEPLOYMENT_ID=dxxxxxxxxxxxxxxx
```

`SAP_DEPLOYMENT_ID` is the only new variable — grab it from
**SAP AI Launchpad → ML Operations → Deployments** and copy the ID of any
RUNNING deployment (the same one your chatbot uses works fine).

### 5. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Using the App

### Workflow

| Step | What to do |
|---|---|
| **Step 1** | Upload your base resume (.docx). Optionally upload custom templates. |
| **Step 2** | Fill in your personal details — applied to every job you generate. |
| **Step 3** | Add one card per job. Paste each job description, click generate. |

### Step 1 — Documents

| Upload | Required? | Default if skipped |
|---|---|---|
| Base Resume (.docx) | ✅ Always required | — |
| Resume Template (.docx) | Optional | Built-in Stony Brook template |
| Cover Letter Template (.docx) | Optional | Built-in Stony Brook template |

### Step 2 — Your Details

Filled in once and applied to every job application you generate in the
session. All fields are optional — blank fields are simply omitted from the
output.

**Personal & Contact Information:**
- Full Name
- Location (e.g. New York, NY)
- Email
- Phone
- LinkedIn URL
- GitHub URL

**Cover Letter — Company & Date:**
- Default Company Name (can be overridden per job in Step 3)
- Company Address (optional)
- City, State ZIP (optional)
- Letter Date (pre-filled to today's date)

The contact line in generated documents is built from whichever fields you
fill in, separated by `|`:

```
New York, NY | jane@email.com | (555) 123-4567 | linkedin.com/in/janedoe | github.com/janedoe
```

### Step 3 — Job Applications

Each job card contains:
- A label field for your own reference (e.g. "Software Engineer @ Acme")
- A company name override for the cover letter header
- The job description text area
- **✨ Tailor Resume** and **✨ Cover Letter** buttons — independent, run either or both
- Preview expanders showing the fully populated document
- Download buttons with filenames derived from the job label

Click **➕ Add Another Job Application** to add as many jobs as you need.
Previously generated documents persist in the session — generating a new job
does not affect existing ones.

### Template requirements

No modifications needed. The AI recognises placeholder content like
"Organization/Company Name", "Skill based bullet #1",
"Section One: Briefly introduce yourself…" and replaces them with real content
from your base resume. It will never touch your name, contact info, section
headers, education section, or cover letter salutation and sign-off.

---

## Available Models (47 total)

The default is **GPT-5.2**. The full list is available in the sidebar dropdown:

| Provider | Models |
|---|---|
| **OpenAI** | GPT-5.2 ⭐, GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano, GPT-4o, GPT-4o Mini, o1, o3, o3-mini, o4-mini |
| **Anthropic** | Claude 4.6 Sonnet/Opus, Claude 4.5 Sonnet/Opus/Haiku, Claude 4 Sonnet/Opus, Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude 3 Haiku |
| **Google** | Gemini 3 Pro Preview, Gemini 2.5 Pro/Flash/Flash-Lite, Gemini 2.0 Flash/Flash-Lite |
| **Amazon** | Nova Premier, Nova Pro, Nova Lite, Nova Micro |
| **Mistral AI** | Mistral Large, Mistral Medium, Mistral Small |
| **Meta** | Llama 3 70B |
| **DeepSeek** | DeepSeek R1 0528, DeepSeek V3.2 |
| **Qwen (Alibaba)** | Qwen3 Max, Qwen3.5 Plus, Qwen Turbo, Qwen Flash |
| **Perplexity** | Sonar Pro, Sonar, Sonar Deep Research |
| **Cohere** | Command A Reasoning |

**Recommended for best results:** GPT-5.2, GPT-4.1, Claude 3.5 Sonnet, or
Gemini 2.5 Flash — fast, instruction-following, and reliable JSON output.

**Notes on specific models:**
- **Temperature is not sent** for any model — it caused errors on GPT-5 and
  o-series and is not needed; the system prompts provide sufficient guidance
- **o1 / o3 / o4-mini** — reasoning models, slower; may occasionally format
  output differently
- **Sonar Deep Research** — performs live web searches, very slow
- **GPT-5** — currently intermittent on SAP AI Core; use GPT-5.2 instead

---

## Honesty Guardrail

System prompts in `ai_utils.py` are hardcoded constants sent on every call:

**Resume:** The AI is forbidden from inventing skills, metrics, job titles,
degrees, or experience not explicitly in the base resume. It reframes and
reorders existing content to match the job description keywords — nothing more.

**Cover letter:** Uses only facts from the base resume. No fabricated
anecdotes, no generic AI filler openings.

---

## Deploying to Streamlit Community Cloud (free)

1. Push the full repo to GitHub — confirm `.env` is in `.gitignore`
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

5. Deploy — `runtime.txt` pins Python 3.12 to avoid the `pydantic-core` Rust
   build failure on Python 3.14.

> **Important:** The `templates/` folder must be committed to the repo.
> Streamlit Cloud has no persistent filesystem, so the bundled default
> templates must ship with the code.

---

## Security Notes

- **Never commit `.env`** — already in `.gitignore`
- `.env.example` contains only placeholder values and is safe to commit
- The app does not log, store, or transmit your resume content anywhere beyond
  the SAP AI Core API call
- SAP AI Core processes data within the SAP BTP trust boundary
- File bytes are held only in Streamlit session state (in-memory, per-session)

---

## License

MIT — free to use, modify, and distribute.
