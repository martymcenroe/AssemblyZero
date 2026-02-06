"""Unit tests for fixture loading behavior.

Issue #152: Mock-mode branches fail silently when fixtures missing

TDD approach: These tests define the EXPECTED behavior where missing
fixtures should raise clear errors instead of returning empty data.
"""

import pytest
from pathlib import Path
from unittest.mock import patch


class TestLoadFixtureMissingFile:
    """Tests for load_fixture when fixture file is missing.

    Issue #152: Currently returns [] silently, should raise FileNotFoundError.
    """

    def test_raises_error_when_fixture_missing(self, tmp_path):
        """Test that load_fixture raises FileNotFoundError for missing fixtures."""
        from assemblyzero.workflows.scout.nodes import load_fixture

        # Point to a non-existent fixture
        with patch.object(
            Path, 'parent',
            new_callable=lambda: property(lambda self: tmp_path)
        ):
            # This should raise FileNotFoundError, not return []
            with pytest.raises(FileNotFoundError) as exc_info:
                load_fixture("nonexistent_fixture.json")

            # Error message should be helpful
            assert "nonexistent_fixture.json" in str(exc_info.value)

    def test_raises_error_with_helpful_message(self, tmp_path):
        """Test that error message includes fixture name and path."""
        from assemblyzero.workflows.scout.nodes import load_fixture

        # Mock the fixture directory to be empty
        fixture_dir = tmp_path / "tests" / "fixtures" / "scout"
        fixture_dir.mkdir(parents=True)

        # Temporarily modify the module to use our temp dir
        import assemblyzero.workflows.scout.nodes as nodes_module
        original_file = nodes_module.__file__

        with patch.object(nodes_module, '__file__', str(tmp_path / "fake" / "nodes.py")):
            with pytest.raises(FileNotFoundError) as exc_info:
                load_fixture("missing.json")

            error_msg = str(exc_info.value)
            assert "missing.json" in error_msg

    def test_loads_existing_fixture_successfully(self, tmp_path):
        """Test that existing fixtures still load correctly."""
        from assemblyzero.workflows.scout.nodes import load_fixture
        import json

        # Create a fixture file
        fixture_dir = tmp_path / "tests" / "fixtures" / "scout"
        fixture_dir.mkdir(parents=True)
        fixture_file = fixture_dir / "test_fixture.json"
        test_data = [{"name": "test-repo", "stars": 100}]
        fixture_file.write_text(json.dumps(test_data))

        import assemblyzero.workflows.scout.nodes as nodes_module

        with patch.object(nodes_module, '__file__', str(tmp_path / "assemblyzero" / "workflows" / "scout" / "nodes.py")):
            result = load_fixture("test_fixture.json")

        assert result == test_data


class TestExplorerNodeWithMissingFixture:
    """Tests for explorer_node when fixture is missing in offline mode."""

    def test_explorer_fails_clearly_when_fixture_missing(self, tmp_path):
        """Test explorer_node raises error when fixture missing in offline mode."""
        from assemblyzero.workflows.scout.nodes import explorer_node
        import assemblyzero.workflows.scout.nodes as nodes_module

        # Create empty fixture directory
        fixture_dir = tmp_path / "tests" / "fixtures" / "scout"
        fixture_dir.mkdir(parents=True)

        state = {
            "topic": "test",
            "min_stars": 100,
            "offline_mode": True,
            "repo_limit": 3,
        }

        with patch.object(nodes_module, '__file__', str(tmp_path / "assemblyzero" / "workflows" / "scout" / "nodes.py")):
            # Should raise FileNotFoundError, not silently return empty repos
            with pytest.raises(FileNotFoundError) as exc_info:
                explorer_node(state)

            assert "github_search_response.json" in str(exc_info.value)


class TestExtractorNodeWithMissingFixture:
    """Tests for extractor_node when fixture is missing in offline mode."""

    def test_extractor_fails_clearly_when_fixture_missing(self, tmp_path):
        """Test extractor_node raises error when fixture missing in offline mode."""
        from assemblyzero.workflows.scout.nodes import extractor_node
        import assemblyzero.workflows.scout.nodes as nodes_module

        # Create empty fixture directory
        fixture_dir = tmp_path / "tests" / "fixtures" / "scout"
        fixture_dir.mkdir(parents=True)

        state = {
            "found_repos": [{"name": "test/repo", "stars": 100, "description": "", "url": "", "license_type": "MIT"}],
            "current_token_usage": 0,
            "max_tokens": 30000,
            "offline_mode": True,
        }

        with patch.object(nodes_module, '__file__', str(tmp_path / "assemblyzero" / "workflows" / "scout" / "nodes.py")):
            # Should raise FileNotFoundError, not silently proceed with empty content
            with pytest.raises(FileNotFoundError) as exc_info:
                extractor_node(state)

            assert "github_content_response.json" in str(exc_info.value)
