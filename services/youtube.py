"""YouTube Data API and OAuth moderation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_MODERATION_SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl"
]


class YouTubeAPIError(RuntimeError):
    """Raised when YouTube returns an unsuccessful API response."""


class YouTubeClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout

    def _get(self, resource: str, **params: Any) -> dict[str, Any]:
        params["key"] = self.api_key
        response = self.session.get(
            f"{YOUTUBE_API_BASE}/{resource}",
            params=params,
            timeout=self.timeout,
        )
        if not response.ok:
            try:
                message = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = response.text or response.reason
            raise YouTubeAPIError(f"YouTube API error {response.status_code}: {message}")
        return response.json()

    def search_channels(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        data = self._get(
            "search",
            part="snippet",
            q=query,
            type="channel",
            maxResults=max_results,
        )
        return [
            {
                "id": item["snippet"]["channelId"],
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
            }
            for item in data.get("items", [])
        ]

    def get_channel(self, channel_id: str) -> dict[str, Any] | None:
        data = self._get(
            "channels", part="statistics,snippet", id=channel_id, maxResults=1
        )
        items = data.get("items", [])
        if not items:
            return None
        item = items[0]
        return {
            "id": channel_id,
            "title": item["snippet"]["title"],
            "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
            "statistics": item.get("statistics", {}),
        }

    def get_channel_videos(
        self, channel_id: str, max_results: int = 12
    ) -> list[dict[str, str]]:
        data = self._get(
            "search",
            part="snippet",
            channelId=channel_id,
            maxResults=max_results,
            order="date",
            type="video",
        )
        return [
            {
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
            }
            for item in data.get("items", [])
        ]

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        data = self._get(
            "videos", part="snippet,statistics", id=video_id, maxResults=1
        )
        items = data.get("items", [])
        if not items:
            return None
        item = items[0]
        stats = item.get("statistics", {})
        return {
            "id": video_id,
            "title": item["snippet"]["title"],
            "views": stats.get("viewCount", "0"),
            "likes": stats.get("likeCount", "0"),
            "comments": stats.get("commentCount", "0"),
        }

    def get_comments(
        self, video_id: str, max_comments: int | None = None
    ) -> list[dict[str, str]]:
        comments: list[dict[str, str]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 100,
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token

            data = self._get("commentThreads", **params)
            for item in data.get("items", []):
                comment = item["snippet"]["topLevelComment"]
                comments.append(
                    {
                        "id": comment["id"],
                        "text": comment["snippet"]["textDisplay"],
                    }
                )
                if max_comments and len(comments) >= max_comments:
                    return comments

            page_token = data.get("nextPageToken")
            if not page_token:
                return comments


def build_moderation_service(client_secrets_file: Path, port: int = 8080):
    """Open Google's OAuth flow and return an authenticated YouTube client."""
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_file), YOUTUBE_MODERATION_SCOPES
    )
    credentials = flow.run_local_server(port=port)
    return build("youtube", "v3", credentials=credentials)


def reject_comments(service: Any, comment_ids: list[str]) -> list[dict[str, str]]:
    """Set comments to rejected and return a per-comment audit result."""
    results = []
    for comment_id in comment_ids:
        try:
            service.comments().setModerationStatus(
                id=comment_id,
                moderationStatus="rejected",
                banAuthor=False,
            ).execute()
            results.append({"id": comment_id, "status": "rejected"})
        except Exception as exc:  # Google client exposes several HTTP exception types.
            results.append({"id": comment_id, "status": "failed", "error": str(exc)})
    return results
