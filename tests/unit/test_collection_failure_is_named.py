"""A phase that breaks an earlier phase's imports must say so (#2035).

boostgauge #2, 2026-07-31, after #2032 made the files genuinely written:

    [N5] Results: 0 passed, 0 failed | Coverage: 0.0% | Exit: 2
    impl failed 140.6s  Green phase stopped: pytest test execution interrupted
    Error: unknown

The run had rewritten gauge.py and stingray.py without `render` and
`render_stingray`, which #1 published and #1's own tests import. pytest said
exactly that and the message was discarded, so the halt named only pytest.

Diagnosing it took a manual worktree from the [CP:post-impl] checkpoint commit
and a re-run by hand. Everything needed was in the output the whole time.
"""


from assemblyzero.workflows.testing.nodes.verify_phases import (
    describe_collection_failures,
)

LIVE_OUTPUT = """
==================== ERRORS ====================
____________ ERROR collecting tests/unit/test_gauge.py ____________
ImportError while importing test module 'tests/unit/test_gauge.py'.
Traceback:
tests/unit/test_gauge.py:13: in <module>
    from boostgauge.gauge import render
src/boostgauge/gauge.py:9: in <module>
    from boostgauge.skins.stingray import (
src/boostgauge/skins/__init__.py:3: in <module>
    from boostgauge.skins.stingray import render_stingray
E   ImportError: cannot import name 'render_stingray' from 'boostgauge.skins.stingray'
____________ ERROR collecting tests/visual/test_stingray_visual.py ____________
tests/visual/test_stingray_visual.py:13: in <module>
    from boostgauge.gauge import render
E   ImportError: cannot import name 'render' from 'boostgauge.gauge'
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
"""


class TestTheLiveFailure:
    def test_it_names_both_vanished_symbols(self):
        summary = describe_collection_failures(LIVE_OUTPUT)
        assert "boostgauge.skins.stingray.render_stingray" in summary
        assert "boostgauge.gauge.render" in summary

    def test_it_says_they_no_longer_exist(self):
        """The wording has to point at deletion, since that is what happened --
        an earlier phase published these and this phase removed them."""
        assert "no longer exists" in describe_collection_failures(LIVE_OUTPUT)

    def test_the_summary_is_not_empty(self):
        """The whole defect was an empty diagnosis."""
        assert describe_collection_failures(LIVE_OUTPUT).strip()


class TestOtherCollectionShapes:
    def test_a_missing_module_is_named(self):
        out = "E   ModuleNotFoundError: No module named 'boostgauge.collector'"
        assert "boostgauge.collector" in describe_collection_failures(out)

    def test_it_falls_back_to_the_failing_files(self):
        """A syntax error gives no import line, but the file is still the
        single most useful thing to report."""
        out = (
            "ERROR collecting tests/unit/test_thing.py\n"
            "E   SyntaxError: invalid syntax\n"
        )
        summary = describe_collection_failures(out)
        assert "tests/unit/test_thing.py" in summary

    def test_duplicates_are_collapsed(self):
        """The same import fails once per importing module; reporting it three
        times is noise."""
        out = LIVE_OUTPUT + LIVE_OUTPUT
        summary = describe_collection_failures(out)
        assert summary.count("boostgauge.gauge.render") == 1

    def test_a_long_list_is_capped(self):
        out = "\n".join(
            f"E   ImportError: cannot import name 'n{i}' from 'mod{i}'"
            for i in range(8)
        )
        summary = describe_collection_failures(out)
        assert "and 5 more" in summary


class TestQuietWhenThereIsNothingToSay:
    def test_empty_output_yields_empty(self):
        assert describe_collection_failures("") == ""

    def test_ordinary_test_failures_are_not_reported_as_import_breakage(self):
        out = "FAILED tests/unit/test_x.py::test_y - assert 1 == 2\n1 failed"
        assert describe_collection_failures(out) == ""


class TestItReachesTheHalt:
    def test_the_error_message_carries_the_detail(self):
        """stdout is not enough -- the halt payload is what the orchestrator
        reports, and it said 'unknown'."""
        from unittest.mock import patch

        from assemblyzero.workflows.testing.nodes import verify_phases

        state = {
            "test_files": ["/tmp/t.py"],
            "repo_root": "/tmp/repo",
            "audit_dir": "",
            "file_counter": 0,
            "issue_number": 2,
            "iteration_count": 0,
            "max_iterations": 5,
            "coverage_target": 95,
            "implementation_files": [],
            "skip_e2e": True,
        }
        result_stub = {
            "returncode": 2,
            "stdout": LIVE_OUTPUT,
            "stderr": "",
            "parsed": {"passed": 0, "failed": 0, "errors": 2, "coverage": 0},
        }
        with patch.object(verify_phases, "run_pytest", return_value=result_stub):
            out = verify_phases.verify_green_phase(state)

        assert out["next_node"] == "end"
        message = out.get("error_message", "")
        assert "no longer resolve" in message or "no longer exists" in message
        assert "boostgauge.gauge.render" in message
