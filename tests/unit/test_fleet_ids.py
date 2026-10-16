"""tools/fleet_ids.py and config/fleet-ids.json: one home for the fleet's public identifiers (#4165).

poetry run pytest tests/unit/test_fleet_ids.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fleet_ids  # noqa: E402

LISTED = {
    "github_owner": "martymcenroe",
    "cerberus_app_id": "3079970",
    "cerberus_bot_login": "cerberus-az[bot]",
    "pr_sentinel_app_id": "2975092",
    "cloudflare_fleet_account_id": "4fe1c5e241425c85d0f2c35c69fb45b8",
    "aws_account_id": "383687041805",
    "aws_region": "us-east-1",
}

# The prefixes a credential carries, as a closed set: a PEM block, GitHub's token
# kinds, an OpenAI or Anthropic key, an AWS access key, a Slack token, a Google API key.
SECRET_PREFIXES = (
    "-----BEGIN", "ghp_", "gho_", "ghs_", "ghu_", "ghr_", "github_pat_",
    "sk-", "AKIA", "ASIA", "xoxb-", "xoxp-", "AIza",
)


@pytest.mark.parametrize(("key", "value"), sorted(LISTED.items()))
def test_t1_get_returns_each_listed_value(key: str, value: str) -> None:
    assert fleet_ids.get(key) == value


def test_t1_an_unknown_key_raises_naming_the_known_ones() -> None:
    with pytest.raises(KeyError) as err:
        fleet_ids.get("cerberus_app")
    assert "cerberus_app_id" in str(err.value) and "aws_region" in str(err.value)


def test_t2_no_program_in_tools_hard_codes_an_app_id() -> None:
    """The IDs live in config/fleet-ids.json; a program reads them through fleet_ids.

    Untracked files are listed too, so a new tool is checked before it is committed.
    """
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard",
                             "tools"], capture_output=True, text=True, check=True).stdout.split()
    offenders = [rel for rel in listed
                 if rel.endswith(".py")
                 and any(v in (ROOT / rel).read_text(encoding="utf-8", errors="replace")
                         for v in ("3079970", "2975092"))]
    assert offenders == []


def test_t3_no_value_is_shaped_like_a_credential() -> None:
    for key, entry in fleet_ids.load().items():
        value = str(entry["value"])
        assert "-----BEGIN" not in value and not value.startswith(SECRET_PREFIXES), key


def test_the_file_says_it_is_generated() -> None:
    about = json.loads(fleet_ids.REGISTRY.read_text(encoding="utf-8"))["_about"]
    assert "Generated" in about and "never here" in about


def test_the_programs_that_need_the_ids_read_them() -> None:
    """R3: the three programs that used to hard-code an App ID now take it from fleet_ids."""
    for rel, key in (("tools/cerberus_worker_key.py", "cerberus_app_id"),
                     ("tools/deploy_cerberus_secrets.py", "cerberus_app_id"),
                     ("tools/sentinel_migrate.py", "pr_sentinel_app_id")):
        assert f'fleet_ids.get("{key}")' in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_the_sentinel_readme_cites_the_file() -> None:
    readme = (ROOT / "sentinel" / "README.md").read_text(encoding="utf-8")
    assert "config/fleet-ids.json" in readme and "2975092" not in readme
