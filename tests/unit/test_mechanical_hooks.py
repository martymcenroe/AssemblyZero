import os
from pathlib import Path
from assemblyzero.workflows.testing.state import TestingWorkflowState
from assemblyzero.workflows.testing.nodes.mechanical_hooks import mechanical_hooks

def test_mechanical_hooks_creates_file(tmp_path: Path):
    # Setup mock repo with .unleashed.json
    unleashed_path = tmp_path / ".unleashed.json"
    unleashed_path.write_text(
        '{"post_implement_command": "echo \\"test output\\" > generated.txt"}',
        encoding="utf-8"
    )
    
    # Initialize git repo so 'git add' works
    os.system(f"cd {tmp_path} && git init")
    
    state = TestingWorkflowState(repo_root=str(tmp_path))
    mechanical_hooks(state)
    
    # Check if file was created
    generated_file = tmp_path / "generated.txt"
    assert generated_file.exists()
    assert generated_file.read_text(encoding="utf-8").strip() == "test output"
    
    # Check if file was staged
    status = os.popen(f"cd {tmp_path} && git status --porcelain").read()
    assert "A  generated.txt" in status or "A  generated.txt" in status.strip()
