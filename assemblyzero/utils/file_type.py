"""File type detection utility for workflow file generation.

Issue #447: Maps file extensions to language tags and content descriptors
so the TDD workflow can correctly prompt Claude for non-Python files.
"""

from pathlib import PurePosixPath
from typing import TypedDict


class FileTypeInfo(TypedDict):
    language_tag: str
    content_descriptor: str
    is_code: bool


FILE_TYPE_REGISTRY: dict[str, FileTypeInfo] = {
    ".py": {"language_tag": "python", "content_descriptor": "Python code", "is_code": True},
    ".md": {"language_tag": "markdown", "content_descriptor": "Markdown content", "is_code": False},
    ".yaml": {"language_tag": "yaml", "content_descriptor": "YAML configuration", "is_code": False},
    ".yml": {"language_tag": "yaml", "content_descriptor": "YAML configuration", "is_code": False},
    ".json": {"language_tag": "json", "content_descriptor": "JSON data", "is_code": False},
    ".toml": {"language_tag": "toml", "content_descriptor": "TOML configuration", "is_code": False},
    ".sh": {"language_tag": "bash", "content_descriptor": "shell script", "is_code": True},
    ".js": {"language_tag": "javascript", "content_descriptor": "JavaScript code", "is_code": True},
    ".ts": {"language_tag": "typescript", "content_descriptor": "TypeScript code", "is_code": True},
    ".txt": {"language_tag": "", "content_descriptor": "text content", "is_code": False},
}

_DEFAULT: FileTypeInfo = {
    "language_tag": "",
    "content_descriptor": "file content",
    "is_code": False,
}


def get_file_type_info(file_path: str) -> FileTypeInfo:
    """Return FileTypeInfo for a given file path based on its extension.

    Falls back to a safe default for unknown extensions.
    """
    ext = PurePosixPath(file_path).suffix.lower()
    return FILE_TYPE_REGISTRY.get(ext, _DEFAULT)


def get_language_tag(file_path: str) -> str:
    """Return the fenced code block language tag for a file path.

    E.g., 'python' for .py, 'markdown' for .md, '' for unknown.
    """
    return get_file_type_info(file_path)["language_tag"]


def get_content_descriptor(file_path: str) -> str:
    """Return a human-readable description of the file content type.

    E.g., 'Python code' for .py, 'Markdown content' for .md.
    """
    return get_file_type_info(file_path)["content_descriptor"]
