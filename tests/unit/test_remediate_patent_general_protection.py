"""Tests for tools/remediate_patent_general_protection.py.

Issue: #1203

Helper unit tests with mocked requests. Does NOT exercise the real
classic-PAT session — the user runs the script with their actual PAT.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from remediate_patent_general_protection import (
    CLASSIC_PROTECTION_BODY,
    delete_ruleset,
    get_ruleset,
    put_classic_protection,
    verify_classic_protection,
)


# ===========================================================================
# get_ruleset
# ===========================================================================


class TestGetRuleset:
    """T100-T120."""

    @patch("remediate_patent_general_protection.requests.get")
    def test_T100_returns_exists_on_200(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text="")
        exists, status = get_ruleset("pat", 12345)
        assert exists is True
        assert status == "exists"

    @patch("remediate_patent_general_protection.requests.get")
    def test_T110_returns_gone_on_404(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404, text="not found")
        exists, status = get_ruleset("pat", 12345)
        assert exists is False
        assert "already removed" in status

    @patch("remediate_patent_general_protection.requests.get")
    def test_T120_returns_error_on_other_status(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500, text="server error")
        exists, status = get_ruleset("pat", 12345)
        assert exists is False
        assert "500" in status


# ===========================================================================
# delete_ruleset
# ===========================================================================


class TestDeleteRuleset:
    """T200-T220."""

    @patch("remediate_patent_general_protection.requests.delete")
    def test_T200_ok_on_204(self, mock_del):
        mock_del.return_value = MagicMock(status_code=204, text="")
        ok, detail = delete_ruleset("pat", 12345)
        assert ok is True
        assert detail == "deleted"

    @patch("remediate_patent_general_protection.requests.delete")
    def test_T210_ok_on_404_idempotent(self, mock_del):
        """Already-gone ruleset is success (idempotent)."""
        mock_del.return_value = MagicMock(status_code=404, text="")
        ok, detail = delete_ruleset("pat", 12345)
        assert ok is True
        assert detail == "already gone"

    @patch("remediate_patent_general_protection.requests.delete")
    def test_T220_error_on_other_status(self, mock_del):
        mock_del.return_value = MagicMock(status_code=403, text="forbidden")
        ok, detail = delete_ruleset("pat", 12345)
        assert ok is False
        assert "403" in detail


# ===========================================================================
# put_classic_protection
# ===========================================================================


class TestPutClassicProtection:
    """T300-T320."""

    @patch("remediate_patent_general_protection.requests.put")
    def test_T300_ok_on_200(self, mock_put):
        mock_put.return_value = MagicMock(status_code=200, text="")
        ok, detail = put_classic_protection("pat")
        assert ok is True

    @patch("remediate_patent_general_protection.requests.put")
    def test_T310_ok_on_201(self, mock_put):
        mock_put.return_value = MagicMock(status_code=201, text="")
        ok, detail = put_classic_protection("pat")
        assert ok is True

    @patch("remediate_patent_general_protection.requests.put")
    def test_T320_error_on_403(self, mock_put):
        mock_put.return_value = MagicMock(
            status_code=403, text="insufficient scope",
        )
        ok, detail = put_classic_protection("pat")
        assert ok is False
        assert "403" in detail

    @patch("remediate_patent_general_protection.requests.put")
    def test_T330_body_includes_fleet_standard_fields(self, mock_put):
        """Verify the body PUTted matches the fleet standard."""
        mock_put.return_value = MagicMock(status_code=200, text="")
        put_classic_protection("pat")
        body = mock_put.call_args.kwargs["json"]
        assert body["enforce_admins"] is True
        assert body["required_pull_request_reviews"]["required_approving_review_count"] == 1
        assert "pr-sentinel / issue-reference" in body["required_status_checks"]["contexts"]
        assert body["allow_force_pushes"] is False
        assert body["allow_deletions"] is False


# ===========================================================================
# verify_classic_protection
# ===========================================================================


class TestVerifyClassicProtection:
    """T400-T440."""

    @patch("remediate_patent_general_protection.requests.get")
    def test_T400_pass_when_all_correct(self, mock_get):
        mock_resp = MagicMock(status_code=200, text="")
        mock_resp.json.return_value = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        }
        mock_get.return_value = mock_resp
        ok, detail = verify_classic_protection("pat")
        assert ok is True

    @patch("remediate_patent_general_protection.requests.get")
    def test_T410_fail_when_enforce_admins_off(self, mock_get):
        mock_resp = MagicMock(status_code=200, text="")
        mock_resp.json.return_value = {
            "enforce_admins": {"enabled": False},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        }
        mock_get.return_value = mock_resp
        ok, detail = verify_classic_protection("pat")
        assert ok is False
        assert "enforce_admins" in detail

    @patch("remediate_patent_general_protection.requests.get")
    def test_T420_fail_when_review_count_wrong(self, mock_get):
        mock_resp = MagicMock(status_code=200, text="")
        mock_resp.json.return_value = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_status_checks": {
                "contexts": ["pr-sentinel / issue-reference"],
            },
        }
        mock_get.return_value = mock_resp
        ok, detail = verify_classic_protection("pat")
        assert ok is False
        assert "review_count" in detail or "want 1" in detail

    @patch("remediate_patent_general_protection.requests.get")
    def test_T430_fail_when_check_missing(self, mock_get):
        mock_resp = MagicMock(status_code=200, text="")
        mock_resp.json.return_value = {
            "enforce_admins": {"enabled": True},
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_status_checks": {"contexts": []},
        }
        mock_get.return_value = mock_resp
        ok, detail = verify_classic_protection("pat")
        assert ok is False
        assert "pr-sentinel" in detail

    @patch("remediate_patent_general_protection.requests.get")
    def test_T440_fail_on_404(self, mock_get):
        """Branch protection doesn't exist on origin → fail loudly."""
        mock_get.return_value = MagicMock(status_code=404, text="not found")
        ok, detail = verify_classic_protection("pat")
        assert ok is False
        assert "404" in detail


# ===========================================================================
# Fleet-standard parity check
# ===========================================================================


def test_protection_body_keys_present():
    """Defensive: body must include all six fields the fleet uses."""
    assert "required_status_checks" in CLASSIC_PROTECTION_BODY
    assert "enforce_admins" in CLASSIC_PROTECTION_BODY
    assert "required_pull_request_reviews" in CLASSIC_PROTECTION_BODY
    assert "restrictions" in CLASSIC_PROTECTION_BODY
    assert "allow_force_pushes" in CLASSIC_PROTECTION_BODY
    assert "allow_deletions" in CLASSIC_PROTECTION_BODY
