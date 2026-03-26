# ─────────────────────────────────────────────────────────────────────────────
#  ai_utils.py  –  SAP AI Core direct REST API (no SDK model-name lookup)
#
#  Uses the same env vars as the user's working chatbot:
#    SAP_AUTH_URL              – OAuth2 token endpoint
#    SAP_CLIENT_ID             – OAuth2 client ID
#    SAP_CLIENT_SECRET         – OAuth2 client secret
#    SAP_AI_API_URL            – AI Core base URL (no trailing slash)
#    RESOURCE_GROUP            – Resource group (usually "default")
#    SAP_DEPLOYMENT_ID         – Default deployment ID to use
#
#  How it works:
#    1. Fetch an OAuth2 bearer token from SAP_AUTH_URL
#    2. POST to /v2/inference/deployments/{deployment_id}/v1/chat/completions
#       with the token and AI-Resource-Group header
#    3. Parse the OpenAI-compatible response
#
#  This is exactly how the working chatbot calls SAP AI Core — no SDK
#  model-name-to-deployment resolution that was causing "No deployment found".
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import json, os, re, time
import requests

# ── Model catalogue ───────────────────────────────────────────────────────────
# Display label → SAP model name hint (sent in the request body).
# The actual routing is determined by the deployment ID, not this name.
# This list is cosmetic / informational — all requests go through whichever
# deployment ID is configured in SAP_DEPLOYMENT_ID.
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

# ── Required env vars (matching the user's existing chatbot setup) ────────────
_REQUIRED_VARS = [
    "SAP_AUTH_URL",
    "SAP_CLIENT_ID",
    "SAP_CLIENT_SECRET",
    "SAP_AI_API_URL",
    "RESOURCE_GROUP",
    "SAP_DEPLOYMENT_ID",
]

def validate_credentials() -> tuple[bool, list[str]]:
    missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    return len(missing) == 0, missing


# ── OAuth2 token cache (avoid fetching a new token on every single call) ──────
_token_cache: dict = {"token": None, "expires_at": 0.0}

def _get_bearer_token() -> str:
    """
    Fetch (or return cached) OAuth2 bearer token from SAP_AUTH_URL.
    Tokens are cached until 60 seconds before expiry.
    """
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    auth_url     = os.environ["SAP_AUTH_URL"]
    client_id    = os.environ["SAP_CLIENT_ID"]
    client_secret = os.environ["SAP_CLIENT_SECRET"]

    # Ensure the token URL ends with /oauth/token
    if not auth_url.rstrip("/").endswith("/oauth/token"):
        auth_url = auth_url.rstrip("/") + "/oauth/token"

    resp = requests.post(
        auth_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expires_in - 60  # 60s safety buffer

    return token


# ── Honesty guardrails ────────────────────────────────────────────────────────
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


# ── Core API call ─────────────────────────────────────────────────────────────
def call_model(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 3000,
    temperature: float = 0.2,
) -> str:
    """
    Call SAP AI Core via the Orchestration service endpoint.
    
    The user's chatbot uses SAP_ORCHESTRATION_DEPLOYMENT_ID which means it
    targets the orchestration service, not the raw model inference endpoint.
    
    Orchestration endpoint:
      POST {SAP_AI_API_URL}/v2/inference/deployments/{id}/completion
    
    This is different from the standard OpenAI-compatible endpoint
      POST .../v1/chat/completions
    which 404s against orchestration deployments.
    """
    ok, missing = validate_credentials()
    if not ok:
        raise RuntimeError(
            f"Missing environment variables: {', '.join(missing)}\n\n"
            f"Add these to your Streamlit Secrets (Settings → Secrets)."
        )

    token          = _get_bearer_token()
    base_url       = os.environ["SAP_AI_API_URL"].rstrip("/")
    deployment_id  = os.environ["SAP_DEPLOYMENT_ID"]
    resource_group = os.environ["RESOURCE_GROUP"]

    # Orchestration service endpoint — this is what works with deployment IDs
    # created via the SAP AI Core Orchestration scenario.
    url = f"{base_url}/v2/inference/deployments/{deployment_id}/completion"

    headers = {
        "Authorization": f"Bearer {token}",
        "AI-Resource-Group": resource_group,
        "Content-Type": "application/json",
    }

    # Orchestration request body format (different from OpenAI chat completions)
    body = {
        "orchestration_config": {
            "module_configurations": {
                "llm_module_config": {
                    "model_name": model_name,
                    "model_params": {
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
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

    if resp.status_code == 404:
        # Deployment might actually be a direct model deployment (not orchestration).
        # Fall back to the standard OpenAI-compatible endpoint.
        url_fallback = (
            f"{base_url}/v2/inference/deployments/{deployment_id}/v1/chat/completions"
        )
        body_fallback = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = requests.post(url_fallback, headers=headers, json=body_fallback, timeout=120)

    if not resp.ok:
        raise RuntimeError(
            f"SAP AI Core API error {resp.status_code}:\n{resp.text[:600]}"
        )

    data = resp.json()

    # Orchestration response shape:  data["orchestration_result"]["choices"][0]["message"]["content"]
    # Standard chat completions shape: data["choices"][0]["message"]["content"]
    try:
        return (
            data.get("orchestration_result", data)
            ["choices"][0]["message"]["content"].strip()
        )
    except (KeyError, IndexError, TypeError):
        # Last resort — return the raw JSON so the user can see what came back
        raise RuntimeError(
            f"Unexpected response structure from SAP AI Core:\n{json.dumps(data, indent=2)[:600]}"
        )


# ── JSON parsing helper ───────────────────────────────────────────────────────
def parse_replacements(raw: str) -> dict[str, str]:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data.get("replacements", data)
    except json.JSONDecodeError:
        pass
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
    prompt = f"""=== COVER LETTER TEMPLATE (paragraph indices) ===
{template_context}

=== BASE RESUME (source of truth — never invent anything not here) ===
{base_resume_text}

=== TARGET JOB DESCRIPTION ===
{job_description}

Return the JSON replacements object as instructed."""
    raw = call_model(model_name, _COVER_LETTER_SYSTEM, prompt, max_tokens=1200, temperature=0.3)
    return parse_replacements(raw)