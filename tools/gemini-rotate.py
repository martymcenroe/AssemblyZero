#!/usr/bin/env python3
"""
gemini-rotate.py - Gemini CLI wrapper with automatic credential rotation.

Rotates through multiple API keys and OAuth credentials to maximize
available quota across Google accounts.

Usage:
    # Direct usage (like gemini CLI)
    python gemini-rotate.py --prompt "Review this code" --model gemini-3-pro-preview

    # With file input (via stdin)
    python gemini-rotate.py --model gemini-3-pro-preview < prompt.txt

    # Check credential status
    python gemini-rotate.py --status

Credentials are stored in: ~/.agentos/gemini-credentials.json

See that file for instructions on adding new API keys.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Import secure credential manager (handles keychain + legacy file)
try:
    from agentos_credentials import CredentialManager as SecureCredentialManager
    HAS_SECURE_CREDENTIALS = True
except ImportError:
    HAS_SECURE_CREDENTIALS = False

# =============================================================================
# Configuration
# =============================================================================

CREDENTIALS_FILE = Path.home() / ".agentos" / "gemini-credentials.json"
OAUTH_CREDS_FILE = Path.home() / ".gemini" / "oauth_creds.json"
OAUTH_CREDS_BACKUP = Path.home() / ".gemini" / "oauth_creds.json.bak"
OAUTH_CREDS_DISABLED = Path.home() / ".gemini" / "oauth_creds.json.disabled"
STATE_FILE = Path.home() / ".agentos" / "gemini-rotation-state.json"

DEFAULT_MODEL = "gemini-3-pro-preview"

# Patterns that indicate quota exhaustion (non-retryable)
QUOTA_EXHAUSTED_PATTERNS = [
    "TerminalQuotaError",
    "exhausted your capacity",
    "QUOTA_EXHAUSTED",
]

# Patterns that indicate temporary capacity issues (retryable with same cred)
CAPACITY_PATTERNS = [
    "MODEL_CAPACITY_EXHAUSTED",
    "RESOURCE_EXHAUSTED",
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Credential:
    """A Gemini credential (OAuth or API key)."""
    name: str
    cred_type: str  # "oauth" or "api_key"
    key: Optional[str] = None  # Only for api_key type
    enabled: bool = True
    notes: str = ""
    account_name: str = ""  # Human-readable account identifier (e.g., email)


@dataclass
class RotationState:
    """Tracks quota status for credentials."""
    exhausted: dict = field(default_factory=dict)  # name -> reset_time_iso
    last_success: Optional[str] = None  # credential name
    last_success_time: Optional[str] = None


# =============================================================================
# Credential Management
# =============================================================================

def load_credentials() -> list[Credential]:
    """Load credentials from secure storage or legacy config file.

    Priority:
    1. Secure credential manager (keychain + env vars) if available
    2. Legacy plaintext file (~/.agentos/gemini-credentials.json)

    Note: OAuth credentials are handled separately by gemini CLI.
    """
    credentials = []

    # Try secure credential manager first (handles env vars + keychain + legacy)
    if HAS_SECURE_CREDENTIALS:
        try:
            manager = SecureCredentialManager()
            secure_creds = manager.get_credentials()
            for cred in secure_creds:
                credentials.append(Credential(
                    name=cred.name,
                    cred_type="api_key",
                    key=cred.key,
                    enabled=cred.enabled,
                    notes="",
                    account_name="",
                ))
            if credentials:
                return credentials
        except Exception as e:
            print(f"[WARNING] Secure credential manager error: {e}", file=sys.stderr)
            # Fall through to legacy loading

    # Legacy: Load from plaintext file
    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: Credentials file not found: {CREDENTIALS_FILE}", file=sys.stderr)
        print("Create it with your API keys. See AgentOS docs.", file=sys.stderr)
        sys.exit(2)

    try:
        with open(CREDENTIALS_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {CREDENTIALS_FILE}: {e}", file=sys.stderr)
        sys.exit(2)

    for cred_data in data.get("credentials", []):
        credentials.append(Credential(
            name=cred_data.get("name", "unnamed"),
            cred_type=cred_data.get("type", "api_key"),
            key=cred_data.get("key"),
            enabled=cred_data.get("enabled", True),
            notes=cred_data.get("notes", ""),
            account_name=cred_data.get("account-name", ""),  # User-friendly identifier
        ))

    return credentials


def load_state() -> RotationState:
    """Load rotation state (quota tracking)."""
    if not STATE_FILE.exists():
        return RotationState()

    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return RotationState(
            exhausted=data.get("exhausted", {}),
            last_success=data.get("last_success"),
            last_success_time=data.get("last_success_time"),
        )
    except (json.JSONDecodeError, IOError):
        return RotationState()


def save_state(state: RotationState):
    """Save rotation state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding='utf-8') as f:
        json.dump({
            "exhausted": state.exhausted,
            "last_success": state.last_success,
            "last_success_time": state.last_success_time,
        }, f, indent=2)


def is_credential_exhausted(cred: Credential, state: RotationState) -> bool:
    """Check if a credential's quota is exhausted."""
    if cred.name not in state.exhausted:
        return False

    reset_time_str = state.exhausted[cred.name]
    try:
        reset_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if now >= reset_time:
            # Quota has reset - remove from exhausted list
            del state.exhausted[cred.name]
            save_state(state)
            return False
        return True
    except (ValueError, TypeError):
        return False


def mark_credential_exhausted(cred: Credential, state: RotationState, reset_hours: float = 24):
    """Mark a credential as quota-exhausted."""
    reset_time = datetime.now(timezone.utc).replace(microsecond=0)
    # Add reset_hours (default 24h, but we'll try to parse from error message)
    from datetime import timedelta
    reset_time = reset_time + timedelta(hours=reset_hours)
    state.exhausted[cred.name] = reset_time.isoformat()
    save_state(state)


def parse_reset_time(error_output: str) -> Optional[float]:
    """Parse quota reset time from error message (returns hours)."""
    import re
    # Pattern: "Your quota will reset after 15h11m58s"
    match = re.search(r'reset after (\d+)h(\d+)m', error_output)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours + minutes / 60
    return None


# =============================================================================
# OAuth Management
# =============================================================================
#
# IMPORTANT: We DO NOT move oauth_creds.json files anymore!
#
# Why: Moving files causes race conditions when multiple agents run simultaneously.
# One agent moves the file, another agent can't find it -> browser popup.
#
# How auth works:
# - If GEMINI_API_KEY env var is set -> Uses API key (no popup)
# - If no API key -> Uses ~/.gemini/oauth_creds.json
# - API key takes PRECEDENCE over OAuth automatically
#
# So we just set/unset the env var. No file manipulation needed.

def check_oauth_available() -> bool:
    """Check if OAuth credentials file exists."""
    return OAUTH_CREDS_FILE.exists()


# =============================================================================
# Gemini Invocation
# =============================================================================

def invoke_gemini(
    cred: Credential,
    prompt: str,
    model: str,
    use_stdin: bool = False,
) -> tuple[bool, str, str]:
    """
    Invoke Gemini CLI with a specific credential.

    Returns: (success, response, raw_output)
    """
    # Set up environment based on credential type
    # NOTE: We use env vars only - no file manipulation (causes race conditions)
    env = os.environ.copy()

    if cred.cred_type == "oauth":
        # Remove API key so Gemini CLI falls through to OAuth
        env.pop("GEMINI_API_KEY", None)
        # Verify OAuth is available
        if not check_oauth_available():
            return False, "", f"OAuth credential '{cred.name}' requires ~/.gemini/oauth_creds.json (run 'gemini' once to authenticate)"
    else:  # api_key
        # Set API key - this takes precedence over OAuth automatically
        if cred.key:
            env["GEMINI_API_KEY"] = cred.key
        else:
            return False, "", f"API key credential '{cred.name}' has no key configured"

    # Build command
    gemini_path = shutil.which("gemini")
    if not gemini_path:
        return False, "", "gemini not found in PATH"

    cmd = [gemini_path, "--model", model, "--output-format", "json"]

    # Handle input
    stdin_input = None
    if use_stdin:
        stdin_input = prompt
    else:
        cmd.extend(["-p", prompt])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=stdin_input,
            env=env,
            timeout=300,  # 5 minute timeout
        )

        output = result.stdout + result.stderr

        # Check for quota exhaustion
        for pattern in QUOTA_EXHAUSTED_PATTERNS:
            if pattern.lower() in output.lower():
                return False, "", output

        # Check for success
        if result.returncode == 0 and "{" in result.stdout:
            # Parse JSON to extract response
            try:
                json_start = result.stdout.find("{")
                json_str = result.stdout[json_start:]
                # Find matching closing brace
                brace_count = 0
                json_end = 0
                for i, char in enumerate(json_str):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                if json_end > 0:
                    json_str = json_str[:json_end]

                data = json.loads(json_str)
                response = data.get("response", "")

                # Verify model used
                models_used = list(data.get("stats", {}).get("models", {}).keys())
                if models_used:
                    model_ok = any(m.startswith("gemini-3-pro") for m in models_used)
                    if not model_ok:
                        return False, "", f"Wrong model used: {models_used}. Required: gemini-3-pro*"

                return True, response, output
            except json.JSONDecodeError:
                pass

        return False, "", output

    except subprocess.TimeoutExpired:
        return False, "", "Timeout after 300 seconds"
    except Exception as e:
        return False, "", str(e)


# =============================================================================
# Main Rotation Logic
# =============================================================================

def rotate_and_invoke(
    prompt: str,
    model: str = DEFAULT_MODEL,
    use_stdin: bool = False,
) -> tuple[bool, str, str]:
    """
    Try each credential until success or all exhausted.

    Returns: (success, response, error_message)
    """
    credentials = load_credentials()
    state = load_state()

    # Filter to enabled, non-exhausted credentials
    available = []
    exhausted_creds = []

    for cred in credentials:
        if not cred.enabled:
            continue
        if is_credential_exhausted(cred, state):
            exhausted_creds.append(cred.name)
            continue
        available.append(cred)

    if not available:
        if exhausted_creds:
            return False, "", f"All credentials exhausted: {', '.join(exhausted_creds)}. Wait for quota reset."
        else:
            return False, "", "No enabled credentials found. Edit ~/.agentos/gemini-credentials.json"

    # Try each credential
    errors = []
    for cred in available:
        print(f"[ROTATE] Trying credential: {cred.name} ({cred.cred_type})", file=sys.stderr)

        success, response, output = invoke_gemini(cred, prompt, model, use_stdin)

        if success:
            print(f"[ROTATE] Success with: {cred.name}", file=sys.stderr)
            state.last_success = cred.name
            state.last_success_time = datetime.now(timezone.utc).isoformat()
            save_state(state)
            return True, response, ""

        # Check if quota exhausted
        is_quota_error = any(p.lower() in output.lower() for p in QUOTA_EXHAUSTED_PATTERNS)
        if is_quota_error:
            reset_hours = parse_reset_time(output) or 24
            mark_credential_exhausted(cred, state, reset_hours)
            print(f"[ROTATE] Credential {cred.name} quota exhausted (reset in {reset_hours:.1f}h)", file=sys.stderr)
            errors.append(f"{cred.name}: quota exhausted")
        else:
            # Other error - don't mark as exhausted, might be temporary
            errors.append(f"{cred.name}: {output[:100]}")

    return False, "", f"All credentials failed: {'; '.join(errors)}"


def print_status():
    """Print credential status."""
    credentials = load_credentials()
    state = load_state()

    print("=" * 60)
    print("GEMINI CREDENTIAL STATUS")
    print("=" * 60)
    print(f"Config file: {CREDENTIALS_FILE}")
    print(f"State file:  {STATE_FILE}")
    print()

    print("CREDENTIALS:")
    for cred in credentials:
        status = "ENABLED" if cred.enabled else "disabled"
        if cred.enabled and is_credential_exhausted(cred, state):
            reset_time = state.exhausted.get(cred.name, "unknown")
            status = f"EXHAUSTED (reset: {reset_time})"

        cred_type = cred.cred_type.upper()
        # Show account-name if available, otherwise show key preview for API keys
        account_info = cred.account_name if cred.account_name else ""
        if not account_info and cred.cred_type == "api_key" and cred.key:
            account_info = f"key={cred.key[:8]}..."

        if account_info:
            print(f"  [{status:20}] {cred.name:20} ({cred_type}) {account_info}")
        else:
            print(f"  [{status:20}] {cred.name:20} ({cred_type})")

    print()
    if state.last_success:
        print(f"Last success: {state.last_success} at {state.last_success_time}")
    print("=" * 60)


# =============================================================================
# Main
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Gemini CLI wrapper with credential rotation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple prompt
  python gemini-rotate.py --prompt "Hello"

  # With specific model
  python gemini-rotate.py --prompt "Review this" --model gemini-3-pro-preview

  # Long prompt via stdin
  python gemini-rotate.py --model gemini-3-pro-preview < prompt.txt

  # Check status
  python gemini-rotate.py --status

Credentials: ~/.agentos/gemini-credentials.json
"""
    )

    parser.add_argument(
        "--prompt", "-p",
        help="Prompt to send to Gemini"
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Print credential status and exit"
    )

    args = parser.parse_args()

    if args.status:
        print_status()
        sys.exit(0)

    # Get prompt from args or stdin
    if args.prompt:
        prompt = args.prompt
        use_stdin = False
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
        use_stdin = True
    else:
        print("ERROR: No prompt provided. Use --prompt or pipe via stdin.", file=sys.stderr)
        sys.exit(2)

    # Run with rotation
    success, response, error = rotate_and_invoke(prompt, args.model, use_stdin=use_stdin)

    if success:
        print(response)
        sys.exit(0)
    else:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
