# YouTube Comment Moderation Prototype

A local Flask application for reviewing YouTube comments. It uses Gemini to identify online gambling promotion and summarize audience sentiment. Comments classified as gambling promotion can be rejected through the YouTube Data API after the channel owner completes Google OAuth.

The original project used `gemini-2.0-flash`. The model name is now configurable through `GEMINI_MODEL`.

## What it does

- Searches for YouTube channels and lists their recent videos.
- Fetches public comments with their YouTube comment IDs.
- Classifies comments as gambling promotion or non-gambling content.
- Produces a sentiment summary for the remaining comments.
- Optionally sets detected comments to `rejected` using an authenticated channel account.
- Stores classifications, moderation results, logs, and summaries locally under `data/runtime/`.

The web interface starts the analysis in a separate local process. Automatic moderation is disabled by default.

## Requirements

- Python 3.11 or newer
- A Google Cloud project with YouTube Data API v3 enabled
- A YouTube Data API key
- A Gemini API key
- A Google OAuth client JSON file if moderation is enabled

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
New-Item -ItemType Directory -Force secrets
```

Edit `.env` and add the required API keys. Place the OAuth client file at `secrets/client_secret.json`.

The default configuration is:

```dotenv
YOUTUBE_API_KEY=replace_with_a_restricted_key
GEMINI_API_KEY=replace_with_a_restricted_key
GEMINI_MODEL=gemini-2.0-flash
GOOGLE_CLIENT_SECRETS_FILE=secrets/client_secret.json
OAUTH_LOCAL_PORT=8080
ENABLE_AUTO_MODERATION=false
```

The OAuth client's redirect URI must match the configured local port, for example `http://localhost:8080/`.

## Running the application

```powershell
python app.py
```

Open <http://127.0.0.1:5000>, search for a channel, select a video, and start the analysis.

The pipeline can also be run directly:

```powershell
# Analyze without changing comments on YouTube
python pipeline.py VIDEO_ID

# Analyze and reject comments classified as gambling promotion
python pipeline.py VIDEO_ID --moderate
```

## Moderation behavior

YouTube does not allow a channel owner to permanently delete arbitrary comments through this workflow. The application uses `comments.setModerationStatus` with the `rejected` status, which removes the comment from public view.

When `ENABLE_AUTO_MODERATION=false`, classifications are written to:

```text
data/runtime/<VIDEO_ID>/classifications.json
```

Review this file before enabling automatic moderation. LLM classifications can produce false positives.

## Project structure

```text
app.py                 Flask application and local API endpoints
pipeline.py            Analysis and moderation workflow
config.py              Environment-based configuration
services/gemini.py     Gemini classification and sentiment analysis
services/youtube.py    YouTube API and OAuth integration
prompts/                Classification criteria and analysis instructions
templates/              Flask HTML templates
static/                 Dashboard JavaScript and CSS
extension/              Optional Chrome extension
tests/                  Unit tests
data/runtime/           Generated local data, excluded from Git
```

## Chrome extension

The optional extension reads the video ID from the active YouTube tab and sends it to the local Flask server.

1. Start the Flask application on `127.0.0.1:5000`.
2. Open `chrome://extensions` and enable Developer mode.
3. Select **Load unpacked** and choose the `extension/` directory.
4. Open a YouTube video and click the extension button.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The unit tests do not call YouTube or Gemini and do not require credentials.

## Security and data handling

- `.env`, OAuth files, tokens, logs, and runtime output are excluded by `.gitignore`.
- Restrict API keys to the APIs and environments that need them.
- Rotate credentials that were previously stored directly in the old source files.
- YouTube comments are sent to Gemini for classification and analysis.
- Runtime files may contain comment text and account-related metadata. Do not publish them.

## Known limitations

- The sentiment request is limited to the first 300 non-gambling comments. All classification results are still saved locally.
- Detection quality depends on the model, prompt, language, and current spam patterns.
- Moderation requires an account with permission to manage comments on the selected channel.
- The background process is intended for local, single-user use and does not provide a production job queue.
