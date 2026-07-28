"""Issue #1842: the skip-on-resume guard must never fire on retry iterations.

The #547 optimization skips Claude calls for Add files already on disk. On a
test-failure retry every file is already on disk (iteration 0 wrote them), so
the unscoped guard turned every retry into a no-op: previous_error was wired
into the prompt but the prompt was never built, N5 re-ran identical files, and
the stagnation detector halted the run. These tests pin the scoping.
"""

from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
    _should_skip_existing_file,
)


class TestSkipOnResumeScoping:
    def test_first_pass_skips_existing_file(self, tmp_path):
        """Iteration 0 + file on disk = the #547 resume case. Skip."""
        f = tmp_path / "config.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert _should_skip_existing_file("Add", f, iteration_count=0) is True

    def test_retry_iteration_never_skips(self, tmp_path):
        """Iteration >0 exists to rewrite files with failure feedback."""
        f = tmp_path / "config.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert _should_skip_existing_file("Add", f, iteration_count=1) is False
        assert _should_skip_existing_file("Add", f, iteration_count=2) is False

    def test_first_pass_missing_file_not_skipped(self, tmp_path):
        assert (
            _should_skip_existing_file("Add", tmp_path / "new.py", iteration_count=0)
            is False
        )

    def test_first_pass_empty_file_not_skipped(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("", encoding="utf-8")
        assert _should_skip_existing_file("Add", f, iteration_count=0) is False

    def test_modify_files_never_skipped(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert _should_skip_existing_file("Modify", f, iteration_count=0) is False
