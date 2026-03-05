"""Tests for the Mechanical Size Gate (Issue #587)."""

import pytest

from assemblyzero.workflows.testing.nodes.implement_code import validate_code_response

def test_validate_code_response_no_shrink():
    """Test that a file that doesn't shrink passes validation."""
    existing_content = "line1\n" * 15
    new_code = "line1\n" * 15
    
    valid, err = validate_code_response(new_code, "test.py", existing_content)
    assert valid is True
    assert err == ""

def test_validate_code_response_minor_shrink():
    """Test that a file shrinking by 20% passes validation."""
    existing_content = "line1\n" * 20
    new_code = "line1\n" * 16
    
    valid, err = validate_code_response(new_code, "test.py", existing_content)
    assert valid is True
    assert err == ""

def test_validate_code_response_drastic_shrink():
    """Test that a file shrinking by >50% fails validation."""
    existing_content = "line1\n" * 270  # The PR #165 scenario
    new_code = "line1\n" * 56
    
    valid, err = validate_code_response(new_code, "test.py", existing_content)
    assert valid is False
    assert "Mechanical Size Gate: File shrank drastically" in err

def test_validate_code_response_small_files_exempt():
    """Test that small files (<10 lines) are exempt from the 50% rule."""
    existing_content = "line1\n" * 8
    new_code = "line1\n" * 3
    
    valid, err = validate_code_response(new_code, "test.py", existing_content)
    assert valid is True
    assert err == ""

def test_validate_code_response_no_existing_content():
    """Test that new files (no existing content) pass."""
    new_code = "line1\n" * 5
    
    valid, err = validate_code_response(new_code, "test.py", "")
    assert valid is True
    assert err == ""
