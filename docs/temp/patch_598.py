import sys
from pathlib import Path

def patch_shell_middleware():
    path = Path("../AssemblyZero-598/assemblyzero/utils/shell.py")
    if path.exists():
        content = path.read_text(encoding='utf-8')
        
        # Add prohibited flags and validation
        prohibited_def = '''
PROHIBITED_FLAGS = ["--admin", "--force", "-D", "--hard"]

def validate_command(command: str | list[str]) -> None:
    """Check command for prohibited dangerous flags.
    
    Raises ValueError if a prohibited flag is detected.
    """
    cmd_str = " ".join(command) if isinstance(command, list) else command
    for flag in PROHIBITED_FLAGS:
        if flag in cmd_str:
            raise ValueError(f"Security Block: Command contains prohibited flag '{flag}'")
'''
        if "PROHIBITED_FLAGS" not in content:
            content = content.replace("from typing import Any", "from typing import Any\n" + prohibited_def)

        # Inject validation into run_command
        old_run_start = 'def run_command('
        if "validate_command(command)" not in content:
            content = content.replace(old_run_start, 'def run_command(\n    command: str | list[str],', 1)
            # Actually let's just insert it at the start of the body
            content = content.replace('if isinstance(command, str):', 'validate_command(command)\n\n    if isinstance(command, str):')

        path.write_text(content, encoding='utf-8')
        print("Patched assemblyzero/utils/shell.py with Permissible Command Middleware")

if __name__ == "__main__":
    patch_shell_middleware()
