from __future__ import annotations

import os
from typing import Dict, Any


def get_openai_key() -> str | None:
    try:
        import streamlit as st
        key = st.secrets.get("OPENAI_API_KEY")
        if key:
            return str(key)
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")


def build_ai_summary(result: Dict[str, Any]) -> str | None:
    """Optional AI layer. The app works without this."""
    key = get_openai_key()
    if not key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)

        prompt = f"""
You are the Bradley Real Estate Offer Engine. Be direct, practical, and conservative.

Analyze this output and write:
1. Decision in one sentence
2. Human next action
3. Cleaner agent/seller message
4. One call opener
5. One warning if needed

Use this data:
{result}
""".strip()

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        return response.output_text
    except Exception as exc:
        return f"AI summary unavailable. Calculator still worked. Error: {exc}"
