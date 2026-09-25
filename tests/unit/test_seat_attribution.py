"""Each node's calls are recorded under its own seat, even when every seat
shares one spec (#3577, found by the #3562 rehearsal).

The per-call record attributes a call to the seat resolved last before the
provider was built. Under `gemini.toml` every seat is `gemini:3.1-pro`, so a
node that resolved a second seat after its own would have its calls recorded
under the other one. These drive the real nodes with a run record open.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.core import call_recording
from assemblyzero.core.model_record import close_sink, open_sink
from assemblyzero.core.seats import parse_profile, using_profile

REPO = Path(__file__).resolve().parents[2]

#: Every seat on one spec, the shape of gemini.toml, offline.
UNIFORM = parse_profile('name = "uniform"\n[defaults]\nspec = "mock:review"\n', "uniform")


class _Sink:
    def __init__(self):
        self.calls: list[dict] = []

    def model(self, fields):
        self.calls.append(fields)


@pytest.fixture
def sink():
    call_recording.reset_context()
    recorder = _Sink()
    open_sink(recorder)
    yield recorder
    close_sink(recorder)
    call_recording.reset_context()


def test_the_requirements_drafter_is_recorded_as_its_seat(sink, tmp_path):
    from assemblyzero.workflows.requirements.nodes.generate_draft import generate_draft

    audit = tmp_path / "audit"
    audit.mkdir()
    generate_draft({
        "workflow_type": "issue",
        "assemblyzero_root": str(REPO),
        "target_repo": str(tmp_path),
        "config_mock_mode": True,
        "audit_dir": str(audit),
        "brief_content": "# Brief\n\nA feature.",
        "model_profile": UNIFORM,
    })

    assert sink.calls, "the drafter made no call"
    assert sink.calls[0]["seat"] == "requirements.draft"


def test_the_requirements_analysis_is_recorded_as_its_seat(sink, tmp_path):
    from importlib import import_module

    node = import_module("assemblyzero.workflows.requirements.nodes.analyze_requirements")
    node.analyze_requirements({
        "issue_title": "t",
        "issue_body": "The app shall persist state.",
        "issue_number": 7,
        "target_repo": str(tmp_path),
        "standalone_precheck": True,
        "model_profile": UNIFORM,
    })

    assert sink.calls, "the analysis made no call"
    assert sink.calls[0]["seat"] == "requirements.analyze"


def test_the_spec_drafter_resolves_its_own_seat_last():
    """Spec N2 needs an LLD on disk to reach its call; the order is pinned on
    the source, beside the N1 test that drives the same shape end to end."""
    import inspect
    from importlib import import_module

    module = import_module("assemblyzero.workflows.implementation_spec.nodes.generate_spec")
    source = inspect.getsource(module.generate_spec)
    review = source.index('resolve(state, "spec.review")')
    draft = source.index('resolve(state, "spec.draft")')
    build = source.index("drafter = get_provider(drafter_spec")
    assert review < draft < build


def test_test_augmentation_is_recorded_as_its_seat(sink):
    from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
        call_claude_for_file,
    )

    with using_profile(UNIFORM):
        call_claude_for_file("p", file_path="t.py", model="mock:review", seat="impl.augment_tests")

    assert [c["seat"] for c in sink.calls] == ["impl.augment_tests"]

    # And N4c hands its seat to both of its calls (the generation and the
    # repair), so the mechanism above is the one the node uses.
    import inspect
    from importlib import import_module

    node = import_module("assemblyzero.workflows.testing.nodes.augment_tests")
    source = inspect.getsource(node.augment_tests_for_coverage)
    assert source.count('seat="impl.augment_tests"') == 2
