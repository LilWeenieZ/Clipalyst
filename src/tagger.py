"""
tagger.py — AI tagging engine for Clipalyst.
"""
import datetime
import threading
import queue
import json
import logging
import os
import re
from anthropic import (
    Anthropic,
    AuthenticationError,
    RateLimitError,
    APIConnectionError,
    APIStatusError,
)
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# API-key heuristic patterns (run locally before calling the LLM)    #
# ------------------------------------------------------------------ #
_API_KEY_PATTERNS = re.compile(
    r'''(?x)
    \b(
        # Common prefixed tokens
        sk-[A-Za-z0-9_\-]{20,}           # OpenAI / Anthropic style
      | pk-[A-Za-z0-9_\-]{20,}
      | rk-[A-Za-z0-9_\-]{20,}
      | ak-[A-Za-z0-9_\-]{20,}
      | [A-Za-z0-9]{32,64}               # Raw hex / base62 secrets
    )\b
    | Bearer\s+[A-Za-z0-9._\-]{20,}      # Authorization header value
    | ghp_[A-Za-z0-9]{36}                # GitHub personal access token
    | gho_[A-Za-z0-9]{36}                # GitHub OAuth token
    | xoxb-[\w\-]+                       # Slack bot token
    | xoxp-[\w\-]+                       # Slack user token
    | AIza[0-9A-Za-z_\-]{35}             # Google API key
    | AKIA[0-9A-Z]{16}                   # AWS access key
    ''',
    re.MULTILINE,
)

# ------------------------------------------------------------------ #
# File / directory path heuristic patterns                           #
# ------------------------------------------------------------------ #
_PATH_PATTERN = re.compile(
    r'''(?x)
    (?:
        # Windows absolute path:  C:\foo\bar  or  C:/foo/bar
        [A-Za-z]:[/\\][^\r\n"'<>|?*\x00-\x1f]*
        |
        # UNC path:  \\server\share  or  //server/share
        [/\\]{2}[^/\\\r\n\s][^/\\\r\n]*[/\\][^\r\n]*
    )
    ''',
    re.MULTILINE,
)

class AITagger(threading.Thread):
    def __init__(self, db, max_content_length=500):
        super().__init__(daemon=True, name="AITaggerThread")
        self._db = db
        self.queue = queue.Queue()
        self.max_content_length = max_content_length
        self.running = False

        # Status tracking (read by get_status())
        self._last_error: str | None = None
        self._tags_processed: int  = 0
        self._last_tagged_at: datetime.datetime | None = None

        # Load API key from .env using python-dotenv
        load_dotenv()
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
            logger.debug("Anthropic client initialised (key …%s).", self.api_key[-4:])
        else:
            self.client = None
            logger.warning(
                "ANTHROPIC_API_KEY not found in environment / .env file. "
                "AI tagging is disabled."
            )

        self.model = "claude-haiku-4-5"
        # NOTE: Do NOT use str.format() with clipboard content — it may contain
        # curly braces (JSON, code, templates) that cause a KeyError.
        self._prompt_prefix = (
            'Classify this clipboard item. '
            'Reply with JSON only, no markdown: '
            '{"type": "api_key|url|code|email|address|phone|name|number|path|text", '
            '"label": "short 3-5 word description"}. '
            'Use type="api_key" for any API keys, tokens, secrets, or credentials. '
            'Use type="path" for file system paths, directory paths, or UNC paths. '
            'Item: '
        )

    # ── Public status API ─────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return a snapshot of the tagger's current state.

        Keys
        ----
        ready          : bool   — True when an API client is configured.
        error          : str|None — human-readable description of the last
                         failure, or None when the last operation succeeded.
        tags_processed : int    — cumulative number of items successfully tagged.
        last_tagged_at : datetime.datetime|None — UTC time of last successful tag.
        """
        return {
            "ready":          self.client is not None,
            "error":          self._last_error,
            "tags_processed": self._tags_processed,
            "last_tagged_at": self._last_tagged_at,
        }

    def tag_item(self, item_id):
        """Accepts item IDs to tag and adds them to the queue."""
        logger.debug("Queuing item %d for AI tagging.", item_id)
        self.queue.put(item_id)

    def reconfigure(self, model: str | None = None, api_key: str | None = None) -> None:
        """Hot-swap the model name and/or API key at runtime.

        Passing an empty string resets to the built-in default.
        """
        _DEFAULT_MODEL = "claude-haiku-4-5"

        if model is not None:
            self.model = model.strip() or _DEFAULT_MODEL
            logger.info("AITagger model set to: %s", self.model)

        if api_key is not None:
            key = api_key.strip()
            if key:
                self.client = Anthropic(api_key=key)
                logger.info("AITagger API key updated (…%s).", key[-4:])
            else:
                # Fall back to env var
                env_key = os.getenv("ANTHROPIC_API_KEY", "")
                self.client = Anthropic(api_key=env_key) if env_key else None
                logger.info("AITagger API key reset to env var.")


    def _looks_like_api_key(self, content: str) -> bool:
        """Return True when the content strongly resembles an API key/token."""
        stripped = content.strip()
        # Must be a single, short line (keys are rarely multi-paragraph)
        if len(stripped.splitlines()) > 3:
            return False
        return bool(_API_KEY_PATTERNS.search(stripped))

    def _looks_like_path(self, content: str) -> bool:
        """Return True when the content looks like a file-system path."""
        stripped = content.strip()
        # Limit to reasonably short, single-path snippets
        if len(stripped.splitlines()) > 5:
            return False
        return bool(_PATH_PATTERN.search(stripped))

    def _process_item(self, item_id):
        """Reads content from DB, calls Anthropic, and writes result back."""
        if not self.client:
            logger.debug("Skipping item %d — no API client (key not configured).", item_id)
            return

        try:
            content = self._db.get_item_content(item_id)
            if not content:
                logger.debug("Skipping item %d — content not found in DB.", item_id)
                return

            logger.debug("Processing item %d (content length=%d).", item_id, len(content))

            # --- Local heuristics: detect well-known types before calling the LLM ---
            if self._looks_like_api_key(content):
                self._db.update_ai_tags(item_id, "api_key", "API key / secret token")
                self._last_error = None
                self._tags_processed += 1
                self._last_tagged_at = datetime.datetime.utcnow()
                logger.debug("Tagged item %d as api_key (local heuristic).", item_id)
                return

            if self._looks_like_path(content):
                self._db.update_ai_tags(item_id, "path", "File / folder path")
                self._last_error = None
                self._tags_processed += 1
                self._last_tagged_at = datetime.datetime.utcnow()
                logger.debug("Tagged item %d as path (local heuristic).", item_id)
                return

            # Truncate content before sending to API
            truncated_content = content[:self.max_content_length]

            # Build prompt via concatenation — never use str.format() with
            # untrusted content that may contain literal curly braces.
            prompt = self._prompt_prefix + truncated_content

            logger.debug(
                "Calling Anthropic (%s) for item %d (%d chars sent).",
                self.model, item_id, len(truncated_content),
            )

            # Call Anthropic API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            response_text = response.content[0].text.strip()
            logger.debug("Anthropic raw response for item %d: %r", item_id, response_text)

            # Extract JSON even if model wraps it in markdown fences
            start_idx = response_text.find("{")
            end_idx   = response_text.rfind("}")
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx + 1]
                data = json.loads(json_str)
                item_type  = data.get("type", "text").lower().strip()
                item_label = data.get("label", "").strip()

                # Write results back to DB
                self._db.update_ai_tags(item_id, item_type, item_label)
                self._last_error = None
                self._tags_processed += 1
                self._last_tagged_at = datetime.datetime.utcnow()
                logger.debug(
                    "Tagged item %d: type=%s  label=%s  (total tagged: %d)",
                    item_id, item_type, item_label, self._tags_processed,
                )
            else:
                logger.warning(
                    "Could not extract JSON from Anthropic response for item %d: %r",
                    item_id, response_text,
                )

        except AuthenticationError:
            self._last_error = "Invalid API key"
            logger.error(
                "Anthropic authentication failed — verify ANTHROPIC_API_KEY in .env"
            )
        except RateLimitError:
            self._last_error = "Rate limit exceeded — will retry next item"
            logger.warning("Anthropic rate limit hit for item %d.", item_id)
        except APIConnectionError as exc:
            self._last_error = "Connection error — check your network"
            logger.error("Network error tagging item %d: %s", item_id, exc)
        except APIStatusError as exc:
            self._last_error = f"API error {exc.status_code}: {exc.message}"
            logger.error("Anthropic API status error for item %d: %s", item_id, exc)
        except Exception as exc:
            self._last_error = str(exc)[:120]
            logger.warning("Unexpected error tagging item %d: %s", item_id, exc)

    def run(self):
        self.running = True
        while self.running:
            try:
                # Use a timeout to allow checking self.running periodically
                item_id = self.queue.get(timeout=1.0)
                self._process_item(item_id)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                # Catch unexpected thread loop errors to keep thread alive
                continue

    def stop(self):
        """Stops the background thread."""
        self.running = False
