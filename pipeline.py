"""CLI pipeline for judol detection, optional moderation, and sentiment analysis."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import BASE_DIR, Settings
from services.gemini import GeminiAnalyzer
from services.youtube import YouTubeClient, build_moderation_service, reject_comments


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def run_pipeline(video_id: str, moderate: bool = False) -> dict[str, Any]:
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise ValueError("Format video ID YouTube tidak valid.")

    settings = Settings.from_env()
    settings.validate_pipeline(moderate=moderate)

    job_dir = settings.data_dir / video_id
    status_file = job_dir / "status.json"
    job_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "video_id": video_id,
        "state": "running",
        "started_at": _now(),
        "model": settings.gemini_model,
        "moderation_requested": moderate,
    }
    _write_json(status_file, status)

    try:
        youtube = YouTubeClient(settings.youtube_api_key)
        comments = youtube.get_comments(video_id)
        _write_json(job_dir / "comments.json", comments)

        analyzer = GeminiAnalyzer(
            settings.gemini_api_key,
            settings.gemini_model,
            BASE_DIR / "prompts",
        )
        classifications = analyzer.classify_judol(comments) if comments else []
        by_id = {item["id"]: item for item in classifications}
        classified_comments = [
            {**comment, **by_id[comment["id"]]} for comment in comments
        ]
        _write_json(job_dir / "classifications.json", classified_comments)

        judol_ids = [
            item["id"] for item in classified_comments if item["is_judol"]
        ]
        clean_comments = [
            {"id": item["id"], "text": item["text"]}
            for item in classified_comments
            if not item["is_judol"]
        ]

        moderation_results: list[dict[str, str]] = []
        if moderate and judol_ids:
            service = build_moderation_service(
                settings.client_secrets_file, settings.oauth_local_port
            )
            moderation_results = reject_comments(service, judol_ids)
            _write_json(job_dir / "moderation.json", moderation_results)

        # Cap the one-shot summary to avoid an oversized model request. All comments
        # remain available in classifications.json for inspection.
        sentiment = analyzer.summarize_sentiment(clean_comments[:300])
        (job_dir / "analysis.txt").write_text(sentiment, encoding="utf-8")

        status.update(
            {
                "state": "completed",
                "completed_at": _now(),
                "comment_count": len(comments),
                "judol_count": len(judol_ids),
                "moderated_count": sum(
                    item["status"] == "rejected" for item in moderation_results
                ),
                "moderation_failures": sum(
                    item["status"] == "failed" for item in moderation_results
                ),
            }
        )
        _write_json(status_file, status)
        return status
    except Exception as exc:
        status.update({"state": "failed", "completed_at": _now(), "error": str(exc)})
        _write_json(status_file, status)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_id", help="11-character YouTube video ID")
    parser.add_argument(
        "--moderate",
        action="store_true",
        help="Reject comments classified as judol after Google OAuth approval.",
    )
    args = parser.parse_args()
    result = run_pipeline(args.video_id, moderate=args.moderate)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
