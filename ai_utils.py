# ─────────────────────────────────────────────────────────────────────────────
#  ai_utils.py  –  SAP AI Core via Orchestration REST API
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import json, os, re, time
import requests

# ── Model catalogue  (GPT-5.2 is the default — listed first) ─────────────────
AVAILABLE_MODELS: dict[str, str] = {
    # Default
    "Claude 4.6 Opus  (Anthropic)":       "anthropic--claude-4.6-opus",
    # OpenAI
    "GPT-5.2  (OpenAI)":                  "gpt-5.2",
    "GPT-5  (OpenAI)":                    "gpt-5",
    "GPT-5 Mini  (OpenAI)":               "gpt-5-mini",
    "GPT-5 Nano  (OpenAI)":               "gpt-5-nano",
    "GPT-4.1  (OpenAI)":                  "gpt-4.1",
    "GPT-4.1 Mini  (OpenAI)":             "gpt-4.1-mini",
    "GPT-4.1 Nano  (OpenAI)":             "gpt-4.1-nano",
    "GPT-4o  (OpenAI)":                   "gpt-4o",
    "GPT-4o Mini  (OpenAI)":              "gpt-4o-mini",
    "o1  (OpenAI)":                       "o1",
    "o3  (OpenAI)":                       "o3",
    "o3 Mini  (OpenAI)":                  "o3-mini",
    "o4 Mini  (OpenAI)":                  "o4-mini",
    # Anthropic
    "Claude 4.6 Sonnet  (Anthropic)":     "anthropic--claude-4.6-sonnet",
    "Claude 4.5 Sonnet  (Anthropic)":     "anthropic--claude-4.5-sonnet",
    "Claude 4.5 Opus  (Anthropic)":       "anthropic--claude-4.5-opus",
    "Claude 4.5 Haiku  (Anthropic)":      "anthropic--claude-4.5-haiku",
    "Claude 4 Sonnet  (Anthropic)":       "anthropic--claude-4-sonnet",
    "Claude 4 Opus  (Anthropic)":         "anthropic--claude-4-opus",
    "Claude 3.7 Sonnet  (Anthropic)":     "anthropic--claude-3.7-sonnet",
    "Claude 3.5 Sonnet  (Anthropic)":     "anthropic--claude-3.5-sonnet",
    "Claude 3 Haiku  (Anthropic)":        "anthropic--claude-3-haiku",
    # Google
    "Gemini 3 Pro Preview  (Google)":     "gemini-3-pro-preview",
    "Gemini 2.5 Pro  (Google)":           "gemini-2.5-pro",
    "Gemini 2.5 Flash  (Google)":         "gemini-2.5-flash",
    "Gemini 2.5 Flash Lite  (Google)":    "gemini-2.5-flash-lite",
    "Gemini 2.0 Flash  (Google)":         "gemini-2.0-flash",
    "Gemini 2.0 Flash Lite  (Google)":    "gemini-2.0-flash-lite",
    # Amazon
    "Nova Premier  (Amazon)":             "amazon--nova-premier",
    "Nova Pro  (Amazon)":                 "amazon--nova-pro",
    "Nova Lite  (Amazon)":                "amazon--nova-lite",
    "Nova Micro  (Amazon)":               "amazon--nova-micro",
    # Mistral AI
    "Mistral Large  (Mistral AI)":        "mistralai--mistral-large-instruct",
    "Mistral Medium  (Mistral AI)":       "mistralai--mistral-medium-instruct",
    "Mistral Small  (Mistral AI)":        "mistralai--mistral-small-instruct",
    # Meta
    "Llama 3 70B  (Meta)":                "meta--llama3-70b-instruct",
    # DeepSeek
    "DeepSeek R1 0528  (DeepSeek)":       "deepseek-r1-0528",
    "DeepSeek V3.2  (DeepSeek)":          "deepseek-v3.2",
    # Qwen
    "Qwen3 Max  (Alibaba)":               "qwen3-max",
    "Qwen3.5 Plus  (Alibaba)":            "qwen3.5-plus",
    "Qwen Turbo  (Alibaba)":              "qwen-turbo",
    "Qwen Flash  (Alibaba)":              "qwen-flash",
    # Perplexity
    "Sonar Pro  (Perplexity)":            "sonar-pro",
    "Sonar  (Perplexity)":                "sonar",
    "Sonar Deep Research  (Perplexity)":  "sonar-deep-research",
    # Cohere
    "Command A Reasoning  (Cohere)":      "cohere--command-a-reasoning",
}

# ── Credentials ───────────────────────────────────────────────────────────────
_REQUIRED_VARS = [
    "SAP_AUTH_URL", "SAP_CLIENT_ID", "SAP_CLIENT_SECRET",
    "SAP_AI_API_URL", "RESOURCE_GROUP", "SAP_DEPLOYMENT_ID",
]

def validate_credentials() -> tuple[bool, list[str]]:
    missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    return len(missing) == 0, missing


# ── OAuth2 token cache ────────────────────────────────────────────────────────
_token_cache: dict = {"token": None, "expires_at": 0.0}

def _get_bearer_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]
    auth_url = os.environ["SAP_AUTH_URL"].rstrip("/")
    if not auth_url.endswith("/oauth/token"):
        auth_url += "/oauth/token"
    resp = requests.post(
        auth_url,
        data={"grant_type": "client_credentials"},
        auth=(os.environ["SAP_CLIENT_ID"], os.environ["SAP_CLIENT_SECRET"]),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600)) - 60
    return _token_cache["token"]


# ── Honesty guardrails ────────────────────────────────────────────────────────
_RESUME_SYSTEM = """
You are an ethical resume tailor. You are strictly forbidden from inventing,
assuming, or adding any skills, metrics, job titles, degrees, or experiences
not explicitly present in the Base Resume.

Rewrite the resume TEMPLATE content to target the Job Description using ONLY
facts from the Base Resume.

OUTPUT FORMAT — return ONLY a raw JSON object, nothing else:
{
  "replacements": {
    "PARAGRAPH_INDEX": "replacement text"
  }
}

CRITICAL RULES — read carefully:

1. TAB-ALIGNED LINES: Lines marked "→TAB→" in the template are two-column
   right-aligned using a tab stop. You MUST return these as "LEFT TEXT\tRIGHT TEXT"
   using a literal \\t (JSON tab escape) to separate left and right content.
   Example — if the template shows:
     [11] Organization/Company Name  →TAB→  Town, State  ← TAB-ALIGNED
   Return: "11": "Acme Corp\\tNew York, NY"
   NEVER return: "11": "Acme Corp, New York, NY"  (comma instead of tab = wrong)
   NEVER return: "11": "Acme Corp  New York, NY"  (spaces instead of tab = wrong)

2. ENTRY GROUPING: Experience and leadership entries each span several
   consecutive paragraphs. A typical group is:
     [N]   Company Name\\tLocation     ← TAB-ALIGNED
     [N+1] Job Title\\tDates           ← TAB-ALIGNED
     [N+2] Bullet point 1
     [N+3] Bullet point 2
     [N+4] Bullet point 3
   Replace ALL paragraphs in a group together. Do not mix content from
   different jobs across different groups.

3. UNUSED SLOTS: If the base resume has fewer jobs than the template provides
   slots for, set ALL paragraphs of the unused slot to "" (empty string).

4. DO NOT REPLACE: lines labelled "SECTION HEADER" or "BLANK SPACER",
   the candidate name (index 0), or the contact info line (index 1).

5. BULLET FORMAT: Bullets should be concise, action-verb-led sentences.
   Use \\n to provide multiple bullets within a single paragraph slot only
   if the template has fewer bullet lines than you need — prefer using the
   individual existing bullet paragraph indices.

6. Never invent experience or skills the candidate does not have.
""".strip()

_COVER_LETTER_SYSTEM = """
You are writing a cover letter for a real person. Use ONLY facts from the Base Resume.
Do not invent anecdotes, fabricate metrics, or use information not present in the resume.

OUTPUT FORMAT — return ONLY a raw JSON object, nothing else:
{
  "replacements": {
    "PARAGRAPH_INDEX": "paragraph text"
  }
}

Replace the body paragraph slots in the template. The number of paragraphs is flexible —
you may write 2 or 3 paragraphs depending on what feels natural. Do not force equal
length. Merge sections if it improves readability.

TONE RULES — these are mandatory:
- Write like a real person, not a template. Vary sentence structure and length.
- Be direct and concise. Cut any sentence that could be removed without losing meaning.
- Slightly conversational but still professional. Avoid stiff formal phrasing.
- If a sentence sounds generic, rewrite it. If it could appear in anyone's cover letter,
  it is not good enough.
- No filler phrases: "I am a hard worker", "team player", "passion for excellence", etc.

OPENING RULE — the first sentence must not be generic:
- Never start with: "I am excited to apply", "I am writing to express my interest",
  "I would like to apply", or any variation.
- Instead open with: a specific reason this role fits the candidate's actual background,
  a concrete connection to the company or team, or a direct statement of what they bring.

STRUCTURE:
- Paragraph 1 (1–2 sentences): Specific hook — why this role, why this company,
  grounded in something real from the candidate's background.
- Paragraph 2 (3–5 sentences): Evidence — 2–3 concrete examples from the Base Resume
  that directly match what the job needs. Be specific, not vague.
- Paragraph 3 (1–2 sentences, optional): Close — confident call to action.
  Skip this paragraph entirely if the first two already feel complete.

Do NOT replace: name, contact info, company address, salutation, or sign-off.
""".strip()


# ── Core API call (temperature-free) ─────────────────────────────────────────
def call_model(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 3000,
) -> str:
    """
    Call SAP AI Core via the Orchestration endpoint.
    Temperature is intentionally omitted — it is unsupported by GPT-5/o-series
    models and the system prompt provides sufficient behavioral guidance.
    """
    ok, missing = validate_credentials()
    if not ok:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}\n"
            "Add them to Streamlit Settings → Secrets."
        )

    token          = _get_bearer_token()
    base_url       = os.environ["SAP_AI_API_URL"].rstrip("/")
    deployment_id  = os.environ["SAP_DEPLOYMENT_ID"]
    resource_group = os.environ["RESOURCE_GROUP"]

    url = f"{base_url}/v2/inference/deployments/{deployment_id}/completion"
    headers = {
        "Authorization": f"Bearer {token}",
        "AI-Resource-Group": resource_group,
        "Content-Type": "application/json",
    }
    body = {
        "orchestration_config": {
            "module_configurations": {
                "llm_module_config": {
                    "model_name": model_name,
                    "model_params": {"max_tokens": max_tokens},
                },
                "templating_module_config": {
                    "template": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ]
                },
            }
        }
    }

    resp = requests.post(url, headers=headers, json=body, timeout=120)

    # Fallback to OpenAI-compatible endpoint for non-orchestration deployments
    if resp.status_code == 404:
        url_fb = f"{base_url}/v2/inference/deployments/{deployment_id}/v1/chat/completions"
        body_fb = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
        resp = requests.post(url_fb, headers=headers, json=body_fb, timeout=120)

    if not resp.ok:
        raise RuntimeError(f"SAP AI Core API error {resp.status_code}:\n{resp.text[:600]}")

    data = resp.json()
    try:
        return data.get("orchestration_result", data)["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(
            f"Unexpected SAP response structure:\n{json.dumps(data, indent=2)[:600]}"
        )


# ── JSON parsing with auto-retry ─────────────────────────────────────────────
def parse_replacements(raw: str) -> dict[str, str]:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data.get("replacements", data)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return data.get("replacements", data)
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse AI response as JSON:\n{raw[:500]}")


def _call_with_retry(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> dict[str, str]:
    """Call model and parse JSON. Auto-retries once with stricter prompt on parse failure."""
    raw = call_model(model_name, system_prompt, user_prompt, max_tokens)
    try:
        return parse_replacements(raw)
    except ValueError:
        retry_prompt = (
            user_prompt
            + "\n\n⚠️ IMPORTANT: Your previous response could not be parsed as JSON. "
            "You MUST return ONLY a raw JSON object — start with { and end with }. "
            "No text before or after. No markdown. No backticks."
        )
        raw2 = call_model(model_name, system_prompt, retry_prompt, max_tokens)
        return parse_replacements(raw2)


# ── Domain functions ──────────────────────────────────────────────────────────
def tailor_resume(
    base_resume_text: str,
    job_description: str,
    template_context: str,
    model_name: str,
) -> dict[str, str]:
    prompt = f"""=== RESUME TEMPLATE (paragraph indices) ===
{template_context}

=== BASE RESUME (source of truth — never invent anything not here) ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Return the JSON replacements object as instructed."""
    return _call_with_retry(model_name, _RESUME_SYSTEM, prompt, max_tokens=3000)


def generate_cover_letter(
    base_resume_text: str,
    job_description: str,
    template_context: str,
    model_name: str,
) -> dict[str, str]:
    prompt = f"""=== COVER LETTER TEMPLATE (paragraph indices) ===
{template_context}

=== BASE RESUME (source of truth — never invent anything not here) ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Return the JSON replacements object as instructed."""
    return _call_with_retry(model_name, _COVER_LETTER_SYSTEM, prompt, max_tokens=1200)
