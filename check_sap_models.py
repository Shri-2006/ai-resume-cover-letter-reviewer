#!/usr/bin/env python3
"""
check_sap_models.py
Lists all available models in your SAP AI Core orchestration deployment.

Usage:
    python3 check_sap_models.py

Reads credentials from environment variables or prompts you to enter them.
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error

def get_token(auth_url, client_id, client_secret):
    print("🔑 Getting SAP token...")
    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
    }).encode()
    req = urllib.request.Request(
        f"{auth_url}/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]

def get_models(api_url, deployment_id, resource_group, token):
    print("📋 Fetching available models...")
    # Use a minimal payload that will fail with the full model list in the error
    payload = json.dumps({
        "orchestration_config": {
            "module_configurations": {
                "templating_module_config": {
                    "template": [{"role": "user", "content": "{{?user_input}}"}]
                },
                "llm_module_config": {
                    "model_name": "INVALID_MODEL_TO_GET_LIST",
                    "model_params": {"max_tokens": 1}
                }
            }
        },
        "input_params": {"user_input": "test"}
    }).encode()

    req = urllib.request.Request(
        f"{api_url}/v2/inference/deployments/{deployment_id}/completion",
        data=payload,
        headers={
            "Authorization":    f"Bearer {token}",
            "AI-Resource-Group": resource_group,
            "Content-Type":     "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return None, error_body

def parse_models_from_error(error_text):
    """Extract model names from the SAP error message."""
    try:
        data = json.loads(error_text)
        msg = data.get("message", "")
        # Extract dict_keys([...])
        start = msg.find("dict_keys([")
        if start == -1:
            return None
        end = msg.find("])", start)
        keys_str = msg[start + len("dict_keys(["):end]
        # Parse the quoted strings
        models = [k.strip().strip("'\"") for k in keys_str.split(",")]
        return [m for m in models if m]
    except Exception:
        return None

def main():
    print("=" * 60)
    print("  SAP AI Core — Available Models Checker")
    print("=" * 60)

    # Read from env vars or prompt
    auth_url      = os.environ.get("SAP_AUTH_URL")
    client_id     = os.environ.get("SAP_CLIENT_ID")
    client_secret = os.environ.get("SAP_CLIENT_SECRET")
    api_url       = os.environ.get("SAP_AI_API_URL")
    deployment_id = os.environ.get("SAP_ORCHESTRATION_DEPLOYMENT_ID")
    resource_group = os.environ.get("RESOURCE_GROUP", "default")

    if not all([auth_url, client_id, client_secret, api_url, deployment_id]):
        print("\n⚠️  Environment variables not set. Please enter credentials:\n")
        auth_url       = input("SAP_AUTH_URL: ").strip()
        client_id      = input("SAP_CLIENT_ID: ").strip()
        client_secret  = input("SAP_CLIENT_SECRET: ").strip()
        api_url        = input("SAP_AI_API_URL: ").strip()
        deployment_id  = input("SAP_ORCHESTRATION_DEPLOYMENT_ID: ").strip()
        resource_group = input("RESOURCE_GROUP (default): ").strip() or "default"

    try:
        token = get_token(auth_url, client_id, client_secret)
        print("✅ Token obtained\n")
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        return

    result, error = get_models(api_url, deployment_id, resource_group, token)

    if error:
        models = parse_models_from_error(error)
        if models:
            # Group by provider
            groups = {}
            for m in models:
                if m.startswith("anthropic--"):    provider = "Anthropic (Claude)"
                elif m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
                                                    provider = "OpenAI"
                elif m.startswith("gemini"):        provider = "Google (Gemini)"
                elif m.startswith("amazon--"):      provider = "Amazon (Nova)"
                elif m.startswith("mistralai--"):   provider = "Mistral AI"
                elif m.startswith("meta--"):        provider = "Meta (Llama)"
                elif m.startswith("deepseek"):      provider = "DeepSeek"
                elif m.startswith("qwen"):          provider = "Qwen (Alibaba)"
                elif m.startswith("gemini-3"):      provider = "Google (Gemini)"
                elif m.startswith("sonar"):         provider = "Perplexity (Sonar)"
                elif m.startswith("cohere"):        provider = "Cohere"
                else:                               provider = "Other"
                groups.setdefault(provider, []).append(m)

            print(f"✅ Found {len(models)} available models:\n")
            for provider, model_list in sorted(groups.items()):
                print(f"  📦 {provider}")
                for m in sorted(model_list):
                    print(f"      • {m}")
                print()
        else:
            print("❌ Could not parse model list from error.")
            print("Raw error:", error[:1000])
    else:
        print("⚠️  Unexpected: request succeeded with INVALID_MODEL_TO_GET_LIST")
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()