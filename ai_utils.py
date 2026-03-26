# ─────────────────────────────────────────────────────────────────────────────
#  ai_utils.py  –  SAP AI Core calls, no-placeholder approach
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import json, os, re

try:
    from gen_ai_hub.proxy.native.openai import OpenAI as AICoreOpenAI
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

# ── Model catalogue ───────────────────────────────────────────────────────────
AVAILABLE_MODELS: dict[str, str] = {
    # ── OpenAI ────────────────────────────────────────────────────────────────
    "GPT-5  (OpenAI)":                    "gpt-5",
    "GPT-5 Mini  (OpenAI)":               "gpt-5-mini",
    "GPT-5 Nano  (OpenAI)":               "gpt-5-nano",
    "GPT-5.2  (OpenAI)":                  "gpt-5.2",
    "GPT-4.1  (OpenAI)":                  "gpt-4.1",
    "GPT-4.1 Mini  (OpenAI)":             "gpt-4.1-mini",
    "GPT-4.1 Nano  (OpenAI)":             "gpt-4.1-nano",
    "GPT-4o  (OpenAI)":                   "gpt-4o",
    "GPT-4o Mini  (OpenAI)":              "gpt-4o-mini",
    "o1  (OpenAI)":                       "o1",
    "o3  (OpenAI)":                       "o3",
    "o3 Mini  (OpenAI)":                  "o3-mini",
    "o4 Mini  (OpenAI)":                  "o4-mini",
    # ── Anthropic ─────────────────────────────────────────────────────────────
    "Claude 4.6 Sonnet  (Anthropic)":     "anthropic--claude-4.6-sonnet",
    "Claude 4.6 Opus  (Anthropic)":       "anthropic--claude-4.6-opus",
    "Claude 4.5 Sonnet  (Anthropic)":     "anthropic--claude-4.5-sonnet",
    "Claude 4.5 Opus  (Anthropic)":       "anthropic--claude-4.5-opus",
    "Claude 4.5 Haiku  (Anthropic)":      "anthropic--claude-4.5-haiku",
    "Claude 4 Sonnet  (Anthropic)":       "anthropic--claude-4-sonnet",
    "Claude 4 Opus  (Anthropic)":         "anthropic--claude-4-opus",
    "Claude 3.7 Sonnet  (Anthropic)":     "anthropic--claude-3.7-sonnet",
    "Claude 3.5 Sonnet  (Anthropic)":     "anthropic--claude-3.5-sonnet",
    "Claude 3 Haiku  (Anthropic)":        "anthropic--claude-3-haiku",
    # ── Google ────────────────────────────────────────────────────────────────
    "Gemini 3 Pro Preview  (Google)":     "gemini-3-pro-preview",
    "Gemini 2.5 Pro  (Google)":           "gemini-2.5-pro",
    "Gemini 2.5 Flash  (Google)":         "gemini-2.5-flash",
    "Gemini 2.5 Flash Lite  (Google)":    "gemini-2.5-flash-lite",
    "Gemini 2.0 Flash  (Google)":         "gemini-2.0-flash",
    "Gemini 2.0 Flash Lite  (Google)":    "gemini-2.0-flash-lite",
    # ── Amazon ────────────────────────────────────────────────────────────────
    "Nova Premier  (Amazon)":             "amazon--nova-premier",
    "Nova Pro  (Amazon)":                 "amazon--nova-pro",
    "Nova Lite  (Amazon)":                "amazon--nova-lite",
    "Nova Micro  (Amazon)":               "amazon--nova-micro",
    # ── Mistral AI ────────────────────────────────────────────────────────────
    "Mistral Large  (Mistral AI)":        "mistralai--mistral-large-instruct",
    "Mistral Medium  (Mistral AI)":       "mistralai--mistral-medium-instruct",
    "Mistral Small  (Mistral AI)":        "mistralai--mistral-small-instruct",
    # ── Meta ──────────────────────────────────────────────────────────────────
    "Llama 3 70B  (Meta)":                "meta--llama3-70b-instruct",
    # ── DeepSeek ──────────────────────────────────────────────────────────────
    "DeepSeek R1 0528  (DeepSeek)":       "deepseek-r1-0528",
    "DeepSeek V3.2  (DeepSeek)":          "deepseek-v3.2",
    # ── Qwen ──────────────────────────────────────────────────────────────────
    "Qwen3 Max  (Alibaba)":               "qwen3-max",
    "Qwen3.5 Plus  (Alibaba)":            "qwen3.5-plus",
    "Qwen Turbo  (Alibaba)":              "qwen-turbo",
    "Qwen Flash  (Alibaba)":              "qwen-flash",
    # ── Perplexity ────────────────────────────────────────────────────────────
    "Sonar Pro  (Perplexity)":            "sonar-pro",
    "Sonar  (Perplexity)":                "sonar",
    "Sonar Deep Research  (Perplexity)":  "sonar-deep-research",
    # ── Cohere ────────────────────────────────────────────────────────────────
    "Command A Reasoning  (Cohere)":      "cohere--command-a-reasoning",
}

# ── Credential check ─────────────────────────────────────────────────────────
_REQUIRED = [
    "AICORE_AUTH_URL", "AICORE_CLIENT_ID", "AICORE_CLIENT_SECRET",
    "AICORE_BASE_URL", "AICORE_RESOURCE_GROUP",
]

def validate_credentials() -> tuple[bool, list[str]]:
    missing = [v for v in _REQUIRED if not os.getenv(v)]
    return (len(missing) == 0), missing

# ── Honesty guardrails (hardcoded, never overrideable) ────────────────────────
_RESUME_SYSTEM = """
You are an ethical resume tailor. You are strictly forbidden from inventing,
assuming, or adding any skills, metrics, job titles, degrees, or experiences
not explicitly present in the Base Resume provided by the user.

Your job is to rewrite and reorder the content of the provided resume TEMPLATE
so it targets the given Job Description — using ONLY facts from the Base Resume.

OUTPUT FORMAT — you must return ONLY a valid JSON object, no markdown, no explanation:
{
  "replacements": {
    "PARAGRAPH_INDEX": "replacement text",
    "PARAGRAPH_INDEX": "replacement text"
  }
}

Rules for which paragraph indices to include:
- Replace experience company/org name lines with REAL entries from the base resume.
- Replace position/role name lines with REAL roles from the base resume.
- Replace date lines with REAL dates from the base resume.
- Replace all "Skill based bullet" lines and sample bullet text with REAL, tailored bullets.
- Replace the skills section lines (Computer:, Language:, Certifications:) with real values.
- For cover letters: replace the Section One/Two/Three body paragraphs only.
- Do NOT replace: the candidate name, contact info line, section headers (EDUCATION, 
  PROFESSIONAL EXPERIENCE, etc.), or blank spacer paragraphs.
- If the base resume has fewer jobs than template slots, set unused slots to empty string "".
- Never add skills or experience the candidate does not have.
- Use \\n inside a string value to represent multiple bullet lines for one slot.
""".strip()

_COVER_LETTER_SYSTEM = """
You are an ethical cover letter writer. Use ONLY facts from the Base Resume.
Do not invent anecdotes, fabricate metrics, or use generic filler openings.

OUTPUT FORMAT — return ONLY a valid JSON object, no markdown, no explanation:
{
  "replacements": {
    "PARAGRAPH_INDEX": "paragraph text"
  }
}

Write exactly 3 body paragraphs (one per Section slot):
- Paragraph 1: Hook — why this specific role/company excites the candidate,
  grounded in something real from their background.
- Paragraph 2: Evidence — 2-3 concrete examples from the Base Resume that
  directly match the job requirements.
- Paragraph 3: Close — confident, professional call to action.

Do NOT include salutation or sign-off — those are already in the template.
""".strip()

# ── Core LLM call ─────────────────────────────────────────────────────────────
def call_model(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 3000,
    temperature: float = 0.2,
) -> str:
    if not _SDK_AVAILABLE:
        raise RuntimeError("generative-ai-hub-sdk not installed.")
    ok, missing = validate_credentials()
    if not ok:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")
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
    return response.choices[0].message.content.strip()

# ── JSON parsing helper ───────────────────────────────────────────────────────
def parse_replacements(raw: str) -> dict[str, str]:
    """
    Extract the replacements dict from the AI response.
    Handles markdown code fences, leading/trailing noise, etc.
    """
    # Strip ```json ... ``` or ``` ... ``` fences
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # Try to parse the whole thing as JSON first
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # Accept {"replacements": {...}} or just {"0": "text", ...}
            return data.get("replacements", data)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first {...} blob
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return data.get("replacements", data)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from AI response:\n{raw[:500]}")

# ── Domain functions ──────────────────────────────────────────────────────────
def tailor_resume(
    base_resume_text: str,
    job_description: str,
    template_context: str,
    model_name: str,
) -> dict[str, str]:
    """
    Returns {paragraph_index: new_text} for every paragraph the AI wants
    to rewrite in the resume template.
    """
    prompt = f"""=== RESUME TEMPLATE (paragraph indices) ===
{template_context}

=== BASE RESUME (source of truth — never invent anything not here) ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Return the JSON replacements object as instructed."""

    raw = call_model(model_name, _RESUME_SYSTEM, prompt, max_tokens=3000, temperature=0.2)
    return parse_replacements(raw)


def generate_cover_letter(
    base_resume_text: str,
    job_description: str,
    template_context: str,
    model_name: str,
) -> dict[str, str]:
    """
    Returns {paragraph_index: new_text} for the cover letter body paragraphs.
    """
    prompt = f"""=== COVER LETTER TEMPLATE (paragraph indices) ===
{template_context}

=== BASE RESUME (source of truth — never invent anything not here) ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Return the JSON replacements object as instructed."""

    raw = call_model(model_name, _COVER_LETTER_SYSTEM, prompt, max_tokens=1200, temperature=0.3)
    return parse_replacements(raw)
