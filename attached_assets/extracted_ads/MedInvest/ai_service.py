from __future__ import annotations

import os
from typing import Any, Dict


def _simple_summary(text: str, max_chars: int = 900) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.2):]
    return head + "\n[...]\n" + tail


def summarize_text(text: str) -> Dict[str, Any]:
    """Summarize a discussion thread. Uses OpenAI if configured."""
    text = (text or "").strip()
    if not text:
        return {"summary": "", "provider": "none"}

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        return {"summary": _simple_summary(text), "provider": "fallback"}

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "You summarize physician community discussions about investing. Be concise. Highlight risks. Do not provide individualized financial advice.",
                },
                {
                    "role": "user",
                    "content": "Summarize this in 5 bullets. Then list 3 key risks. Then list 3 recommended next steps for diligence:\n\n" + text,
                },
            ],
        )
        return {"summary": resp.output_text, "provider": "openai", "model": model}
    except Exception as e:
        return {"summary": _simple_summary(text), "provider": "fallback", "error": str(e)}


def analyze_deal(text: str) -> Dict[str, Any]:
    """Structured deal analysis. Uses OpenAI if configured."""
    text = (text or "").strip()
    if not text:
        return {"analysis": "", "provider": "none"}

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        return {
            "analysis": "OPENAI_API_KEY not set. Provide OPENAI_API_KEY to enable analysis.",
            "provider": "fallback",
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "You are an investment diligence assistant for physicians. You must be practical, identify risks, ask underwriting questions, and avoid personalized financial advice.",
                },
                {
                    "role": "user",
                    "content": "Analyze the following deal summary. Output: (1) Thesis (2) Underwriting questions (3) Key risks (4) Diligence checklist (5) Red flags.\n\n" + text,
                },
            ],
        )
        return {"analysis": resp.output_text, "provider": "openai", "model": model}
    except Exception as e:
        return {
            "analysis": "AI analysis failed; falling back.\n\n" + _simple_summary(text),
            "provider": "fallback",
            "error": str(e),
        }


def analyze_deal_with_memory(text: str, memory_context: str) -> Dict[str, Any]:
    """Structured deal analysis augmented with prior deal outcomes (memory)."""
    text = (text or "").strip()
    memory_context = (memory_context or "").strip()

    if not memory_context:
        return analyze_deal(text)

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        # Fall back to non-memory response with a note.
        base = analyze_deal(text)
        base["analysis"] = (base.get("analysis") or "") + "\n\n(Memory disabled: OPENAI_API_KEY not set.)"
        return base

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        prompt = (
            "Analyze the following deal summary. Output: (1) Thesis (2) Underwriting questions "
            "(3) Key risks (4) Diligence checklist (5) Red flags (6) Compare against similar past deals.\n\n"
            "DEAL SUMMARY:\n" + text
            + "\n\nDEAL MEMORY (prior outcomes):\n" + memory_context
        )
        resp = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "You are an investment diligence assistant for physicians. Be practical, identify risks, ask underwriting questions, and avoid personalized financial advice. Use deal memory to spot repeat failure modes.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return {"analysis": resp.output_text, "provider": "openai", "model": model, "used_memory": True}
    except Exception as e:
        return {
            "analysis": "AI analysis failed; falling back.\n\n" + _simple_summary(text) + "\n\n" + memory_context,
            "provider": "fallback",
            "error": str(e),
            "used_memory": False,
        }
