"""Visual baselines made by the run under test need a baseline-free oracle (#1902).

Run 11 phase 3 generated tests/visual/baselines/*.png in the same run that
generated the renderer, then 'visual regression' compared the renderer to
its own output — a systematically wrong first render (inverted needle,
mirrored dial) becomes its own reference and passes forever. Completeness
Check 8 makes any spec that adds or regenerates baseline images declare
property assertions computable WITHOUT a baseline, in a section carrying
the literal marker "baseline-independent".
"""

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_visual_baselines_not_self_referential,
)

MARKED_SPEC = (
    "# Spec\n\n## Tests (baseline-independent)\n\n"
    "The needle tip for value 55 must lie at 147.6 degrees, computed by "
    "trigonometry with no baseline involved.\n"
)
UNMARKED_SPEC = "# Spec\n\nCompare renders against tests/visual/baselines/.\n"


def _file(path, change_type="Add"):
    return {"path": path, "change_type": change_type}


class TestTriggering:
    def test_added_baseline_png_without_marker_fails(self):
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC, [_file("tests/visual/baselines/gauge_55.png")]
        )
        assert result["passed"] is False
        assert "gauge_55.png" in result["details"]
        assert "baseline-independent" in result["details"]

    def test_modified_baseline_is_rebaselining_and_also_gated(self):
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC,
            [_file("tests/visual/baselines/gauge_55.png", "Modify")],
        )
        assert result["passed"] is False

    def test_test_tree_image_outside_baselines_dir_is_gated(self):
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC, [_file("tests/visual/golden_dial.png")]
        )
        assert result["passed"] is False

    def test_windows_style_paths_are_recognized(self):
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC,
            [_file("tests\\visual\\baselines\\gauge_0.png")],
        )
        assert result["passed"] is False


class TestPassing:
    def test_marker_satisfies_the_gate(self):
        result = check_visual_baselines_not_self_referential(
            MARKED_SPEC, [_file("tests/visual/baselines/gauge_55.png")]
        )
        assert result["passed"] is True

    def test_marker_is_case_insensitive(self):
        spec = MARKED_SPEC.replace("baseline-independent", "Baseline-Independent")
        result = check_visual_baselines_not_self_referential(
            spec, [_file("tests/visual/baselines/gauge_55.png")]
        )
        assert result["passed"] is True

    def test_spec_without_baseline_files_passes(self):
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC,
            [_file("src/boostgauge/telltale.py", "Modify")],
        )
        assert result["passed"] is True

    def test_source_tree_image_is_not_a_baseline(self):
        """An icon or docs screenshot outside tests/ is not gated."""
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC, [_file("assets/icon.png")]
        )
        assert result["passed"] is True

    def test_deleted_baseline_is_not_gated(self):
        result = check_visual_baselines_not_self_referential(
            UNMARKED_SPEC,
            [_file("tests/visual/baselines/old.png", "Delete")],
        )
        assert result["passed"] is True
