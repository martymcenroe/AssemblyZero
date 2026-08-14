"""New repos are born on the Python the fleet actually runs (#2274).

The scaffolder stamped `^3.10` into every new repo's pyproject and `"3.10"`
into its release workflow. That is the #2185 defect class built into the
generator rather than inherited: a floor nothing in the fleet runs lets the
resolver choose package versions with no cp314 wheels, and on a workstation
with no C compiler the source build fails, so `poetry install` exits nonzero
forever.

The pinning here is deliberately not "the two constants are equal". A floor and
a CI version are different claims and AssemblyZero's own configuration holds
them at different values. What must never drift is each constant from the
parent repo's real configuration, so that is what these tests read -- the
actual `pyproject.toml` and the actual `ci.yml`, not a copy of their values.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import new_repo  # noqa: E402


def assemblyzero_floor() -> str:
    """The floor AssemblyZero itself declares, read from its pyproject."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires = data["project"]["requires-python"]
    match = re.search(r">=\s*(\d+\.\d+)", requires)
    assert match, f"could not read a floor out of {requires!r}"
    return match.group(1)


def assemblyzero_ci_version() -> str:
    """The version AssemblyZero's own CI installs."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    match = re.search(r"python-version:\s*['\"]?(\d+\.\d+)", ci)
    assert match, "could not read a python-version out of ci.yml"
    return match.group(1)


class TestTheConstantsTrackTheParentRepo:
    """A comment claiming the constants match is not a check. These read the
    parent repo's real files, so moving the fleet floor fails the scaffolder
    until it follows."""

    def test_the_floor_matches_assemblyzeros_own(self):
        assert new_repo.FLEET_PYTHON_FLOOR == assemblyzero_floor()

    def test_the_ci_version_matches_assemblyzeros_own(self):
        assert new_repo.FLEET_PYTHON_CI == assemblyzero_ci_version()

    def test_the_ci_version_is_not_below_the_floor(self):
        """The one relationship between them that must hold whatever they are:
        a workflow may not run on an interpreter the project disclaims."""
        as_tuple = lambda v: tuple(int(p) for p in v.split("."))  # noqa: E731
        assert as_tuple(new_repo.FLEET_PYTHON_CI) >= as_tuple(
            new_repo.FLEET_PYTHON_FLOOR
        )

    def test_the_retired_floor_is_gone(self):
        """#2185's floor, specifically. Nothing in the fleet runs below 3.14 and
        the ruled floor is 3.12, so a 3.10 anywhere here is the old defect."""
        assert new_repo.FLEET_PYTHON_FLOOR != "3.10"
        assert new_repo.FLEET_PYTHON_CI != "3.10"


class TestBothSurfacesAreStamped:
    def test_poetry_init_is_handed_the_floor(self):
        source = (ROOT / "tools" / "new_repo.py").read_text(encoding="utf-8")
        assert 'f"^{FLEET_PYTHON_FLOOR}"' in source
        assert '"--python", "^3.10"' not in source

    def test_the_release_workflow_carries_no_literal_version(self):
        source = (ROOT / "tools" / "new_repo.py").read_text(encoding="utf-8")
        assert 'python-version: "3.10"' not in source
        assert f'python-version: "{new_repo._PYTHON_CI_SENTINEL}"' in source

    def test_no_stray_310_remains_in_the_generator(self):
        """Catches a third surface nobody remembered, which is how the first two
        got out of step."""
        source = (ROOT / "tools" / "new_repo.py").read_text(encoding="utf-8")
        offenders = [
            line
            for line in source.splitlines()
            if "3.10" in line and not line.lstrip().startswith("#")
        ]
        assert not offenders, f"literal 3.10 still stamped: {offenders}"


class TestTheSentinelIsActuallySubstituted:
    """A sentinel that reaches disk is worse than the literal it replaced --
    `python-version: "__FLEET_PYTHON_CI__"` fails at workflow run time, far
    from here."""

    @pytest.fixture
    def rendered(self) -> str:
        """The template as it reaches disk.

        Taken from source and substituted the way the write site does, rather
        than by running `create_python_project`, which shells out to poetry and
        the GitHub API. `test_the_substitution_is_wired_at_the_write_site`
        below is what ties this rendering to the real one.
        """
        source = (ROOT / "tools" / "new_repo.py").read_text(encoding="utf-8")
        template = source.split("release_yml = '''\\", 1)[1].split("'''", 1)[0]
        assert new_repo._PYTHON_CI_SENTINEL in template, (
            "the template no longer carries the sentinel; this fixture is "
            "rendering the wrong block"
        )
        return template.replace(
            new_repo._PYTHON_CI_SENTINEL, new_repo.FLEET_PYTHON_CI
        )

    def test_the_sentinel_does_not_survive(self, rendered):
        assert new_repo._PYTHON_CI_SENTINEL not in rendered

    def test_the_rendered_workflow_names_the_fleet_version(self, rendered):
        assert f'python-version: "{new_repo.FLEET_PYTHON_CI}"' in rendered

    def test_the_substitution_is_wired_at_the_write_site(self):
        """The template and the write are far apart in the file; this asserts
        the write applies the replacement rather than writing the raw template."""
        source = (ROOT / "tools" / "new_repo.py").read_text(encoding="utf-8")
        assert "release_yml.replace(_PYTHON_CI_SENTINEL, FLEET_PYTHON_CI)" in source


class TestTheFloorSurvivesPep440Normalisation:
    """`poetry init` writes the caret form and #1573's normaliser rewrites it.
    The floor has to come out the other side intact."""

    def test_the_caret_floor_normalises_to_the_same_floor(self):
        floor = new_repo.FLEET_PYTHON_FLOOR
        text = f'requires-python = "^{floor}"\n'
        out = new_repo._normalize_requires_python(text)
        major = floor.split(".")[0]
        assert out == f'requires-python = ">={floor},<{int(major) + 1}.0"\n'
