from __future__ import annotations

SENSITIVE_KEYS = {
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "app_secret",
    "authorization",
    "password",
    "secret",
    "token",
    "verify_token",
    "x-api-key",
    "x_api_key",
}


def sanitize_payload(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = sanitize_payload(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value
