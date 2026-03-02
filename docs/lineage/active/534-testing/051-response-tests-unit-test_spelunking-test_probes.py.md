

```python
"""Tests for all six automated spelunking probes.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from assemblyzero.workflows.janitor.probes.inventory_drift import (
    probe_inventory_drift,
)
from assemblyzero.workflows.janitor.probes.dead_references import (
    probe_dead_references,
)
from assemblyzero.workflows.janitor.probes.adr_collision import (
    probe_adr_collision,
)
from assemblyzero.workflows.janitor.probes.stale_timestamps import (
    probe_stale_timestamps,
)
from assemblyzero.workflows.janitor.probes.readme_claims import (
    probe_readme_claims,
)
from assemblyzero.workflows.janitor.probes.persona_status import (
    probe_persona_status,
)


class TestInventoryDriftProbe:
    """Tests for inventory drift probe."""

    def test_T200_drift_detected(self, tmp_path: Path) -> None:
        """T200: Inventory says 5, actual 8 -> passed=False."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T210_inventory_matches(self, tmp_path: Path) -> None:
        """T210: Inventory says 3, actual 3 -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("3 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is True

    def test_missing_inventory(self, tmp_path: Path) -> None:
        """Missing inventory file -> passed=True, skipping."""
        result = probe_inventory_drift(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_inventory_drift(tmp_path)

        assert result.probe_name == "inventory_drift"

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_inventory_drift(tmp_path)

        assert result.execution_time_ms >= 0

    def test_no_count_claims_in_inventory(self, tmp_path: Path) -> None:
        """Inventory file with no parseable count claims -> passed=True."""
        inventory = tmp_path / "inventory.md"
        inventory.write_text("# Inventory\n\nJust some text, no counts.")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is True

    def test_multiple_mismatches(self, tmp_path: Path) -> None:
        """Multiple directory count mismatches are all reported."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        docs_adrs = tmp_path / "docs" / "adrs"
        docs_adrs.mkdir(parents=True)
        for i in range(5):
            (docs_adrs / f"000{i}-adr.md").write_text(f"# ADR {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/\n3 ADRs in docs/adrs/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_summary_contains_mismatch_details(self, tmp_path: Path) -> None:
        """Summary string includes mismatch details when drift detected."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(8):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        inventory = tmp_path / "inventory.md"
        inventory.write_text("5 tools in tools/")

        result = probe_inventory_drift(tmp_path, inventory_path=inventory)

        assert "mismatch" in result.summary.lower()


class TestDeadReferencesProbe:
    """Tests for dead references probe."""

    def test_T220_dead_ref_found(self, tmp_path: Path) -> None:
        """T220: Doc references ghost.py -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/ghost.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T230_all_refs_valid(self, tmp_path: Path) -> None:
        """T230: Doc references existing file -> passed=True."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "real.py").write_text("# real")

        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/real.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_dead_references(tmp_path, doc_dirs=[tmp_path])

        assert result.probe_name == "dead_references"

    def test_no_markdown_files(self, tmp_path: Path) -> None:
        """No markdown files -> passed=True, empty findings."""
        docs = tmp_path / "docs"
        docs.mkdir()

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is True
        assert len(result.findings) == 0

    def test_multiple_dead_refs(self, tmp_path: Path) -> None:
        """Multiple dead references are all reported."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text(
            "See `tools/ghost1.py` and `tools/ghost2.py` for details."
        )

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 2

    def test_summary_lists_dead_paths(self, tmp_path: Path) -> None:
        """Summary includes the dead reference paths."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("See `tools/ghost.py` for details.")

        result = probe_dead_references(tmp_path, doc_dirs=[docs])

        assert "dead reference" in result.summary.lower()

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_dead_references(tmp_path, doc_dirs=[tmp_path])

        assert result.execution_time_ms >= 0

    def test_nonexistent_doc_dir(self, tmp_path: Path) -> None:
        """Nonexistent doc directory is handled gracefully."""
        result = probe_dead_references(
            tmp_path, doc_dirs=[tmp_path / "nonexistent"]
        )

        assert result.passed is True


class TestAdrCollisionProbe:
    """Tests for ADR collision probe."""

    def test_T240_collision_detected(self, tmp_path: Path) -> None:
        """T240: Duplicate prefix 0204 -> passed=False."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First")
        (adrs / "0204-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is False
        assert len(result.findings) >= 1

    def test_T250_no_collisions(self, tmp_path: Path) -> None:
        """T250: All unique prefixes -> passed=True."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-first.md").write_text("# First")
        (adrs / "0202-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_adr_collision(tmp_path)

        assert result.probe_name == "adr_collision"

    def test_missing_adr_dir(self, tmp_path: Path) -> None:
        """Missing ADR directory -> passed=True, skipping."""
        result = probe_adr_collision(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_empty_adr_dir(self, tmp_path: Path) -> None:
        """Empty ADR directory -> passed=True."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is True

    def test_multiple_collisions(self, tmp_path: Path) -> None:
        """Multiple prefix collisions are all detected."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0201-a.md").write_text("# a")
        (adrs / "0201-b.md").write_text("# b")
        (adrs / "0202-c.md").write_text("# c")
        (adrs / "0202-d.md").write_text("# d")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert result.passed is False
        assert len(result.findings) >= 2

    def test_collision_evidence_includes_prefix(self, tmp_path: Path) -> None:
        """Collision evidence mentions the colliding prefix."""
        adrs = tmp_path / "adrs"
        adrs.mkdir()
        (adrs / "0204-first.md").write_text("# First")
        (adrs / "0204-second.md").write_text("# Second")

        result = probe_adr_collision(tmp_path, adr_dir=adrs)

        assert any("0204" in f.evidence for f in result.findings)

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_adr_collision(tmp_path)

        assert result.execution_time_ms >= 0


class TestStaleTimestampsProbe:
    """Tests for stale timestamps probe."""

    def test_T260_stale_found(self, tmp_path: Path) -> None:
        """T260: Document with old date -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "old.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Old")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False

    def test_T270_all_fresh(self, tmp_path: Path) -> None:
        """T270: Document with recent date -> passed=True."""
        docs = tmp_path / "docs"
        docs.mkdir()
        fresh_date = (date.today() - timedelta(days=5)).isoformat()
        (docs / "fresh.md").write_text(f"<!-- Last Updated: {fresh_date} -->\n# Fresh")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_T275_stale_and_missing_timestamps(self, tmp_path: Path) -> None:
        """T275: Stale doc + missing timestamp doc -> passed=False with 2+ findings."""
        docs = tmp_path / "docs"
        docs.mkdir()

        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "stale.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Stale")
        (docs / "missing.md").write_text("# No Timestamp Here\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert len(result.findings) >= 2

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_stale_timestamps(tmp_path, doc_dirs=[tmp_path])

        assert result.probe_name == "stale_timestamps"

    def test_no_markdown_files(self, tmp_path: Path) -> None:
        """No markdown files -> passed=True."""
        docs = tmp_path / "docs"
        docs.mkdir()

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is True

    def test_missing_timestamp_only(self, tmp_path: Path) -> None:
        """Document with missing timestamp -> passed=False."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "missing.md").write_text("# No Timestamp\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert result.passed is False
        assert any(
            f.claim.claim_text == "missing timestamp" for f in result.findings
        )

    def test_custom_max_age(self, tmp_path: Path) -> None:
        """Custom max_age_days threshold is respected."""
        docs = tmp_path / "docs"
        docs.mkdir()
        test_date = (date.today() - timedelta(days=10)).isoformat()
        (docs / "doc.md").write_text(f"<!-- Last Updated: {test_date} -->\n# Doc")

        result_short = probe_stale_timestamps(tmp_path, max_age_days=5, doc_dirs=[docs])
        result_long = probe_stale_timestamps(tmp_path, max_age_days=30, doc_dirs=[docs])

        assert result_short.passed is False
        assert result_long.passed is True

    def test_summary_counts_stale_and_missing(self, tmp_path: Path) -> None:
        """Summary distinguishes stale vs missing timestamps."""
        docs = tmp_path / "docs"
        docs.mkdir()

        stale_date = (date.today() - timedelta(days=45)).isoformat()
        (docs / "stale.md").write_text(f"<!-- Last Updated: {stale_date} -->\n# Stale")
        (docs / "missing.md").write_text("# No Timestamp\n\nJust content.")

        result = probe_stale_timestamps(tmp_path, doc_dirs=[docs])

        assert "stale" in result.summary.lower() or "missing" in result.summary.lower()

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_stale_timestamps(tmp_path, doc_dirs=[tmp_path])

        assert result.execution_time_ms >= 0


class TestReadmeClaimsProbe:
    """Tests for README claims probe."""

    def test_T280_contradiction_found(self, tmp_path: Path) -> None:
        """T280: README says 'not chromadb' but code has it -> passed=False."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use chromadb for storage.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "db.py").write_text("import chromadb\nclient = chromadb.Client()")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is False

    def test_T290_claims_valid(self, tmp_path: Path) -> None:
        """T290: README says 'not quantum' and no quantum code -> passed=True."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use quantum computing.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("import os\nprint('hello')")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_readme_claims(tmp_path)

        assert result.probe_name == "readme_claims"

    def test_missing_readme(self, tmp_path: Path) -> None:
        """Missing README -> passed=True, skipping."""
        result = probe_readme_claims(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_no_negation_claims(self, tmp_path: Path) -> None:
        """README with no negation claims -> passed=True."""
        readme = tmp_path / "README.md"
        readme.write_text("# My Project\n\nThis is a great project.")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert result.passed is True

    def test_summary_lists_contradicted_terms(self, tmp_path: Path) -> None:
        """Summary includes the contradicted terms."""
        readme = tmp_path / "README.md"
        readme.write_text("This system does not use chromadb for storage.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "db.py").write_text("import chromadb")

        result = probe_readme_claims(tmp_path, readme_path=readme)

        assert "contradiction" in result.summary.lower()

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_readme_claims(tmp_path)

        assert result.execution_time_ms >= 0


class TestPersonaStatusProbe:
    """Tests for persona status probe."""

    def test_T300_persona_gaps(self, tmp_path: Path) -> None:
        """T300: 2 of 5 personas missing status -> passed=False."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\nDesigns things.\n\n"
            "## The Builder\n\nStatus: implemented\n\nBuilds things.\n\n"
            "## The Tester\n\nStatus: implemented\n\nTests things.\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
            "## The Planner\n\nPlans things.\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is False
        assert len(result.findings) == 2

    def test_all_personas_have_status(self, tmp_path: Path) -> None:
        """All personas with status markers -> passed=True."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Builder\n\nStatus: active\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is True

    def test_probe_name(self, tmp_path: Path) -> None:
        """Probe result has correct probe_name."""
        result = probe_persona_status(tmp_path)

        assert result.probe_name == "persona_status"

    def test_missing_persona_file(self, tmp_path: Path) -> None:
        """Missing persona file -> passed=True, skipping."""
        result = probe_persona_status(tmp_path)

        assert result.passed is True
        assert "not found" in result.summary.lower() or "skipping" in result.summary.lower()

    def test_summary_counts_gaps(self, tmp_path: Path) -> None:
        """Summary reports how many personas are missing status."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
            "## The Planner\n\nPlans things.\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert "2" in result.summary
        assert "3" in result.summary

    def test_findings_reference_persona_names(self, tmp_path: Path) -> None:
        """Findings mention the specific persona names that are missing status."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## The Architect\n\nStatus: implemented\n\n"
            "## The Reviewer\n\nReviews code.\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is False
        finding_texts = [f.claim.claim_text for f in result.findings]
        assert any("Reviewer" in t for t in finding_texts)

    def test_execution_time_measured(self, tmp_path: Path) -> None:
        """Execution time is a positive number."""
        result = probe_persona_status(tmp_path)

        assert result.execution_time_ms >= 0

    def test_various_status_values_accepted(self, tmp_path: Path) -> None:
        """All valid status values (implemented, active, planned, deprecated, draft) are accepted."""
        persona = tmp_path / "personas.md"
        persona.write_text(
            "# Dramatis Personae\n\n"
            "## Alpha\n\nStatus: implemented\n\n"
            "## Beta\n\nStatus: active\n\n"
            "## Gamma\n\nStatus: planned\n\n"
            "## Delta\n\nStatus: deprecated\n\n"
            "## Epsilon\n\nStatus: draft\n\n"
        )

        result = probe_persona_status(tmp_path, persona_file=persona)

        assert result.passed is True
        assert len(result.findings) == 0
```
