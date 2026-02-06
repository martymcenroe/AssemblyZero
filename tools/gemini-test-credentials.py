#!/usr/bin/env python3
"""
gemini-test-credentials.py - Test all Gemini credentials.

Tests each credential in ~/.assemblyzero/gemini-credentials.json
(including disabled ones) to verify they work.

Usage:
    python gemini-test-credentials.py
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CREDENTIALS_FILE = Path.home() / ".assemblyzero" / "gemini-credentials.json"
OAUTH_CREDS_FILE = Path.home() / ".gemini" / "oauth_creds.json"
TEST_PROMPT = "Say hello in exactly 3 words."
TEST_MODEL = "gemini-2.0-flash"  # Fast model for testing

# Find gemini CLI
GEMINI_CLI = shutil.which("gemini")
if not GEMINI_CLI:
    # Try common locations
    npm_gemini = Path.home() / "AppData" / "Roaming" / "npm" / "gemini.cmd"
    if npm_gemini.exists():
        GEMINI_CLI = str(npm_gemini)
    else:
        npm_gemini_unix = Path.home() / "AppData" / "Roaming" / "npm" / "gemini"
        if npm_gemini_unix.exists():
            GEMINI_CLI = str(npm_gemini_unix)


def test_api_key(name: str, key: str, account: str) -> tuple[bool, str]:
    """Test an API key credential."""
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = key

    try:
        result = subprocess.run(
            [GEMINI_CLI, "--prompt", TEST_PROMPT, "--model", TEST_MODEL],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )

        if result.returncode == 0:
            response = result.stdout.strip()[:50]
            return True, f"OK - Response: {response}"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            # Parse common errors
            error_lower = error.lower()
            if "api_key_invalid" in error_lower or "api key not valid" in error_lower:
                return False, "INVALID KEY"
            elif "quota" in error_lower or "exhausted" in error_lower:
                return False, "QUOTA EXHAUSTED"
            elif "429" in error or "resource_exhausted" in error_lower:
                return False, "RATE LIMITED (429)"
            elif "529" in error:
                return False, "GEMINI OVERLOADED (529)"
            elif "401" in error:
                return False, "AUTH FAILED (401)"
            elif "403" in error:
                return False, "PERMISSION DENIED (403)"
            else:
                return False, f"ERROR: {error[:100]}"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT (30s)"
    except FileNotFoundError:
        return False, f"gemini CLI not found (GEMINI_CLI={GEMINI_CLI})"
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def test_oauth() -> tuple[bool, str]:
    """Test OAuth credential."""
    if not OAUTH_CREDS_FILE.exists():
        return False, "NO OAUTH FILE (~/.gemini/oauth_creds.json)"

    # Temporarily unset API key to force OAuth
    env = os.environ.copy()
    env.pop("GEMINI_API_KEY", None)

    try:
        result = subprocess.run(
            [GEMINI_CLI, "--prompt", TEST_PROMPT, "--model", TEST_MODEL],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )

        if result.returncode == 0:
            response = result.stdout.strip()[:50]
            return True, f"OK - Response: {response}"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            if "529" in error:
                return False, "GEMINI OVERLOADED (529)"
            elif "quota" in error.lower():
                return False, "QUOTA EXHAUSTED"
            else:
                return False, f"ERROR: {error[:100]}"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT (30s)"
    except FileNotFoundError:
        return False, f"gemini CLI not found (GEMINI_CLI={GEMINI_CLI})"
    except Exception as e:
        return False, f"EXCEPTION: {e}"


def main():
    if not GEMINI_CLI:
        print("ERROR: gemini CLI not found!")
        print("Install with: npm install -g @anthropic/gemini-cli")
        sys.exit(1)

    print("=" * 60)
    print("GEMINI CREDENTIAL TEST")
    print(f"Testing with model: {TEST_MODEL}")
    print(f"Prompt: \"{TEST_PROMPT}\"")
    print("=" * 60)
    print()

    # Load credentials
    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: Credentials file not found: {CREDENTIALS_FILE}")
        sys.exit(1)

    try:
        with open(CREDENTIALS_FILE) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in credentials file: {e}")
        sys.exit(1)

    credentials = config.get("credentials", [])

    if not credentials:
        print("No credentials found in config file.")
        sys.exit(1)

    results = []

    for cred in credentials:
        name = cred.get("name", "unnamed")
        cred_type = cred.get("type", "unknown")
        enabled = cred.get("enabled", False)
        account = cred.get("account-name", "")

        status_str = "ENABLED" if enabled else "disabled"
        account_str = f" ({account})" if account else ""

        print(f"Testing: {name}{account_str} [{cred_type}] [{status_str}]")
        print("-" * 50)

        if cred_type == "oauth":
            success, message = test_oauth()
        elif cred_type == "api_key":
            key = cred.get("key", "")
            if not key:
                success, message = False, "NO KEY CONFIGURED"
            else:
                success, message = test_api_key(name, key, account)
        else:
            success, message = False, f"UNKNOWN TYPE: {cred_type}"

        status_icon = "PASS" if success else "FAIL"
        print(f"  {status_icon} {message}")
        print()

        results.append((name, enabled, success, message))

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    working = [r for r in results if r[2]]
    enabled_working = [r for r in working if r[1]]

    print(f"Total credentials: {len(results)}")
    print(f"Working: {len(working)}")
    print(f"Working + Enabled: {len(enabled_working)}")
    print()

    if not working:
        print("WARNING: No working credentials!")
        sys.exit(1)
    elif not enabled_working:
        print("WARNING: Working credentials exist but are disabled!")
        print("Consider enabling them in ~/.assemblyzero/gemini-credentials.json")
    else:
        print("All good! You have working enabled credentials.")


if __name__ == "__main__":
    main()
