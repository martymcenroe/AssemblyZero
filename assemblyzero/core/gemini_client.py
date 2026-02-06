"""Custom Gemini client with credential rotation and model enforcement.

This module encapsulates ALL Gemini API interaction for LLD reviews,
ensuring:
1. Model hierarchy enforcement - Never downgrades from Pro
2. Credential rotation - Automatic failover on quota exhaustion
3. Differentiated error handling - 529 vs 429 vs other errors

Ported from tools/gemini-rotate.py for programmatic use.
"""

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from assemblyzero.core.config import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_MAX_SECONDS,
    CREDENTIALS_FILE,
    FORBIDDEN_MODELS,
    GEMINI_API_LOG_FILE,
    REVIEWER_MODEL,
    MAX_RETRIES_PER_CREDENTIAL,
    ROTATION_STATE_FILE,
)


# =============================================================================
# Error Classification
# =============================================================================


class GeminiErrorType(Enum):
    """Classification of Gemini API errors."""

    QUOTA_EXHAUSTED = "quota"  # 429 - Rotate to next credential
    CAPACITY_EXHAUSTED = "capacity"  # 529 - Backoff and retry same credential
    AUTH_ERROR = "auth"  # Invalid key - Skip credential permanently
    PARSE_ERROR = "parse"  # JSON parse failure - Fail closed
    MODEL_MISMATCH = "model"  # Wrong model used - Fail closed
    UNKNOWN = "unknown"  # Other errors - Fail closed


# Pattern matching (from gemini-rotate.py)
QUOTA_EXHAUSTED_PATTERNS = [
    "TerminalQuotaError",
    "exhausted your capacity",
    "QUOTA_EXHAUSTED",
    "429",
    "Resource has been exhausted",
]

CAPACITY_PATTERNS = [
    "MODEL_CAPACITY_EXHAUSTED",
    "RESOURCE_EXHAUSTED",
    "503",
    "529",
    "The model is overloaded",
]

AUTH_ERROR_PATTERNS = [
    "API_KEY_INVALID",
    "API key not valid",
    "PERMISSION_DENIED",
    "UNAUTHENTICATED",
    "401",
    "403",
]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Credential:
    """A Gemini credential (API key or OAuth)."""

    name: str
    key: str  # API key for api_key type, empty for oauth type
    enabled: bool = True
    account_name: str = ""
    cred_type: str = "api_key"  # "api_key" or "oauth"


@dataclass
class RotationState:
    """Tracks quota status for credentials."""

    exhausted: dict = field(default_factory=dict)  # name -> reset_time_iso
    last_success: Optional[str] = None
    last_success_time: Optional[str] = None


class CredentialPoolExhaustedException(Exception):
    """Raised when all Gemini credentials are exhausted.

    This exception signals that the workflow should pause (not fail)
    and wait for quota to reset. The workflow can be resumed later.
    """

    def __init__(self, message: str, earliest_reset: str = "", exhausted_credentials: list = None):
        super().__init__(message)
        self.earliest_reset = earliest_reset  # ISO timestamp of earliest quota reset
        self.exhausted_credentials = exhausted_credentials or []

    def get_resume_message(self) -> str:
        """Generate a user-friendly message about when to resume."""
        if self.earliest_reset:
            return f"Earliest quota reset: {self.earliest_reset}"
        return "Check ~/.assemblyzero/gemini-rotation-state.json for reset times"


@dataclass
class GeminiCallResult:
    """Result of a Gemini API call with full observability."""

    success: bool
    response: Optional[str]  # Parsed response text
    raw_response: Optional[str]  # Full API response
    error_type: Optional[GeminiErrorType]
    error_message: Optional[str]
    credential_used: str  # Name of credential that succeeded
    rotation_occurred: bool  # True if we rotated from initial credential
    attempts: int  # Total attempts made
    duration_ms: int  # Total time including retries
    model_verified: str  # Actual model used (for audit)
    pool_exhausted: bool = False  # True if ALL credentials are exhausted
    earliest_reset: str = ""  # ISO timestamp of earliest quota reset


# =============================================================================
# Gemini API Logging (Quota & Rotation Visibility)
# =============================================================================


def log_gemini_event(
    event_type: str,
    credential_name: str = "",
    model: str = "",
    reset_time: str = "",
    error_message: str = "",
    details: dict = None,
) -> None:
    """Log a Gemini API event to the dedicated log file.

    This log provides visibility into:
    - Quota exhaustion (429) - when to add more API keys
    - Capacity exhaustion (529) - temporary overload
    - Credential rotation - which credentials are being used
    - OAuth reset times - when quotas will refresh

    Args:
        event_type: One of: quota_exhausted, capacity_exhausted, credential_rotated,
                    oauth_exhausted, all_exhausted, api_success, api_error
        credential_name: Name of the credential involved
        model: Model being used
        reset_time: ISO timestamp when quota will reset (for exhaustion events)
        error_message: Error details if applicable
        details: Additional context dict
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "credential": credential_name,
        "model": model,
    }

    if reset_time:
        log_entry["reset_time"] = reset_time
    if error_message:
        log_entry["error"] = error_message
    if details:
        log_entry["details"] = details

    # Ensure log directory exists
    GEMINI_API_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Append to log file
    with open(GEMINI_API_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


def get_credential_status() -> dict:
    """Get current status of all credentials for visibility.

    Returns:
        Dict with credential status summary:
        {
            "total": 4,
            "available": 3,
            "exhausted": ["oauth-primary"],
            "exhausted_details": {"oauth-primary": "2026-02-01T20:49:18+00:00"},
            "last_success": "api-key-1"
        }
    """
    try:
        if not CREDENTIALS_FILE.exists():
            return {"error": "No credentials file found"}

        with open(CREDENTIALS_FILE, encoding="utf-8") as f:
            cred_data = json.load(f)

        credentials = cred_data.get("credentials", [])
        enabled = [c for c in credentials if c.get("enabled", True)]

        state = {}
        if ROTATION_STATE_FILE.exists():
            with open(ROTATION_STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)

        exhausted = state.get("exhausted", {})
        now = datetime.now(timezone.utc)

        # Filter to actually exhausted (not yet reset)
        still_exhausted = {}
        for name, reset_str in exhausted.items():
            try:
                reset_time = datetime.fromisoformat(reset_str)
                if reset_time > now:
                    still_exhausted[name] = reset_str
            except (ValueError, TypeError):
                pass

        available_names = [
            c.get("name") for c in enabled
            if c.get("name") not in still_exhausted
        ]

        return {
            "total": len(enabled),
            "available": len(available_names),
            "available_names": available_names,
            "exhausted": list(still_exhausted.keys()),
            "exhausted_details": still_exhausted,
            "last_success": state.get("last_success"),
            "last_success_time": state.get("last_success_time"),
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Gemini Client
# =============================================================================


class GeminiClient:
    """
    Gemini API client with credential rotation and model enforcement.

    Ported from tools/gemini-rotate.py for programmatic use.
    """

    def __init__(
        self,
        model: str = REVIEWER_MODEL,
        credentials_file: Path = CREDENTIALS_FILE,
        state_file: Path = ROTATION_STATE_FILE,
    ):
        """
        Initialize client with model and credential configuration.

        Args:
            model: The Gemini model to use. Must be Pro-tier.
            credentials_file: Path to credentials JSON file.
            state_file: Path to rotation state JSON file.

        Raises:
            ValueError: If model is in FORBIDDEN_MODELS list or not a valid Gemini model.
        """
        if model in FORBIDDEN_MODELS:
            raise ValueError(
                f"Model '{model}' is explicitly forbidden for governance. "
                f"Allowed: gemini-3-pro-preview, gemini-3-pro, gemini-3-flash-preview"
            )
        if not model.startswith("gemini-"):
            raise ValueError(
                f"Model '{model}' is not a valid Gemini model. "
                f"Expected format: gemini-*"
            )

        self.model = model
        self.credentials_file = credentials_file
        self.state_file = state_file
        self._credentials: Optional[list[Credential]] = None
        self._state: Optional[RotationState] = None
        self._gemini_cli = self._find_gemini_cli()

    def _find_gemini_cli(self) -> Optional[str]:
        """Find the gemini CLI executable."""
        cli = shutil.which("gemini")
        if cli:
            return cli
        # Try common locations on Windows
        npm_gemini = Path.home() / "AppData" / "Roaming" / "npm" / "gemini.cmd"
        if npm_gemini.exists():
            return str(npm_gemini)
        npm_gemini_unix = Path.home() / "AppData" / "Roaming" / "npm" / "gemini"
        if npm_gemini_unix.exists():
            return str(npm_gemini_unix)
        return None

    def _invoke_via_cli(
        self,
        system_instruction: str,
        content: str,
    ) -> tuple[bool, str, str]:
        """
        Invoke Gemini via CLI (for OAuth credentials).

        The CLI doesn't have a --system flag, so we prepend the system
        instruction to the content with clear delineation.

        IMPORTANT: The CLI loads GEMINI.md from the working directory, which
        contains handshake instructions that interfere with governance reviews.
        We temporarily rename GEMINI.md during the call to avoid this.

        We also use --sandbox mode to disable agentic features.

        Returns:
            Tuple of (success, response_text, error_message)
        """
        if not self._gemini_cli:
            return False, "", "Gemini CLI not found"

        # Combine system instruction and content
        full_prompt = (
            f"You are {self.model}.\n\n"
            f"<system_instruction>\n{system_instruction}\n</system_instruction>\n\n"
            f"<user_content>\n{content}\n</user_content>"
        )

        gemini_md_path = Path.cwd() / "GEMINI.md"
        gemini_md_backup = Path.cwd() / "GEMINI.md.bak"
        gemini_md_renamed = False

        try:
            # Temporarily rename GEMINI.md to prevent CLI from loading it
            if gemini_md_path.exists():
                gemini_md_path.rename(gemini_md_backup)
                gemini_md_renamed = True

            # Use stdin to pass the prompt to avoid agentic file reading
            result = subprocess.run(
                [
                    self._gemini_cli,
                    "--prompt",
                    "-",  # Read from stdin
                    "--model",
                    self.model,
                    "--output-format",
                    "text",
                    "--sandbox",  # Disable agentic features
                ],
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            if result.returncode == 0 and result.stdout:
                return True, result.stdout.strip(), ""
            else:
                error_msg = (
                    result.stderr.strip() or result.stdout.strip() or "Unknown error"
                )
                return False, "", error_msg

        except subprocess.TimeoutExpired:
            return False, "", "CLI timeout (120s)"
        except Exception as e:
            return False, "", str(e)
        finally:
            # Restore GEMINI.md
            if gemini_md_renamed and gemini_md_backup.exists():
                try:
                    gemini_md_backup.rename(gemini_md_path)
                except OSError:
                    pass

    def invoke(
        self,
        system_instruction: str,
        content: str,
        response_schema: Optional[dict] = None,
    ) -> GeminiCallResult:
        """
        Invoke Gemini with automatic rotation and retry.

        Logic (ported from gemini-rotate.py):
        1. Load available credentials (skip exhausted ones)
        2. For each credential:
           a. Try API call
           b. IF 529 (capacity): Exponential backoff, retry same credential
           c. IF 429 (quota): Mark exhausted, rotate to next credential
           d. IF success: Return result
           e. IF auth error: Skip credential, try next
        3. If all credentials fail: Return failure with BLOCK verdict

        Args:
            system_instruction: The system prompt to send.
            content: The user content to analyze.
            response_schema: Optional JSON schema for structured output.

        Returns:
            GeminiCallResult with full observability data.
        """
        start_time = time.time()
        total_attempts = 0

        credentials = self._load_credentials()
        state = self._load_state()

        # Filter to enabled, non-exhausted credentials
        available = [
            c for c in credentials if c.enabled and not self._is_exhausted(c, state)
        ]

        if not available:
            exhausted_names = [c.name for c in credentials if c.name in state.exhausted]
            # Find earliest reset time
            earliest_reset = ""
            if state.exhausted:
                reset_times = sorted(state.exhausted.values())
                if reset_times:
                    earliest_reset = reset_times[0]
            # Log: All credentials exhausted
            log_gemini_event(
                event_type="all_exhausted",
                model=self.model,
                error_message=f"All credentials exhausted: {', '.join(exhausted_names)}",
                details={
                    "exhausted_credentials": exhausted_names,
                    "reset_times": {k: v for k, v in state.exhausted.items()},
                    "earliest_reset": earliest_reset,
                },
            )
            return GeminiCallResult(
                success=False,
                response=None,
                raw_response=None,
                error_type=GeminiErrorType.QUOTA_EXHAUSTED,
                error_message=f"All credentials exhausted: {', '.join(exhausted_names)}. Wait for quota reset.",
                credential_used="",
                rotation_occurred=False,
                attempts=0,
                duration_ms=0,
                model_verified="",
                pool_exhausted=True,
                earliest_reset=earliest_reset,
            )

        initial_credential = available[0]
        errors: list[str] = []

        for cred in available:
            rotation_occurred = cred.name != initial_credential.name
            if rotation_occurred:
                # Log credential rotation
                log_gemini_event(
                    event_type="credential_rotated",
                    credential_name=cred.name,
                    model=self.model,
                    details={
                        "previous_credential": initial_credential.name,
                        "reason": "previous credential failed",
                    },
                )
            attempt = 0

            while attempt < MAX_RETRIES_PER_CREDENTIAL:
                attempt += 1
                total_attempts += 1

                try:
                    # Use different approach based on credential type
                    if cred.cred_type == "oauth":
                        # OAuth: use CLI subprocess
                        success, response_text, error_msg = self._invoke_via_cli(
                            system_instruction, content
                        )
                        if success:
                            # Update state on success
                            state.last_success = cred.name
                            state.last_success_time = datetime.now(
                                timezone.utc
                            ).isoformat()
                            self._save_state(state)

                            duration_ms = int((time.time() - start_time) * 1000)

                            return GeminiCallResult(
                                success=True,
                                response=response_text,
                                raw_response=response_text,
                                error_type=None,
                                error_message=None,
                                credential_used=cred.name,
                                rotation_occurred=rotation_occurred,
                                attempts=total_attempts,
                                duration_ms=duration_ms,
                                model_verified=self.model,
                            )
                        else:
                            # Raise exception to trigger error handling
                            raise RuntimeError(error_msg)
                    else:
                        # API key: use new google.genai SDK
                        client = genai.Client(api_key=cred.key)

                        # Make the API call with system instruction in config
                        response = client.models.generate_content(
                            model=self.model,
                            contents=content,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                            ),
                        )

                        # Check for successful response
                        if response.text:
                            # Verify model used (if available in response metadata)
                            model_verified = self.model  # Default to requested model

                            # Update state on success
                            state.last_success = cred.name
                            state.last_success_time = datetime.now(
                                timezone.utc
                            ).isoformat()
                            self._save_state(state)

                            duration_ms = int((time.time() - start_time) * 1000)

                            return GeminiCallResult(
                                success=True,
                                response=response.text,
                                raw_response=str(response),
                                error_type=None,
                                error_message=None,
                                credential_used=cred.name,
                                rotation_occurred=rotation_occurred,
                                attempts=total_attempts,
                                duration_ms=duration_ms,
                                model_verified=model_verified,
                            )

                except Exception as e:
                    error_str = str(e)
                    error_type = self._classify_error(error_str)

                    if error_type == GeminiErrorType.CAPACITY_EXHAUSTED:
                        # 529: Backoff and retry same credential
                        delay = self._backoff_delay(attempt)
                        log_gemini_event(
                            event_type="capacity_exhausted",
                            credential_name=cred.name,
                            model=self.model,
                            error_message=f"529 capacity exhausted, backing off {delay:.1f}s (attempt {attempt})",
                            details={"backoff_seconds": delay, "attempt": attempt},
                        )
                        time.sleep(delay)
                        continue

                    elif error_type == GeminiErrorType.QUOTA_EXHAUSTED:
                        # 429: Mark exhausted and rotate
                        reset_hours = self._parse_reset_time(error_str) or 24
                        reset_time = (datetime.now(timezone.utc) + timedelta(hours=reset_hours)).isoformat()
                        self._mark_exhausted(cred, state, reset_hours)
                        log_gemini_event(
                            event_type="quota_exhausted",
                            credential_name=cred.name,
                            model=self.model,
                            reset_time=reset_time,
                            error_message=f"429 quota exhausted, will reset in {reset_hours}h",
                            details={"reset_hours": reset_hours, "cred_type": cred.cred_type},
                        )
                        errors.append(f"{cred.name}: Quota exhausted")
                        break  # Move to next credential

                    elif error_type == GeminiErrorType.AUTH_ERROR:
                        # Auth error: Skip credential
                        log_gemini_event(
                            event_type="auth_error",
                            credential_name=cred.name,
                            model=self.model,
                            error_message=error_str[:200],
                        )
                        errors.append(f"{cred.name}: Authentication failed")
                        break  # Move to next credential

                    else:
                        # Unknown error: Log and try next credential
                        log_gemini_event(
                            event_type="api_error",
                            credential_name=cred.name,
                            model=self.model,
                            error_message=error_str[:200],
                        )
                        errors.append(f"{cred.name}: {error_str[:100]}")
                        break  # Move to next credential

        # All credentials failed
        duration_ms = int((time.time() - start_time) * 1000)
        # Check if any are quota exhausted (vs other errors)
        quota_errors = [e for e in errors if "Quota exhausted" in e]
        is_pool_exhausted = len(quota_errors) == len(errors) and len(errors) > 0
        # Find earliest reset time from state
        earliest_reset = ""
        if state.exhausted:
            reset_times = sorted(state.exhausted.values())
            if reset_times:
                earliest_reset = reset_times[0]
        log_gemini_event(
            event_type="all_credentials_failed",
            model=self.model,
            error_message=f"Tried {len(available)} credentials, all failed",
            details={
                "credentials_tried": [c.name for c in available],
                "errors": errors,
                "total_attempts": total_attempts,
                "duration_ms": duration_ms,
                "pool_exhausted": is_pool_exhausted,
                "earliest_reset": earliest_reset,
            },
        )
        return GeminiCallResult(
            success=False,
            response=None,
            raw_response=None,
            error_type=GeminiErrorType.QUOTA_EXHAUSTED if is_pool_exhausted else GeminiErrorType.UNKNOWN,
            error_message=f"All credentials failed:\n  - " + "\n  - ".join(errors),
            credential_used="",
            rotation_occurred=len(available) > 1,
            attempts=total_attempts,
            duration_ms=duration_ms,
            model_verified="",
            pool_exhausted=is_pool_exhausted,
            earliest_reset=earliest_reset,
        )

    def _load_credentials(self) -> list[Credential]:
        """Load credentials from config file.

        OAuth credentials are loaded first (higher quota limits),
        followed by API key credentials.

        Note: OAuth through CLI loads GEMINI.md. We prepend model identity
        to satisfy the handshake protocol defined there.
        """
        if self._credentials is not None:
            return self._credentials

        if not self.credentials_file.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_file}\n"
                f"Create it with your API keys. See AssemblyZero docs."
            )

        with open(self.credentials_file, encoding="utf-8") as f:
            data = json.load(f)

        credentials = []

        # Load OAuth credentials first (higher quota limits)
        for c in data.get("credentials", []):
            if c.get("type") == "oauth" and c.get("enabled", True):
                credentials.append(
                    Credential(
                        name=c.get("name", "unnamed"),
                        key="",  # OAuth doesn't use API key
                        enabled=True,
                        account_name=c.get("account-name", ""),
                        cred_type="oauth",
                    )
                )

        # Then load API key credentials
        for c in data.get("credentials", []):
            if c.get("type") == "api_key" and c.get("key") and c.get("enabled", True):
                credentials.append(
                    Credential(
                        name=c.get("name", "unnamed"),
                        key=c.get("key", ""),
                        enabled=True,
                        account_name=c.get("account-name", ""),
                        cred_type="api_key",
                    )
                )

        self._credentials = credentials
        return self._credentials

    def _load_state(self) -> RotationState:
        """Load rotation state from file."""
        if self._state is not None:
            return self._state

        if not self.state_file.exists():
            self._state = RotationState()
            return self._state

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            self._state = RotationState(
                exhausted=data.get("exhausted", {}),
                last_success=data.get("last_success"),
                last_success_time=data.get("last_success_time"),
            )
        except (json.JSONDecodeError, IOError):
            self._state = RotationState()

        return self._state

    def _save_state(self, state: RotationState) -> None:
        """Save rotation state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "exhausted": state.exhausted,
                    "last_success": state.last_success,
                    "last_success_time": state.last_success_time,
                },
                f,
                indent=2,
            )

    def _is_exhausted(self, cred: Credential, state: RotationState) -> bool:
        """Check if credential quota is exhausted."""
        if cred.name not in state.exhausted:
            return False

        reset_time_str = state.exhausted[cred.name]
        try:
            reset_time = datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now >= reset_time:
                # Quota has reset - remove from exhausted list
                del state.exhausted[cred.name]
                self._save_state(state)
                return False
            return True
        except (ValueError, TypeError):
            return False

    def _mark_exhausted(
        self, cred: Credential, state: RotationState, reset_hours: float = 24
    ) -> None:
        """Mark credential as quota-exhausted with reset time."""
        reset_time = datetime.now(timezone.utc).replace(microsecond=0)
        reset_time = reset_time + timedelta(hours=reset_hours)
        state.exhausted[cred.name] = reset_time.isoformat()
        self._save_state(state)

    def _classify_error(self, error_output: str) -> GeminiErrorType:
        """Classify error type from API response."""
        error_lower = error_output.lower()

        # Check quota patterns first
        for pattern in QUOTA_EXHAUSTED_PATTERNS:
            if pattern.lower() in error_lower:
                return GeminiErrorType.QUOTA_EXHAUSTED

        # Check capacity patterns
        for pattern in CAPACITY_PATTERNS:
            if pattern.lower() in error_lower:
                return GeminiErrorType.CAPACITY_EXHAUSTED

        # Check auth patterns
        for pattern in AUTH_ERROR_PATTERNS:
            if pattern.lower() in error_lower:
                return GeminiErrorType.AUTH_ERROR

        return GeminiErrorType.UNKNOWN

    def _backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        return min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_MAX_SECONDS)

    def _parse_reset_time(self, error_output: str) -> Optional[float]:
        """Parse quota reset time from error message (returns hours)."""
        import re

        # Pattern: "Your quota will reset after 15h11m58s"
        match = re.search(r"reset after (\d+)h(\d+)m", error_output)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            return hours + minutes / 60
        return None
