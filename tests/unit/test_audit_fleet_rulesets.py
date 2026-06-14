"""Tests for tools/audit_fleet_rulesets.py (#905).

Audits the fleet for repository rulesets. This test suite uses mocks
to avoid network dependency; the integration is exercised by running
the tool against the real fleet (separate manual step).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "audit_fleet_rulesets", TOOLS_DIR / "audit_fleet_rulesets.py",
)
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_fleet_rulesets"] = audit
_spec.loader.exec_module(audit)


def _ruleset_detail(
    rs_id: int = 14061333,
    name: str = "main",
    enforcement: str = "active",
    target: str = "branch",
    include: list[str] | None = None,
    rule_types: list[str] | None = None,
    bypass_actors: list[dict] | None = None,
) -> dict:
    """Mock GitHub ruleset detail response."""
    return {
        "id": rs_id,
        "name": name,
        "target": target,
        "enforcement": enforcement,
        "conditions": {"ref_name": {"include": include or ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": t} for t in (rule_types or ["pull_request"])],
        "bypass_actors": bypass_actors or [],
    }


# ---- summarize_ruleset ----


class TestSummarizeRuleset:
    def test_default_branch_target_via_default_marker(self):
        detail = _ruleset_detail(include=["~DEFAULT_BRANCH"])
        s = audit.summarize_ruleset(detail, default_branch="main")
        assert s.targets_default_branch is True

    def test_default_branch_target_via_explicit_ref(self):
        detail = _ruleset_detail(include=["refs/heads/main"])
        s = audit.summarize_ruleset(detail, default_branch="main")
        assert s.targets_default_branch is True

    def test_non_default_branch_does_not_target(self):
        detail = _ruleset_detail(include=["refs/heads/dev"])
        s = audit.summarize_ruleset(detail, default_branch="main")
        assert s.targets_default_branch is False

    def test_admin_bypass_detected(self):
        detail = _ruleset_detail(bypass_actors=[
            {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
        ])
        s = audit.summarize_ruleset(detail, "main")
        assert s.admin_role_bypass is True
        assert s.bypass_actor_count == 1

    def test_admin_bypass_absent(self):
        detail = _ruleset_detail(bypass_actors=[])
        s = audit.summarize_ruleset(detail, "main")
        assert s.admin_role_bypass is False
        assert s.bypass_actor_count == 0

    def test_non_admin_bypass_does_not_count_as_admin_bypass(self):
        detail = _ruleset_detail(bypass_actors=[
            {"actor_id": 9999, "actor_type": "Team", "bypass_mode": "always"},
        ])
        s = audit.summarize_ruleset(detail, "main")
        assert s.admin_role_bypass is False
        assert s.bypass_actor_count == 1

    def test_rule_types_extracted_in_order(self):
        detail = _ruleset_detail(rule_types=["deletion", "pull_request", "non_fast_forward"])
        s = audit.summarize_ruleset(detail, "main")
        assert s.rule_types == ["deletion", "pull_request", "non_fast_forward"]

    def test_inactive_ruleset_marked(self):
        detail = _ruleset_detail(enforcement="disabled")
        s = audit.summarize_ruleset(detail, "main")
        assert s.enforcement == "disabled"
        assert s.blocks_direct_push_to_default() is False


class TestBlocksDirectPushToDefault:
    """The blocks_direct_push_to_default property is the bottom-line
    signal: does this ruleset prevent a direct Contents-API PUT?"""

    def test_blocks_when_active_default_branch_pull_request_rule(self):
        detail = _ruleset_detail(rule_types=["pull_request"], include=["~DEFAULT_BRANCH"])
        s = audit.summarize_ruleset(detail, "main")
        assert s.blocks_direct_push_to_default() is True

    def test_does_not_block_when_disabled(self):
        detail = _ruleset_detail(enforcement="disabled", rule_types=["pull_request"])
        s = audit.summarize_ruleset(detail, "main")
        assert s.blocks_direct_push_to_default() is False

    def test_does_not_block_when_not_targeting_default(self):
        detail = _ruleset_detail(include=["refs/heads/dev"], rule_types=["pull_request"])
        s = audit.summarize_ruleset(detail, "main")
        assert s.blocks_direct_push_to_default() is False

    def test_does_not_block_when_no_blocking_rules(self):
        detail = _ruleset_detail(rule_types=["tag_name_pattern"])
        s = audit.summarize_ruleset(detail, "main")
        assert s.blocks_direct_push_to_default() is False


# ---- RepoVerdict aggregation ----


class TestRepoVerdict:
    def test_blocks_when_any_ruleset_blocks(self):
        v = audit.RepoVerdict(name="boostgauge")
        v.rulesets = [
            audit.summarize_ruleset(_ruleset_detail(rule_types=["pull_request"]), "main"),
        ]
        v.ruleset_count = 1
        assert v.blocks_direct_push is True

    def test_does_not_block_with_zero_rulesets(self):
        v = audit.RepoVerdict(name="comp-environ")
        assert v.blocks_direct_push is False

    def test_can_admin_bypass_when_all_default_target_rulesets_have_admin(self):
        v = audit.RepoVerdict(name="x")
        v.rulesets = [
            audit.summarize_ruleset(
                _ruleset_detail(bypass_actors=[
                    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
                ]),
                "main",
            ),
        ]
        assert v.can_admin_bypass is True

    def test_can_admin_bypass_false_when_any_default_target_lacks_admin(self):
        v = audit.RepoVerdict(name="x")
        v.rulesets = [
            audit.summarize_ruleset(
                _ruleset_detail(rs_id=1, bypass_actors=[
                    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
                ]),
                "main",
            ),
            audit.summarize_ruleset(
                _ruleset_detail(rs_id=2, bypass_actors=[]),
                "main",
            ),
        ]
        assert v.can_admin_bypass is False

    def test_can_admin_bypass_ignores_non_default_target_rulesets(self):
        v = audit.RepoVerdict(name="x")
        v.rulesets = [
            audit.summarize_ruleset(
                _ruleset_detail(rs_id=1, include=["~DEFAULT_BRANCH"], bypass_actors=[
                    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
                ]),
                "main",
            ),
            # Non-default-branch ruleset without admin bypass -- must NOT
            # affect the can_admin_bypass verdict for the default branch.
            audit.summarize_ruleset(
                _ruleset_detail(rs_id=2, include=["refs/heads/release"], bypass_actors=[]),
                "main",
            ),
        ]
        assert v.can_admin_bypass is True


# ---- TSV serialization ----


class TestTsvRow:
    def test_error_row_has_explicit_error_classification(self):
        v = audit.RepoVerdict(name="repo", error="network failure")
        row = v.tsv_row()
        cols = row.split("\t")
        assert cols[0] == "repo"
        assert "ERROR" in row
        assert "network failure" in cols[-1]

    def test_clean_repo_with_no_rulesets(self):
        v = audit.RepoVerdict(name="comp-environ", default_branch="main")
        row = v.tsv_row()
        cols = row.split("\t")
        assert cols[0] == "comp-environ"
        assert cols[1] == "main"
        assert cols[2] == "no"  # blocks_direct_push
        assert cols[4] == "0"   # ruleset_count

    def test_repo_with_blocking_ruleset(self):
        v = audit.RepoVerdict(name="boostgauge", default_branch="main")
        v.rulesets = [
            audit.summarize_ruleset(_ruleset_detail(rs_id=14061333), "main"),
        ]
        v.ruleset_count = 1
        row = v.tsv_row()
        cols = row.split("\t")
        assert cols[0] == "boostgauge"
        assert cols[2] == "yes"  # blocks_direct_push
        assert "14061333" in cols[5]  # ruleset_ids


# ---- audit_one orchestration ----


class TestAuditOne:
    def test_no_rulesets_returns_zero_count(self):
        repo_obj = {"name": "comp-environ", "defaultBranchRef": {"name": "main"}}
        with patch.object(audit, "list_ruleset_summaries", return_value=([], None)), \
             patch.object(audit, "get_ruleset_detail") as mock_detail:
            v = audit.audit_one(repo_obj)
        assert v.name == "comp-environ"
        assert v.ruleset_count == 0
        assert v.rulesets == []
        mock_detail.assert_not_called()

    def test_summaries_error_sets_error_field(self):
        repo_obj = {"name": "x", "defaultBranchRef": {"name": "main"}}
        with patch.object(audit, "list_ruleset_summaries",
                          return_value=([], "gh rulesets list: 503")):
            v = audit.audit_one(repo_obj)
        assert v.error is not None
        assert "503" in v.error

    def test_detail_fetched_for_each_summary(self):
        repo_obj = {"name": "boostgauge", "defaultBranchRef": {"name": "main"}}
        summaries = [
            {"id": 14061333, "name": "main", "target": "branch", "enforcement": "active"},
        ]
        detail = _ruleset_detail(rs_id=14061333)
        with patch.object(audit, "list_ruleset_summaries", return_value=(summaries, None)), \
             patch.object(audit, "get_ruleset_detail", return_value=(detail, None)):
            v = audit.audit_one(repo_obj)
        assert v.ruleset_count == 1
        assert len(v.rulesets) == 1
        assert v.rulesets[0].rs_id == 14061333

    def test_detail_error_aborts_with_error(self):
        repo_obj = {"name": "x", "defaultBranchRef": {"name": "main"}}
        summaries = [{"id": 1, "name": "x", "target": "branch", "enforcement": "active"}]
        with patch.object(audit, "list_ruleset_summaries", return_value=(summaries, None)), \
             patch.object(audit, "get_ruleset_detail", return_value=(None, "detail 503")):
            v = audit.audit_one(repo_obj)
        assert v.error is not None
        assert "detail 503" in v.error


# ---- main() integration smoke ----


class TestMainIntegration:
    def test_main_writes_tsv_with_expected_columns(self, tmp_path, capsys):
        out_path = tmp_path / "rulesets.tsv"

        fake_repos = [
            {"name": "comp-environ", "defaultBranchRef": {"name": "main"},
             "isArchived": False, "isFork": False},
            {"name": "boostgauge", "defaultBranchRef": {"name": "main"},
             "isArchived": False, "isFork": False},
        ]

        def fake_audit_one(repo_obj):
            v = audit.RepoVerdict(name=repo_obj["name"], default_branch="main")
            if repo_obj["name"] == "boostgauge":
                v.rulesets = [
                    audit.summarize_ruleset(_ruleset_detail(rs_id=14061333), "main"),
                ]
                v.ruleset_count = 1
            return v

        with patch.object(audit, "list_user_repos", return_value=fake_repos), \
             patch.object(audit, "audit_one", side_effect=fake_audit_one):
            rc = audit.main(["--output", str(out_path)])

        assert rc == 0
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        # Header + 2 rows
        assert len(lines) == 3
        # Header has all expected columns
        header_cols = lines[0].split("\t")
        assert "repo" in header_cols
        assert "blocks_direct_push_to_default" in header_cols
        assert "admin_bypass_present" in header_cols
        assert "ruleset_count" in header_cols

    def test_main_summary_lists_repos_requiring_bootstrap(self, tmp_path, capsys):
        out_path = tmp_path / "rulesets.tsv"

        fake_repos = [
            {"name": "comp-environ", "defaultBranchRef": {"name": "main"},
             "isArchived": False, "isFork": False},
            {"name": "boostgauge", "defaultBranchRef": {"name": "main"},
             "isArchived": False, "isFork": False},
        ]

        def fake_audit_one(repo_obj):
            v = audit.RepoVerdict(name=repo_obj["name"], default_branch="main")
            if repo_obj["name"] == "boostgauge":
                v.rulesets = [
                    audit.summarize_ruleset(_ruleset_detail(rs_id=14061333), "main"),
                ]
                v.ruleset_count = 1
            return v

        with patch.object(audit, "list_user_repos", return_value=fake_repos), \
             patch.object(audit, "audit_one", side_effect=fake_audit_one):
            audit.main(["--output", str(out_path)])

        out = capsys.readouterr().out
        assert "REPOS THAT WILL REQUIRE BOOTSTRAP" in out
        assert "boostgauge" in out
        # comp-environ has no rulesets -> NOT listed in the bootstrap-needed group
        # (it appears earlier in the per-repo trace but not in the summary list)
        bootstrap_section = out.split("REPOS THAT WILL REQUIRE BOOTSTRAP")[1]
        assert "comp-environ" not in bootstrap_section
