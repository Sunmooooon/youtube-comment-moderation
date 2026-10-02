import unittest

from services.youtube import YouTubeAPIError, YouTubeClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = ""
        self.reason = "error"

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return next(self.responses)


class YouTubeClientTests(unittest.TestCase):
    def test_paginates_comments_and_keeps_ids(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "items": [
                            {
                                "snippet": {
                                    "topLevelComment": {
                                        "id": "one",
                                        "snippet": {"textDisplay": "Komentar satu"},
                                    }
                                }
                            }
                        ],
                        "nextPageToken": "next",
                    }
                ),
                FakeResponse(
                    {
                        "items": [
                            {
                                "snippet": {
                                    "topLevelComment": {
                                        "id": "two",
                                        "snippet": {"textDisplay": "Komentar dua"},
                                    }
                                }
                            }
                        ]
                    }
                ),
            ]
        )
        client = YouTubeClient("test-key", session=session)

        self.assertEqual(
            client.get_comments("video123456"),
            [
                {"id": "one", "text": "Komentar satu"},
                {"id": "two", "text": "Komentar dua"},
            ],
        )
        self.assertEqual(session.calls[1][1]["pageToken"], "next")

    def test_surfaces_api_error_message(self):
        session = FakeSession(
            [FakeResponse({"error": {"message": "quota exceeded"}}, status_code=403)]
        )
        client = YouTubeClient("test-key", session=session)

        with self.assertRaisesRegex(YouTubeAPIError, "quota exceeded"):
            client.get_video("video123456")


if __name__ == "__main__":
    unittest.main()
