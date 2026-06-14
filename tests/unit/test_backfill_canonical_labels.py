"""Tests for tools/backfill_canonical_labels.py.

Issue: #1213

Helper unit tests. The orchestration is exercised via integration —
tests do NOT spawn real gh subprocesses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from backfill_canonical_labels import (
    apply_label,
    get_existing_labels,
    label_state,
    list_fleet_repos,
    process_repo,
)


# ===========================================================================
# label_state — classify what gh label create --force would do
# ===========================================================================


class TestLabelState:
    """T010-T040."""

    def test_T010_create_when_absent(self):
        """Label name not present → create."""
        assert label_state({}, "implementation", "0E8A16", "desc") == "create"

    def test_T020_noop_when_present_and_matches(self):
        """Same color + same description → noop."""
        existing = {"implementation": {"color": "0E8A16", "description": "desc"}}
        assert label_state(existing, "implementation", "0E8A16", "desc") == "noop"

    def test_T030_update_when_color_drifts(self):
        """Same name, different color → update."""
        existing = {"implementation": {"color": "FF0000", "description": "desc"}}
        assert label_state(existing, "implementation", "0E8A16", "desc") == "update"

    def test_T035_update_when_description_drifts(self):
        """Same name + color, different description → update."""
        existing = {"implementation": {"color": "0E8A16", "description": "stale"}}
        assert label_state(existing, "implementation", "0E8A16", "fresh") == "update"

    def test_T040_color_case_insensitive(self):
        """GitHub color is hex — case shouldn't matter."""
        existing = {"implementation": {"color": "0e8a16", "description": "desc"}}
        assert label_state(existing, "implementation", "0E8A16", "desc") == "noop"


# ===========================================================================
# get_existing_labels — gh label list wrapper
# ===========================================================================


class TestGetExistingLabels:
    """T100-T120."""

    @patch("backfill_canonical_labels.run")
    def test_T100_parses_label_list(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "bug", "color": "ff0000", "description": "A bug"},
                {"name": "implementation", "color": "0E8A16", "description": "In flight"},
            ]),
        )
        labels = get_existing_labels("some-repo")
        assert labels is not None
        assert labels["bug"]["color"] == "ff0000"
        assert labels["implementation"]["description"] == "In flight"

    @patch("backfill_canonical_labels.run")
    def test_T110_returns_none_on_gh_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="repo not found",
        )
        assert get_existing_labels("some-repo") is None

    @patch("backfill_canonical_labels.run")
    def test_T120_returns_none_on_malformed_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        assert get_existing_labels("some-repo") is None


# ===========================================================================
# list_fleet_repos — gh repo list wrapper
# ===========================================================================


class TestListFleetRepos:
    """T200-T220."""

    @patch("backfill_canonical_labels.run")
    def test_T200_returns_sorted_names(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "Zeta"},
                {"name": "Alpha"},
                {"name": "Beta"},
            ]),
        )
        assert list_fleet_repos() == ["Alpha", "Beta", "Zeta"]

    @patch("backfill_canonical_labels.run")
    def test_T210_returns_empty_on_gh_error(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="oops")
        assert list_fleet_repos() == []

    @patch("backfill_canonical_labels.run")
    def test_T220_returns_empty_on_malformed_json(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        assert list_fleet_repos() == []


# ===========================================================================
# apply_label — gh label create --force wrapper
# ===========================================================================


class TestApplyLabel:
    """T300-T310."""

    @patch("backfill_canonical_labels.run")
    def test_T300_returns_true_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ok, err = apply_label("repo", "implementation", "0E8A16", "desc")
        assert ok is True
        assert err == ""

    @patch("backfill_canonical_labels.run")
    def test_T310_returns_false_on_gh_error(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="insufficient scope",
        )
        ok, err = apply_label("repo", "implementation", "0E8A16", "desc")
        assert ok is False
        assert "insufficient" in err


# ===========================================================================
# process_repo — orchestration of the above
# ===========================================================================


class TestProcessRepo:
    """T400-T430."""

    @patch("backfill_canonical_labels.get_existing_labels")
    @patch("backfill_canonical_labels.apply_label")
    def test_T400_dry_run_does_not_apply(self, mock_apply, mock_get):
        """Dry-run counts what would change but never calls apply_label."""
        mock_get.return_value = {}  # no labels exist → everything would be created
        result = process_repo("some-repo", dry_run=True)
        assert mock_apply.call_count == 0
        assert result.created == 2  # both canonical labels
        assert result.updated == 0
        assert result.failed == []

    @patch("backfill_canonical_labels.get_existing_labels")
    @patch("backfill_canonical_labels.apply_label")
    def test_T410_apply_creates_missing(self, mock_apply, mock_get):
        """Apply mode calls apply_label for each missing label."""
        mock_get.return_value = {}
        mock_apply.return_value = (True, "")
        result = process_repo("some-repo", dry_run=False)
        assert mock_apply.call_count == 2
        assert result.created == 2
        assert result.failed == []

    @patch("backfill_canonical_labels.get_existing_labels")
    @patch("backfill_canonical_labels.apply_label")
    def test_T420_apply_skips_already_correct(self, mock_apply, mock_get):
        """Both canonical labels already present with matching color/desc → noop."""
        from backfill_canonical_labels import _CANONICAL_LABELS
        mock_get.return_value = {
            name: {"color": color, "description": desc}
            for name, color, desc in _CANONICAL_LABELS
        }
        result = process_repo("some-repo", dry_run=False)
        assert mock_apply.call_count == 0
        assert result.created == 0
        assert result.updated == 0

    @patch("backfill_canonical_labels.get_existing_labels")
    def test_T430_error_when_label_list_fails(self, mock_get):
        mock_get.return_value = None
        result = process_repo("some-repo", dry_run=False)
        assert result.error != ""
