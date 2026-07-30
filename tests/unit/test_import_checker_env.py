"""Third-party imports validate against the TARGET repo's environment (#1901).

Hardening run 11 phase 3: the completeness checker flagged PIL.Image /
PIL.ImageChops as "nonexistent modules" because it resolved every dotted
non-stdlib import by walking the target repo's file tree — which sees
first-party modules but never installed site-packages. Pillow was a
declared, importable dependency of boostgauge; the spec burned a revision
cycle appeasing a checker that modeled the environment wrongly.

The split now: first-party tops keep the strict exists-or-created rule
(#842's real scenario); everything else probes the target repo's own venv
in one batched find_spec call. An unanswerable environment means "cannot
validate", never "missing" (#1904: wrong-environment answers are worse
than none).
"""

from unittest.mock import patch

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _first_party_tops,
    check_import_targets_exist,
)

MODULE = "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"


def _make_repo(tmp_path, package="myproj", src_layout=False):
    base = tmp_path / "src" if src_layout else tmp_path
    pkg = base / package
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("x = 1", encoding="utf-8")
    return tmp_path


def _spec_with_imports(*imports):
    lines = "\n".join(imports)
    return f"# Spec\n\n```python\n{lines}\n```\n"


class TestFirstPartyTops:
    def test_flat_and_src_layouts_detected(self, tmp_path):
        _make_repo(tmp_path, package="flatpkg")
        _make_repo(tmp_path, package="srcpkg", src_layout=True)
        tops = _first_party_tops(tmp_path)
        assert "flatpkg" in tops
        assert "srcpkg" in tops

    def test_plain_dirs_without_init_excluded(self, tmp_path):
        (tmp_path / "docs").mkdir()
        assert "docs" not in _first_party_tops(tmp_path)


class TestFirstPartyRuleUnchanged:
    def test_hallucinated_first_party_module_still_fails(self, tmp_path):
        """#842's actual scenario survives the split — no env probe runs.

        Depth matters: `_import_resolves` deliberately forgives `pkg.name`
        when `pkg/__init__.py` exists (name may be an attribute), so the
        strict rule bites on a missing INTERMEDIATE package — the shape
        #842 actually described (assemblyzero.core.metrics).
        """
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports("from myproj.sub.metrics import Collector")
        with patch(f"{MODULE}._probe_target_env") as probe:
            result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is False
        assert "myproj.sub.metrics" in result["details"]
        probe.assert_not_called()

    def test_existing_first_party_module_passes(self, tmp_path):
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports("from myproj.core import x")
        result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is True

    def test_created_by_spec_passes(self, tmp_path):
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports("from myproj.telltale import Needle")
        files = [{"path": "myproj/telltale.py", "change_type": "Add"}]
        result = check_import_targets_exist(spec, files, str(repo))
        assert result["passed"] is True


class TestThirdPartyProbe:
    def test_the_pillow_incident_passes_when_env_importable(self, tmp_path):
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports(
            "from PIL.Image import open", "import PIL.ImageChops"
        )
        with patch(f"{MODULE}._probe_target_env", return_value={"PIL": True}):
            result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is True

    def test_genuinely_missing_third_party_fails(self, tmp_path):
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports("from requests.sessions import Session")
        with patch(
            f"{MODULE}._probe_target_env", return_value={"requests": False}
        ):
            result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is False
        assert "requests.sessions" in result["details"]
        assert "target repo" in result["details"]

    def test_probe_batches_by_top_level(self, tmp_path):
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports(
            "import PIL.Image", "import PIL.ImageChops", "import psutil.tests"
        )
        with patch(
            f"{MODULE}._probe_target_env",
            return_value={"PIL": True, "psutil": True},
        ) as probe:
            result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is True
        assert probe.call_count == 1
        assert sorted(probe.call_args.args[1]) == ["PIL", "psutil"]

    def test_unavailable_env_gives_benefit_of_the_doubt(self, tmp_path):
        """None means cannot-validate: pass, and say so in the details."""
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports("from PIL.Image import open")
        with patch(f"{MODULE}._probe_target_env", return_value=None):
            result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is True
        assert "not validated" in result["details"]

    def test_stdlib_never_reaches_the_probe(self, tmp_path):
        repo = _make_repo(tmp_path)
        spec = _spec_with_imports("from pathlib import Path", "import os.path")
        with patch(f"{MODULE}._probe_target_env") as probe:
            result = check_import_targets_exist(spec, [], str(repo))
        assert result["passed"] is True
        probe.assert_not_called()
