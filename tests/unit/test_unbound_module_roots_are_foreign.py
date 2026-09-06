"""A chain rooted in a name the spec never binds, that the target env can
import, is a dependency's API and not the target repo's (#2876).

boostgauge #4, `run-issue4-190442` and `run-issue4-193821`, spec stage:

    Spec calls methods not found in the target project's gathered symbols:
    `AccessDenied` (e.g. `raise psutil.AccessDenied()`); `Process` (e.g.
    `p = psutil.Process(pid)`); `pids` (e.g. `for pid in psutil.pids():`);
    `skipif` (e.g. `pytestmark = pytest.mark.skipif(...)`); `is_alive`
    (e.g. `assert not t.is_alive()`) ...

`_flag_calls` exempts a chain rooted in an imported name (#1948, #2411) --
but only when some fence shows the import, and a spec's excerpts routinely
omit their import header. `psutil` and `pytest` were roots the checker had
never seen bound, and an unbound root fell through to the symbol test as
though the target repo owned it. Two of three spec rounds went to dodging
correct calls.

The discriminator is the target environment, the same authority #1904 uses
for third-party imports: an unbound root that IMPORTS there is a module the
spec elided the import of; one that does not (a bare parameter such as
`win` in `def f(win): win.model_dump()`) stays judged, so #1527's founding
true positive is untouched. The probe is injected here; the real one is
`_probe_target_env` against the target venv.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    detect_unknown_method_calls,
)

TARGET_SYMBOLS = {"WindowsCollector", "DataCollector", "collect"}

# Excerpts as the drafter writes them: usage without the import header.
RUN_25_SHAPE = """# Spec

```python
def _read_cmdline_safe(self, pid: int) -> list[str]:
    try:
        return psutil.Process(pid).cmdline()
    except psutil.AccessDenied:
        return []


def _all_pids():
    for pid in psutil.pids():
        yield pid
```

```python
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows sweep")


def test_thread_stops():
    t = threading.Thread(target=lambda: None)
    t.start()
    t.join()
    assert not t.is_alive()
```
"""

FOUNDING_TRUE_POSITIVE = """# S

```python
def f(win):
    win.model_dump()
```
"""


def _env_with(*modules: str):
    known = set(modules)

    def probe(roots: list[str]) -> set[str]:
        return {r for r in roots if r in known}

    return probe


class TestUnboundModuleRootsAreForeign:
    def test_psutil_and_pytest_chains_pass_without_an_import_line(self):
        flagged = detect_unknown_method_calls(
            RUN_25_SHAPE, TARGET_SYMBOLS, "", importable=_env_with("psutil", "pytest")
        )

        for name in ("Process", "AccessDenied", "pids", "skipif", "cmdline"):
            assert name not in flagged, f"{name} flagged: {flagged.get(name)}"

    def test_a_bare_parameter_is_not_a_module_and_stays_judged(self):
        flagged = detect_unknown_method_calls(
            FOUNDING_TRUE_POSITIVE, TARGET_SYMBOLS, "", importable=_env_with("psutil", "pytest")
        )

        assert "model_dump" in flagged

    def test_a_root_the_env_cannot_import_stays_judged(self):
        """`psutil` absent from the env: the checker has no grounds to exempt it."""
        flagged = detect_unknown_method_calls(
            RUN_25_SHAPE, TARGET_SYMBOLS, "", importable=_env_with("pytest")
        )

        assert "Process" in flagged
        assert "skipif" not in flagged

    def test_no_probe_keeps_the_previous_behaviour(self):
        flagged = detect_unknown_method_calls(RUN_25_SHAPE, TARGET_SYMBOLS, "")

        assert "Process" in flagged

    def test_a_probe_that_cannot_answer_adds_no_exemption(self):
        flagged = detect_unknown_method_calls(
            RUN_25_SHAPE, TARGET_SYMBOLS, "", importable=lambda roots: set()
        )

        assert "Process" in flagged


class TestIsAliveIsAThreadMethod:
    def test_is_alive_is_not_a_project_api(self):
        flagged = detect_unknown_method_calls(RUN_25_SHAPE, TARGET_SYMBOLS, "")

        assert "is_alive" not in flagged


class TestTheProbeIsAskedOnlyAboutUnboundRoots:
    def test_bound_and_first_party_roots_are_not_probed(self):
        asked: list[list[str]] = []

        def recording(roots: list[str]) -> set[str]:
            asked.append(sorted(roots))
            return set()

        spec = """# S

```python
import json
collector = WindowsCollector({})
collector.collect()
json.dumps({})
psutil.pids()
```
"""
        detect_unknown_method_calls(spec, TARGET_SYMBOLS, "", importable=recording)

        assert asked == [["psutil"]], asked
