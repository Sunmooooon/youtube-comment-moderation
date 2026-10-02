"""Flask dashboard for YouTube comment intelligence and moderation."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import BASE_DIR, Settings
from services.youtube import YouTubeAPIError, YouTubeClient


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _valid_video_id(video_id: str) -> bool:
    return bool(VIDEO_ID_PATTERN.fullmatch(video_id))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}, r"/fetch-comments": {"origins": "*"}})

    def youtube_client() -> YouTubeClient:
        if not settings.youtube_api_key:
            raise RuntimeError("YOUTUBE_API_KEY belum dikonfigurasi. Lihat .env.example.")
        return YouTubeClient(settings.youtube_api_key)

    @app.errorhandler(YouTubeAPIError)
    def handle_youtube_error(error: YouTubeAPIError):
        if request.path.startswith("/api/") or request.path == "/fetch-comments":
            return jsonify({"error": str(error)}), 502
        return render_template("index.html", error=str(error), config_missing=[]), 502

    @app.get("/")
    @app.post("/")
    def index():
        context = {
            "creator": "",
            "channel_choices": [],
            "channel": None,
            "videos": [],
            "error": None,
            "config_missing": settings.missing_dashboard_config(),
            "auto_moderation": settings.enable_auto_moderation,
        }
        if request.method == "GET" or context["config_missing"]:
            return render_template("index.html", **context)

        creator = request.form.get("creator", "").strip()
        channel_id = request.form.get("channel_id", "").strip()
        context["creator"] = creator

        try:
            client = youtube_client()
            if channel_id:
                context["channel"] = client.get_channel(channel_id)
                context["videos"] = client.get_channel_videos(channel_id)
                if context["channel"] is None:
                    context["error"] = "Channel tidak ditemukan."
            elif creator:
                context["channel_choices"] = client.search_channels(creator)
                if not context["channel_choices"]:
                    context["error"] = "Tidak ada channel yang ditemukan."
        except (YouTubeAPIError, RuntimeError) as exc:
            context["error"] = str(exc)

        return render_template("index.html", **context)

    @app.get("/api/videos/<video_id>")
    def video_detail(video_id: str):
        if not _valid_video_id(video_id):
            return jsonify({"error": "Video ID tidak valid."}), 400
        video = youtube_client().get_video(video_id)
        if video is None:
            return jsonify({"error": "Video tidak ditemukan."}), 404
        return jsonify(video)

    @app.get("/api/videos/<video_id>/comments")
    def video_comments(video_id: str):
        if not _valid_video_id(video_id):
            return jsonify({"error": "Video ID tidak valid."}), 400
        return jsonify({"comments": youtube_client().get_comments(video_id)})

    @app.post("/api/videos/<video_id>/process")
    def process_video(video_id: str):
        if not _valid_video_id(video_id):
            return jsonify({"error": "Video ID tidak valid."}), 400
        try:
            settings.validate_pipeline(moderate=settings.enable_auto_moderation)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

        job_dir = settings.data_dir / video_id
        status_file = job_dir / "status.json"
        if status_file.is_file() and _read_json(status_file).get("state") in {
            "queued",
            "running",
        }:
            return jsonify({"error": "Video ini sedang diproses."}), 409

        job_dir.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            json.dumps(
                {
                    "video_id": video_id,
                    "state": "queued",
                    "queued_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        command = [sys.executable, str(BASE_DIR / "pipeline.py"), video_id]
        if settings.enable_auto_moderation:
            command.append("--moderate")

        log_file = job_dir / "pipeline.log"
        with log_file.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=BASE_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        return (
            jsonify(
                {
                    "message": "Pemrosesan dimulai.",
                    "video_id": video_id,
                    "pid": process.pid,
                    "auto_moderation": settings.enable_auto_moderation,
                }
            ),
            202,
        )

    @app.get("/api/videos/<video_id>/analysis")
    def video_analysis(video_id: str):
        if not _valid_video_id(video_id):
            return jsonify({"error": "Video ID tidak valid."}), 400
        job_dir = settings.data_dir / video_id
        status_file = job_dir / "status.json"
        if not status_file.is_file():
            return jsonify({"state": "not_started", "analysis": None}), 404
        status = _read_json(status_file)
        analysis_file = job_dir / "analysis.txt"
        status["analysis"] = (
            analysis_file.read_text(encoding="utf-8")
            if analysis_file.is_file()
            else None
        )
        return jsonify(status)

    # Compatibility endpoint used by the optional Chrome extension.
    @app.post("/fetch-comments")
    def extension_process_video():
        payload = request.get_json(silent=True) or {}
        video_id = str(payload.get("videoId", ""))
        if not _valid_video_id(video_id):
            return jsonify({"error": "Video ID tidak valid."}), 400
        comments = youtube_client().get_comments(video_id)
        return jsonify({"video_id": video_id, "comment_count": len(comments)})

    return app


if __name__ == "__main__":
    current_settings = Settings.from_env()
    create_app(current_settings).run(
        host=current_settings.flask_host,
        port=current_settings.flask_port,
        debug=current_settings.flask_debug,
    )
