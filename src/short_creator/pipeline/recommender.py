"""LLM-powered short-clip recommender.

Reads the transcript, asks an LLM to suggest 3–10 compelling clips of 15–90s,
and returns a Recommendations payload with stable IDs.
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Protocol

from ..config import RecommenderConfig
from ..models import ClipSuggestion, Recommendations, Transcript


SYSTEM_PROMPT = """\
You are a viral short-form video editor. Given a transcript with timestamps,
identify segments that would make compelling YouTube Shorts / TikToks.

For each suggestion follow these rules:
- The clip must be a complete thought (do not start mid-sentence).
- Duration must be between {min_s} and {max_s} seconds.
- The first 3 seconds must contain a hook (question, surprising statement, strong claim).
- The clip should stand alone without surrounding context.

Return strictly valid JSON in this schema:
{{
  "clips": [
    {{
      "start": <float seconds>,
      "end": <float seconds>,
      "title": <string, <=60 chars>,
      "hook": <string, the first attention-grabbing line>,
      "reason": <string, why this works>,
      "score": <int 0-100>
    }}
  ]
}}

Output ONLY the JSON object — no prose, no markdown fences.
"""


def _format_transcript(transcript: Transcript) -> str:
    lines = []
    for seg in transcript.segments:
        lines.append(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}")
    return "\n".join(lines)


class RecommenderProvider(Protocol):
    def recommend(self, transcript: Transcript, cfg: RecommenderConfig) -> list[dict]: ...


class AnthropicProvider:
    def recommend(self, transcript: Transcript, cfg: RecommenderConfig) -> list[dict]:
        from anthropic import Anthropic
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

        client = Anthropic(api_key=key)
        prompt = _format_transcript(transcript)
        system = SYSTEM_PROMPT.format(min_s=cfg.min_clip_seconds, max_s=cfg.max_clip_seconds)

        msg = client.messages.create(
            model=cfg.model,
            max_tokens=2048,
            system=system,
            messages=[
                {"role": "user", "content": f"Transcript:\n\n{prompt}\n\nSuggest up to {cfg.max_clips} clips."}
            ],
        )
        text = "".join(block.text for block in msg.content if hasattr(block, "text"))
        return _parse_clips(text)


class OpenAIProvider:
    def recommend(self, transcript: Transcript, cfg: RecommenderConfig) -> list[dict]:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")

        client = OpenAI(api_key=key)
        prompt = _format_transcript(transcript)
        system = SYSTEM_PROMPT.format(min_s=cfg.min_clip_seconds, max_s=cfg.max_clip_seconds)

        completion = client.chat.completions.create(
            model=cfg.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Transcript:\n\n{prompt}\n\nSuggest up to {cfg.max_clips} clips."},
            ],
        )
        text = completion.choices[0].message.content or "{}"
        return _parse_clips(text)


class OllamaProvider:
    def recommend(self, transcript: Transcript, cfg: RecommenderConfig) -> list[dict]:
        import httpx
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        prompt = _format_transcript(transcript)
        system = SYSTEM_PROMPT.format(min_s=cfg.min_clip_seconds, max_s=cfg.max_clip_seconds)

        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                f"{host}/api/chat",
                json={
                    "model": cfg.model,
                    "format": "json",
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Transcript:\n\n{prompt}"},
                    ],
                    "options": {"temperature": 0.4, "keep_alive": 0},
                },
            )
            resp.raise_for_status()
            text = resp.json().get("message", {}).get("content", "{}")
        return _parse_clips(text)


def _parse_clips(text: str) -> list[dict]:
    """Robust JSON extraction — tolerates a fenced or padded LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return data.get("clips", []) or []


PROVIDERS: dict[str, type[RecommenderProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def recommend(transcript: Transcript, cfg: RecommenderConfig) -> Recommendations:
    provider_cls = PROVIDERS.get(cfg.provider)
    if provider_cls is None:
        raise ValueError(f"Unknown provider: {cfg.provider}")
    provider = provider_cls()
    raw_clips = provider.recommend(transcript, cfg)

    clips: list[ClipSuggestion] = []
    for raw in raw_clips:
        try:
            start = float(raw["start"])
            end = float(raw["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if end <= start:
            continue
        if end - start < cfg.min_clip_seconds:
            continue
        if end - start > cfg.max_clip_seconds + 5:  # tiny slack
            continue
        clips.append(
            ClipSuggestion(
                id=secrets.token_hex(4),
                start=start,
                end=end,
                title=str(raw.get("title", "")).strip()[:100],
                hook=str(raw.get("hook", "")).strip()[:200],
                reason=str(raw.get("reason", "")).strip()[:400],
                score=int(raw.get("score", 50)),
            )
        )
    clips.sort(key=lambda c: c.score, reverse=True)

    import hashlib
    transcript_hash = hashlib.sha256(transcript.text().encode("utf-8")).hexdigest()[:16]

    return Recommendations(
        generated_at_transcript_hash=transcript_hash,
        clips=clips,
    )
