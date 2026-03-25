# ─────────────────────────────────────────────────────────────────────────────
#  ai_utils.py
#
#  Module for all SAP AI Core / Generative AI Hub SDK interactions.
#
#  Responsibilities
#  ────────────────
#  • Validate that the required environment variables are set.
#  • Provide a thin, model-agnostic ``call_model()`` wrapper that routes
#    requests to the correct SDK client based on the model name prefix.
#  • Expose two domain-specific functions:
#      – ``tailor_resume()``       → produces a rewritten resume body
#      – ``generate_cover_letter()`` → produces a 3-paragraph cover letter
#  • Enforce the "Honesty Guardrail" system prompts so the AI cannot
#    hallucinate skills, experiences, or credentials not in the base resume.
#
#  SAP AI Core SDK primer
#  ──────────────────────
#  The ``generative-ai-hub-sdk`` package provides proxy clients that
#  transparently route requests through SAP AI Core's unified LLM gateway.
#  It reads credentials from environment variables automatically:
#
#    AICORE_AUTH_URL        – OAuth token endpoint
#    AICORE_CLIENT_ID       – OAuth client ID
#    AICORE_CLIENT_SECRET   – OAuth client secret
#    AICORE_BASE_URL        – AI API base URL
#    AICORE_RESOURCE_GROUP  – Resource group (usually "default")
#
#  Model routing
#  ─────────────
#  SAP AI Core exposes all models through OpenAI-compatible Chat Completions
#  endpoints via its proxy.  We therefore use a single ``OpenAI``-style proxy
#  client for every model family (GPT, Claude, Gemini, Mistral, Qwen …).
#  The ``model`` parameter in the API call maps to the *deployment name*
#  configured inside your SAP AI Core resource group.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
from typing import Optional

# ── Lazy import guard ─────────────────────────────────────────────────────────
# We wrap SDK imports in a try/except so the module can be imported even when
# the package is not yet installed (useful during development / linting).
try:
    from gen_ai_hub.proxy.native.openai import OpenAI as AICoreOpenAI  # type: ignore
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
#  Model catalogue shown in the Streamlit sidebar
#  Keys  → display label in the UI
#  Values → exact deployment / model name sent to SAP AI Core
# ─────────────────────────────────────────────────────────────────────────────
AVAILABLE_MODELS: dict[str, str] = {
    "GPT-4o  (OpenAI)":                  "gpt-4o",
    "GPT-4o Mini  (OpenAI)":             "gpt-4o-mini",
    "Claude 3.5 Sonnet  (Anthropic)":    "claude-3-5-sonnet",
    "Claude 3 Opus  (Anthropic)":        "claude-3-opus",
    "Gemini 1.5 Pro  (Google)":          "gemini-1.5-pro",
    "Mistral Large  (Mistral AI)":       "mistral-large-instruct",
    "Qwen 2.5 72B  (Alibaba)":           "qwen2-5-72b-instruct",
}

# ─────────────────────────────────────────────────────────────────────────────
#  Honesty guardrail system prompts  (hardcoded – must never be overridden)
# ─────────────────────────────────────────────────────────────────────────────

_RESUME_SYSTEM_PROMPT = """
You are an ethical resume tailor. You are strictly forbidden from inventing,
assuming, or adding any skills, metrics, job titles, degrees, or experiences
not explicitly stated in the Base Resume. Reframe and reorder bullets to match
the Target Job Description keywords, but do not fabricate. If the job requires
a skill the candidate lacks, do not add it.

Output format:
- Return ONLY the tailored resume body text (experience, skills, summary).
- Use clear section headers in ALL CAPS (e.g., PROFESSIONAL SUMMARY, EXPERIENCE, SKILLS).
- Each job entry: Company | Title | Dates, followed by bullet points starting with "•".
- Keep bullets concise, action-verb-led, and keyword-aligned to the job description.
- Do NOT include contact information or the candidate's name — the template handles that.
""".strip()

_COVER_LETTER_SYSTEM_PROMPT = """
Write a 3-paragraph cover letter for the Target Job Description using ONLY facts
from the Base Resume. Do not use filler or robotic AI openings such as
"I am writing to express my interest". Do not invent anecdotes, projects, or
skills. Do not fabricate metrics.

Output format:
- Return ONLY the 3 paragraphs of body text, separated by blank lines.
- Paragraph 1: Hook — why this specific role at this specific company excites
  the candidate, grounded in something real from their background.
- Paragraph 2: Evidence — 2-3 concrete examples from the Base Resume that map
  directly to the job's requirements.
- Paragraph 3: Close — confident call to action; no desperate or overly formal
  language.
- Do NOT include salutation ("Dear Hiring Manager"), sign-off ("Sincerely"),
  or placeholders — the template handles those.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Credential validation
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_ENV_VARS = [
    "AICORE_AUTH_URL",
    "AICORE_CLIENT_ID",
    "AICORE_CLIENT_SECRET",
    "AICORE_BASE_URL",
    "AICORE_RESOURCE_GROUP",
]


def validate_credentials() -> tuple[bool, list[str]]:
    """
    Check that all required SAP AI Core environment variables are present and
    non-empty.

    Returns
    -------
    (bool, list[str])
        ``(True, [])`` if all variables are set;
        ``(False, [missing_var, ...])`` otherwise.
    """
    missing = [v for v in _REQUIRED_ENV_VARS if not os.getenv(v)]
    return (len(missing) == 0), missing


# ─────────────────────────────────────────────────────────────────────────────
#  Core model call
# ─────────────────────────────────────────────────────────────────────────────

def call_model(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2500,
    temperature: float = 0.25,
) -> str:
    """
    Send a chat completion request to SAP AI Core via the Generative AI Hub SDK.

    The SAP proxy exposes all configured model deployments through an
    OpenAI-compatible Chat Completions API, so we use a single client class
    regardless of the underlying model family (GPT, Claude, Gemini, …).

    Parameters
    ----------
    model_name : str
        The SAP AI Core deployment / model name (e.g. ``"gpt-4o"``).
    system_prompt : str
        The hardcoded guardrail instruction for the AI.
    user_prompt : str
        The user-side prompt containing the resume text and job description.
    max_tokens : int
        Maximum tokens in the completion response (default 2500).
    temperature : float
        Sampling temperature.  Low values (0.1–0.3) reduce hallucination risk
        for factual rewriting tasks.

    Returns
    -------
    str
        The AI-generated text content.

    Raises
    ------
    RuntimeError
        If the SDK is not installed or credentials are missing.
    Exception
        Propagates any API-level errors for the caller to handle.
    """
    if not _SDK_AVAILABLE:
        raise RuntimeError(
            "The 'generative-ai-hub-sdk' package is not installed. "
            "Run:  pip install generative-ai-hub-sdk"
        )

    ok, missing = validate_credentials()
    if not ok:
        raise RuntimeError(
            f"Missing SAP AI Core environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in your credentials."
        )

    # The SAP proxy client auto-reads credentials from env vars.
    # A new client instance per call avoids stale token issues in long sessions.
    client = AICoreOpenAI()

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # Extract and return the text content
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Domain-specific AI functions
# ─────────────────────────────────────────────────────────────────────────────

def tailor_resume(
    base_resume_text: str,
    job_description: str,
    model_name: str,
) -> str:
    """
    Use the AI to rewrite / reorder the candidate's resume content so it
    optimally targets the given job description — without adding anything not
    already present in the base resume.

    Parameters
    ----------
    base_resume_text : str
        Full plain-text content of the candidate's base resume.
    job_description : str
        The target job posting text pasted by the user.
    model_name : str
        SAP AI Core deployment name selected in the sidebar.

    Returns
    -------
    str
        Tailored resume body text ready for template injection.
    """
    user_prompt = f"""
=== BASE RESUME ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Task: Rewrite the Base Resume body (summary, experience bullets, skills section)
so it is optimally aligned with the Target Job Description. Follow every rule
in your system instructions. Return ONLY the tailored resume content.
""".strip()

    return call_model(
        model_name=model_name,
        system_prompt=_RESUME_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=2500,
        temperature=0.2,   # low temp for factual rewriting
    )


def generate_cover_letter(
    base_resume_text: str,
    job_description: str,
    model_name: str,
) -> str:
    """
    Generate a 3-paragraph cover letter body grounded exclusively in facts from
    the candidate's base resume.

    Parameters
    ----------
    base_resume_text : str
        Full plain-text content of the candidate's base resume.
    job_description : str
        The target job posting text.
    model_name : str
        SAP AI Core deployment name selected in the sidebar.

    Returns
    -------
    str
        Cover letter body text (3 paragraphs) ready for template injection.
    """
    user_prompt = f"""
=== BASE RESUME ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Task: Write a 3-paragraph cover letter body following your system instructions.
Use ONLY facts found in the Base Resume. Return ONLY the 3 paragraphs of text.
""".strip()

    return call_model(
        model_name=model_name,
        system_prompt=_COVER_LETTER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=800,
        temperature=0.35,  # slightly higher for natural-sounding prose
    )