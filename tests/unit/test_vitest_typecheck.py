import pytest
import os
import json
from unittest.mock import patch

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runners.jest_runner import JestRunner

@pytest.fixture
def temp_project_dir(tmp_path):
    return str(tmp_path)

def test_vitest_typecheck_with_package_json(temp_project_dir):
    with patch("shutil.which", return_value="/usr/bin/npx"):
        with patch("assemblyzero.workflows.testing.runners.jest_runner.JestRunner._run_subprocess") as mock_sub:
            # Setup project with package.json
            with open(os.path.join(temp_project_dir, "package.json"), "w") as f:
                json.dump({"scripts": {"typecheck": "tsc --noEmit"}}, f)
                
            config = {"framework": TestFramework.VITEST}
            runner = JestRunner(config, project_root=temp_project_dir)
            
            mock_sub.side_effect = [
                ("typecheck output", 0),
                ('{"success":true,"numPassedTests":1}', 0)
            ]
            runner.run_tests()
            
            assert mock_sub.call_count == 2
            args1, _ = mock_sub.call_args_list[0]
            assert args1[0] == ["npm", "run", "typecheck"]
            args2, _ = mock_sub.call_args_list[1]
            assert args2[0] == ["npx", "vitest", "run", "--reporter=json"]

def test_vitest_typecheck_with_tsconfig(temp_project_dir):
    with patch("shutil.which", return_value="/usr/bin/npx"):
        with patch("assemblyzero.workflows.testing.runners.jest_runner.JestRunner._run_subprocess") as mock_sub:
            # Setup project with tsconfig.json only
            with open(os.path.join(temp_project_dir, "tsconfig.json"), "w") as f:
                f.write("{}")
                
            config = {"framework": TestFramework.VITEST}
            runner = JestRunner(config, project_root=temp_project_dir)
            
            mock_sub.side_effect = [
                ("typecheck output", 0),
                ('{"success":true,"numPassedTests":1}', 0)
            ]
            runner.run_tests()
            
            assert mock_sub.call_count == 2
            args1, _ = mock_sub.call_args_list[0]
            assert args1[0] == ["npx", "tsc", "--noEmit"]
            args2, _ = mock_sub.call_args_list[1]
            assert args2[0] == ["npx", "vitest", "run", "--reporter=json"]

def test_vitest_typecheck_failure(temp_project_dir):
    with patch("shutil.which", return_value="/usr/bin/npx"):
        with patch("assemblyzero.workflows.testing.runners.jest_runner.JestRunner._run_subprocess") as mock_sub:
            with open(os.path.join(temp_project_dir, "tsconfig.json"), "w") as f:
                f.write("{}")
                
            config = {"framework": TestFramework.VITEST}
            runner = JestRunner(config, project_root=temp_project_dir)
            
            # Fail typecheck
            mock_sub.side_effect = [
                ("TS Error 2322", 1)
            ]
            result = runner.run_tests()
            
            assert mock_sub.call_count == 1
            assert result["failed"] == 1
            assert "TS Error 2322" in result["raw_output"]
