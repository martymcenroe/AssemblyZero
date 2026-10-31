"""The LLD path extractor's "no Section 2.1" answer is a contract (ADR 0236, #3585).

Ledger 0908 asks for a raise when the content has no Section 2.1. That
prescription is not taken. On a real implementation run the content handed to
``extract_paths_from_lld`` is the implementation SPEC (``load_lld`` puts the
spec in ``lld_content``), whose files table is ``## 2. Files to Implement`` and
which has no Section 2.1 by design. The implementation node then adds every
path of the spec's files table to the allowed set itself. A raise there would
halt every implementation run; the empty answer is the legitimate one, so it is
pinned here and documented in the docstring.

Named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

from assemblyzero.utils.lld_path_enforcer import extract_paths_from_lld

SPEC = """# Implementation Spec: Something

## 1. Overview

What it does.

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/thing.py` | Add | The thing |

## 3. Current State (for Modify/Delete files)

### 3.1 `pyproject.toml`
"""

LLD = """# 1 - Feature: Something

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/thing.py` | Add | The thing |

### 2.2 Dependencies
"""


def test_97_a_spec_with_no_section_2_1_yields_no_paths_quietly(operator_alerts):
    spec = extract_paths_from_lld(SPEC)

    assert spec["all_allowed_paths"] == set()
    assert spec["implementation_files"] == []
    assert operator_alerts == []


def test_97_an_lld_with_section_2_1_yields_its_paths(operator_alerts):
    spec = extract_paths_from_lld(LLD)

    assert spec["all_allowed_paths"] == {"assemblyzero/thing.py"}


def test_97_the_docstring_says_why_absence_is_quiet():
    doc = extract_paths_from_lld.__doc__ or ""

    assert "Files to Implement" in doc
    assert "no Section 2.1" in doc
