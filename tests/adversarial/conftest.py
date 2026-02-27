"""Shared fixtures for adversarial tests.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)

NOTE: This conftest enforces NO MOCKS. Adversarial tests must exercise
real code paths. Any test using mocks should be flagged by the validator.
"""

import pytest


@pytest.fixture
def adversarial_marker():
    """Marker fixture indicating this is an adversarial test.

    Adversarial tests are machine-generated and exercise real code paths.
    They do not use mocks, stubs, or fakes.
    """
    return True