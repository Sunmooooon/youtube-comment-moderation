"""Gemini-backed comment classification and sentiment summarization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from google import genai
from google.genai import types


def _chunks(items: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def parse_json_response(text: str) -> Any:
    """Parse JSON while tolerating Markdown fences from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned.strip())


def _as_classification(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


class GeminiAnalyzer:
    def __init__(self, api_key: str, model: str, prompts_dir: Path) -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.judol_criteria = (prompts_dir / "judol_indicators.txt").read_text(
            encoding="utf-8"
        )
        self.sentiment_prompt = (prompts_dir / "sentiment_analysis.txt").read_text(
            encoding="utf-8"
        )

    def classify_judol(
        self, comments: list[dict[str, str]], batch_size: int = 50
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        known_ids = {comment["id"] for comment in comments}

        for batch in _chunks(comments, batch_size):
            prompt = (
                "Klasifikasikan komentar YouTube berikut sebagai promosi judi online. "
                "Balas hanya dengan JSON array. Setiap item wajib berbentuk "
                '{"id":"...","is_judol":true|false,"reason":"alasan singkat"}. '
                "Jangan mengubah ID dan jangan menambahkan komentar yang tidak ada.\n\n"
                f"KRITERIA:\n{self.judol_criteria}\n\n"
                f"KOMENTAR:\n{json.dumps(batch, ensure_ascii=False)}"
            )
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            parsed = parse_json_response(response.text or "[]")
            if isinstance(parsed, dict):
                parsed = parsed.get("results", [])
            if not isinstance(parsed, list):
                raise ValueError("Respons klasifikasi Gemini bukan JSON array.")

            for item in parsed:
                if not isinstance(item, dict) or item.get("id") not in known_ids:
                    continue
                results.append(
                    {
                        "id": item["id"],
                        "is_judol": _as_classification(
                            item.get("is_judol", False)
                        ),
                        "reason": str(item.get("reason", "")).strip(),
                    }
                )

        returned_ids = {item["id"] for item in results}
        missing_ids = known_ids - returned_ids
        if missing_ids:
            raise ValueError(
                f"Gemini tidak mengembalikan hasil untuk {len(missing_ids)} komentar."
            )
        return results

    def summarize_sentiment(self, comments: list[dict[str, str]]) -> str:
        if not comments:
            return "Tidak ada komentar non-judol yang dapat dianalisis."

        prompt = (
            f"{self.sentiment_prompt}\n\n"
            "KOMENTAR (JSON):\n"
            f"{json.dumps(comments, ensure_ascii=False)}"
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return (response.text or "Analisis tidak tersedia.").strip()
