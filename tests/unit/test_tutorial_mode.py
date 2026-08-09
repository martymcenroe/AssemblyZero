"""Tutorial narration mode (#2160): the live roll, annotated for newcomers.

Same emit-once architecture as its siblings: the view annotates, the roll
never knows, the log on disk stays complete.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

from assemblyzero.workflows.requirements.atlas import (  # noqa: E402
    ATLAS as REQ_ATLAS,
    TOTAL_STEPS as REQ_TOTAL,
)


def _node_line(node_id: str) -> str:
    entry = REQ_ATLAS[node_id]
    return (
        f"NODE [{entry['ordinal']}/{REQ_TOTAL}] {entry['title']} -- "
        f"{entry['goal']}\n"
    )


class TestAnnotation:
    def test_a_node_line_gets_its_teach_text_indented(self):
        view = sr._NarrationView("tutorial")
        out = view.feed("n", _node_line("N0c_analyze_requirements"))
        assert "NODE [3/11]" in out
        assert "  | " in out
        assert "cheapest possible failure" in out, "teach text comes from the atlas"

    def test_totals_disambiguate_titles_both_graphs_share(self):
        from assemblyzero.workflows.implementation_spec.atlas import (
            ATLAS as SPEC_ATLAS, TOTAL_STEPS as SPEC_TOTAL,
        )
        view = sr._NarrationView("tutorial")
        req = view.feed("a", _node_line("N0b_analyze_codebase"))
        spec_entry = SPEC_ATLAS["N1_analyze_codebase"]
        spec = view.feed("b", (
            f"NODE [{spec_entry['ordinal']}/{SPEC_TOTAL}] "
            f"{spec_entry['title']} -- {spec_entry['goal']}\n"
        ))
        assert REQ_ATLAS["N0b_analyze_codebase"]["teach"].split()[0] in req
        assert spec_entry["teach"].split()[-1].rstrip(".") in spec

    def test_an_unknown_title_renders_the_line_alone(self):
        view = sr._NarrationView("tutorial")
        out = view.feed("n", "NODE [9/99] mystery step -- does things\n")
        assert "mystery step" in out
        assert "  | " not in out

    def test_refusals_and_storms_teach_too(self):
        view = sr._NarrationView("tutorial")
        storm = view.feed("n", "STORM BACKOFF 15m before attempt 2/3\n")
        blocked = view.feed("n", "BLOCKED: this machine is not healthy enough\n")
        assert "provider stopped answering" in storm
        assert "system working" in blocked

    def test_detail_lines_stay_filtered_tutorial_implies_terse(self):
        view = sr._NarrationView("tutorial")
        assert view.feed("n", "incidental model chatter\n") == ""

    def test_toggle_leaves_tutorial_for_terse(self):
        view = sr._NarrationView("tutorial")
        assert view.toggle() == "terse"


class TestOrientation:
    def test_the_orientation_file_prints_once_on_attach(self, tmp_path, capsys):
        runs = tmp_path / "runs"
        runs.mkdir()
        (runs / "detached-launcher.log").write_bytes(b"")

        with patch.object(sr, "_task_status", lambda: "Ready"), \
                patch.object(sr, "_poll_view_keys", lambda v: None), \
                patch.object(sr.time, "sleep", lambda s: None):
            sr.follow_roll(runs, wait_for_start=False, level="tutorial")

        out = capsys.readouterr().out
        assert "Watching a roll, for the first time" in out

    def test_the_orientation_names_the_real_file(self):
        path = (
            Path(sr.__file__).resolve().parents[1]
            / "docs" / "tutorial" / "0001-follow-orientation.md"
        )
        assert path.is_file(), "the curriculum file must exist where the code looks"
