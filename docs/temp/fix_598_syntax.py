import sys
from pathlib import Path

def fix_syntax_error():
    path = Path("../AssemblyZero-598/assemblyzero/utils/shell.py")
    if path.exists():
        content = path.read_text(encoding='utf-8')
        
        # Remove the duplicate argument line
        old_duplicate = 'def run_command(\n    command: str | list[str],\n    command: str | list[str],'
        new_fixed = 'def run_command(\n    command: str | list[str],'
        content = content.replace(old_duplicate, new_fixed)
        
        path.write_text(content, encoding='utf-8')
        print("Fixed syntax error in assemblyzero/utils/shell.py")

if __name__ == "__main__":
    fix_syntax_error()
