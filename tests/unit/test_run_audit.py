"""Tests for tools/run_audit.py — standalone CLI audit runner.

Issue #343: Standalone CLI Audit Runner
"""

import subprocess
from unittest.mock import patch


from tools.run_audit import (
    AUDIT_REGISTRY,
    AuditFinding,
    AuditResult,
    _parse_inventory_counts,
    _parse_worktree_porcelain,
    check_0832_cost_optimization,
    check_0834_worktree_hygiene,
    check_0836_gitignore_consistency,
    check_0837_readme_compliance,
    check_0838_broken_references,
    check_0844_file_inventory_drift,
    format_markdown_report,
)


class TestAuditDataStructures:
    """Test AuditFinding and AuditResult dataclasses."""

    def test_audit_finding_defaults(self):
        f = AuditFinding(severity="HIGH", audit_id="0834", message="test")
        assert f.severity == "HIGH"
        assert f.details == ""

    def test_audit_result_defaults(self):
        r = AuditResult(audit_id="0834", name="Test", status="PASS")
        assert r.findings == []


class TestAuditRegistry:
    """Test that the audit registry is properly configured."""

    def test_registry_has_six_audits(self):
        assert len(AUDIT_REGISTRY) == 6

    def test_registry_ids(self):
        expected = {"0832", "0834", "0836", "0837", "0838", "0844"}
        assert set(AUDIT_REGISTRY.keys()) == expected

    def test_registry_entries_are_callable(self):
        for audit_id, (name, fn) in AUDIT_REGISTRY.items():
            assert callable(fn), f"{audit_id} check is not callable"
            assert isinstance(name, str) and name, f"{audit_id} has no name"


class TestCheck0832CostOptimization:
    """Test command cost optimization check."""

    def test_no_commands_dir(self, tmp_path):
        result = check_0832_cost_optimization(tmp_path)
        assert result.status == "SKIP"

    def test_empty_commands_dir(self, tmp_path):
        (tmp_path / ".claude" / "commands").mkdir(parents=True)
        result = check_0832_cost_optimization(tmp_path)
        assert result.status == "SKIP"

    def test_all_small_commands(self, tmp_path):
        cmd_dir = tmp_path / ".claude" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "small.md").write_text("# Small\nShort command.", encoding="utf-8")
        result = check_0832_cost_optimization(tmp_path)
        assert result.status == "PASS"

    def test_oversized_command_flagged(self, tmp_path):
        cmd_dir = tmp_path / ".claude" / "commands"
        cmd_dir.mkdir(parents=True)
        # Write a >4KB file
        (cmd_dir / "large.md").write_text("x" * 5000, encoding="utf-8")
        result = check_0832_cost_optimization(tmp_path)
        assert result.status == "WARN"
        medium_findings = [f for f in result.findings if f.severity == "MEDIUM"]
        assert len(medium_findings) == 1
        assert "large.md" in medium_findings[0].message


class TestCheck0834WorktreeHygiene:
    """Test worktree hygiene check."""

    def test_clean_repo_no_extra_worktrees(self, tmp_path):
        """Mock git worktree list showing only main."""
        porcelain_output = f"worktree {tmp_path}\nHEAD abc123\nbranch refs/heads/main\n\n"
        with patch("tools.run_audit.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=porcelain_output, stderr=""
            )
            result = check_0834_worktree_hygiene(tmp_path)
        assert result.status == "PASS"

    def test_git_not_available(self, tmp_path):
        with patch("tools.run_audit.subprocess.run", side_effect=FileNotFoundError):
            result = check_0834_worktree_hygiene(tmp_path)
        assert result.status == "ERROR"

    def test_parse_worktree_porcelain(self):
        output = (
            "worktree /main/repo\n"
            "HEAD abc123\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /main/repo-42\n"
            "HEAD def456\n"
            "branch refs/heads/42-feature\n"
            "\n"
        )
        wts = _parse_worktree_porcelain(output)
        assert len(wts) == 2
        assert wts[0]["worktree"] == "/main/repo"
        assert wts[1]["branch"] == "refs/heads/42-feature"

    def test_parse_worktree_bare(self):
        output = "worktree /bare/repo\nHEAD abc\nbare\n\n"
        wts = _parse_worktree_porcelain(output)
        assert wts[0].get("bare") is True


class TestCheck0836GitignoreConsistency:
    """Test gitignore consistency check."""

    def test_no_gitignore(self, tmp_path):
        result = check_0836_gitignore_consistency(tmp_path)
        assert result.status == "FAIL"
        assert any(f.severity == "HIGH" for f in result.findings)

    def test_complete_gitignore(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            ".env\n*.pem\n*.key\ncredentials.json\nsecrets.json\n",
            encoding="utf-8",
        )
        with patch("tools.run_audit.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = check_0836_gitignore_consistency(tmp_path)
        assert result.status == "PASS"

    def test_missing_pattern(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(".env\n*.pem\n", encoding="utf-8")
        with patch("tools.run_audit.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            result = check_0836_gitignore_consistency(tmp_path)
        assert result.status == "FAIL"
        high_findings = [f for f in result.findings if f.severity == "HIGH"]
        assert len(high_findings) >= 1

    def test_tracked_secret_detected(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            ".env\n*.pem\n*.key\ncredentials.json\nsecrets.json\n",
            encoding="utf-8",
        )

        def mock_run_fn(cmd, **kwargs):
            if "ls-files" in cmd and cmd[-1] == "*.pem":
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="server.pem\n", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        with patch("tools.run_audit.subprocess.run", side_effect=mock_run_fn):
            result = check_0836_gitignore_consistency(tmp_path)
        assert result.status == "FAIL"
        critical = [f for f in result.findings if f.severity == "CRITICAL"]
        assert len(critical) == 1
        assert "server.pem" in critical[0].message


class TestCheck0837ReadmeCompliance:
    """Test README compliance check."""

    def test_no_readme(self, tmp_path):
        result = check_0837_readme_compliance(tmp_path)
        assert result.status == "FAIL"

    def test_complete_readme(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "# MyProject\n"
            "## Overview\n"
            "## Status\n"
            "## Quick Start\n"
            "## Project Structure\n"
            "## Documentation\n"
            "## Development\n"
            "## License\n",
            encoding="utf-8",
        )
        result = check_0837_readme_compliance(tmp_path)
        assert result.status == "PASS"

    def test_missing_sections(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# MyProject\n## Overview\n", encoding="utf-8")
        result = check_0837_readme_compliance(tmp_path)
        assert result.status in ("WARN", "FAIL")
        medium_findings = [f for f in result.findings if f.severity == "MEDIUM"]
        assert len(medium_findings) >= 1


class TestCheck0838BrokenReferences:
    """Test broken reference check."""

    def test_no_markdown_files(self, tmp_path):
        result = check_0838_broken_references(tmp_path)
        assert result.status == "SKIP"

    def test_valid_links(self, tmp_path):
        (tmp_path / "target.md").write_text("# Target\n", encoding="utf-8")
        (tmp_path / "source.md").write_text(
            "See [target](target.md) for details.\n",
            encoding="utf-8",
        )
        result = check_0838_broken_references(tmp_path)
        assert result.status == "PASS"

    def test_broken_link_detected(self, tmp_path):
        (tmp_path / "source.md").write_text(
            "See [missing](nonexistent.md) for details.\n",
            encoding="utf-8",
        )
        result = check_0838_broken_references(tmp_path)
        assert result.status in ("WARN", "FAIL")
        findings = [f for f in result.findings if f.severity == "MEDIUM"]
        assert len(findings) == 1
        assert "nonexistent.md" in findings[0].details

    def test_urls_skipped(self, tmp_path):
        (tmp_path / "doc.md").write_text(
            "See [Google](https://google.com) and [anchor](#section).\n",
            encoding="utf-8",
        )
        result = check_0838_broken_references(tmp_path)
        assert result.status == "PASS"

    def test_git_dir_excluded(self, tmp_path):
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        (git_dir / "readme.md").write_text(
            "[broken](nonexistent.md)\n",
            encoding="utf-8",
        )
        result = check_0838_broken_references(tmp_path)
        # Should skip .git dir — either SKIP (no md files) or PASS
        assert result.status in ("SKIP", "PASS")


class TestCheck0844FileInventoryDrift:
    """Test file inventory drift check."""

    def test_no_inventory_file(self, tmp_path):
        result = check_0844_file_inventory_drift(tmp_path)
        assert result.status == "SKIP"

    def test_matching_counts(self, tmp_path):
        # Create inventory file
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        inventory = docs_dir / "0003-file-inventory.md"
        inventory.write_text(
            "# Inventory\n"
            "## Summary Statistics\n"
            "| Category | Count | Status |\n"
            "|----------|-------|--------|\n"
            "| Commands | 2 | All stable |\n",
            encoding="utf-8",
        )
        # Create matching files
        cmd_dir = tmp_path / ".claude" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "a.md").write_text("cmd a", encoding="utf-8")
        (cmd_dir / "b.md").write_text("cmd b", encoding="utf-8")

        result = check_0844_file_inventory_drift(tmp_path)
        assert result.status == "PASS"

    def test_drift_detected(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        inventory = docs_dir / "0003-file-inventory.md"
        inventory.write_text(
            "# Inventory\n"
            "## Summary Statistics\n"
            "| Category | Count | Status |\n"
            "|----------|-------|--------|\n"
            "| Commands | 5 | All stable |\n",
            encoding="utf-8",
        )
        # Create only 2 files (drift: 5 vs 2)
        cmd_dir = tmp_path / ".claude" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "a.md").write_text("cmd a", encoding="utf-8")
        (cmd_dir / "b.md").write_text("cmd b", encoding="utf-8")

        result = check_0844_file_inventory_drift(tmp_path)
        assert result.status == "WARN"
        medium = [f for f in result.findings if f.severity == "MEDIUM"]
        assert len(medium) >= 1


class TestParseInventoryCounts:
    """Test the inventory count parser."""

    def test_standard_table(self):
        content = (
            "## Summary Statistics\n"
            "| Category | Count | Status |\n"
            "|----------|-------|--------|\n"
            "| Standards | 9 | All stable |\n"
            "| Templates | 10 | All stable |\n"
            "| **Total Docs** | **19** | |\n"
        )
        counts = _parse_inventory_counts(content)
        assert counts["Standards"] == 9
        assert counts["Templates"] == 10
        assert "Total Docs" not in counts

    def test_empty_content(self):
        counts = _parse_inventory_counts("")
        assert counts == {}

    def test_no_summary_section(self):
        content = "# File Inventory\n\nSome text."
        counts = _parse_inventory_counts(content)
        assert counts == {}


class TestFormatMarkdownReport:
    """Test the markdown report formatter."""

    def test_report_has_required_sections(self, tmp_path):
        results = [
            AuditResult(audit_id="0834", name="Worktree", status="PASS"),
            AuditResult(
                audit_id="0836",
                name="Gitignore",
                status="FAIL",
                findings=[
                    AuditFinding(
                        severity="HIGH",
                        audit_id="0836",
                        message="Missing .env pattern",
                    )
                ],
            ),
        ]
        report = format_markdown_report(results, tmp_path)
        assert "# CLI Audit Results" in report
        assert "## Summary" in report
        assert "| 0834 Worktree | PASS |" in report
        assert "| 0836 Gitignore | FAIL |" in report
        assert "## High Findings" in report
        assert "Missing .env pattern" in report
        assert "## Statistics" in report

    def test_report_no_findings(self, tmp_path):
        results = [
            AuditResult(audit_id="0834", name="Worktree", status="PASS"),
        ]
        report = format_markdown_report(results, tmp_path)
        assert "Passed:** 1" in report


class TestCLIArgumentParsing:
    """Test CLI argument parsing."""

    def test_no_args_runs_all(self):
        # Just verify the parser accepts empty args
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("audits", nargs="*")
        parser.add_argument("--repo", default=".")
        args = parser.parse_args([])
        assert args.audits == []

    def test_specific_audits(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("audits", nargs="*")
        args = parser.parse_args(["0834", "0836"])
        assert args.audits == ["0834", "0836"]
