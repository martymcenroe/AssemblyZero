"""Context estimation and file summarization for code generation.

Manages prompt context size and produces compact file summaries.
"""

import ast

# Issue #324: Large file thresholds for diff-based generation
LARGE_FILE_LINE_THRESHOLD = 500  # Lines
LARGE_FILE_BYTE_THRESHOLD = 15000  # Bytes (~15KB)


def estimate_context_tokens(lld_content: str, completed_files: list[tuple[str, str]]) -> int:
    """Estimate token count for context.

    Uses simple heuristic: ~4 chars per token.
    """
    total_chars = len(lld_content)
    for filepath, content in completed_files:
        total_chars += len(filepath) + len(content) + 50  # 50 for formatting

    return total_chars // 4


def summarize_file_for_context(content: str) -> str:
    """Extract imports and signatures from a Python file for compact context.

    Issue #373: Instead of embedding full file bodies (~20KB+) in accumulated
    context, extract only what subsequent files need: imports, class/function
    signatures, and their docstrings. Reduces context from ~20KB to ~2-3KB.

    Args:
        content: Full Python file content.

    Returns:
        Compact summary with imports and signatures.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # If we can't parse it, return first 50 lines as fallback
        lines = content.split("\n")
        return "\n".join(lines[:50]) + "\n# ... (truncated, syntax error in original)\n"

    parts: list[str] = []

    # Extract module docstring
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        docstring = tree.body[0].value.value
        parts.append(f'"""{docstring}"""')

    # Extract all imports
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Get the source lines for this import
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            source_lines = content.split("\n")[start:end]
            parts.append("\n".join(source_lines))

    # Extract class and function signatures
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            parts.append(_summarize_class(node, content))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(_summarize_function(node, content))

    # Extract module-level constants/type aliases (simple assignments)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            start = node.lineno - 1
            end = node.end_lineno if node.end_lineno else start + 1
            source_lines = content.split("\n")[start:end]
            line_text = "\n".join(source_lines)
            # Only include short assignments (constants, not large data structures)
            if len(line_text) < 200:
                parts.append(line_text)

    return "\n\n".join(parts)


def _summarize_function(node: ast.FunctionDef | ast.AsyncFunctionDef, source: str) -> str:
    """Extract function signature and docstring."""
    # Get the def line from source
    start = node.lineno - 1
    source_lines = source.split("\n")

    # Find the end of the signature (the line with the colon)
    sig_lines = []
    for i in range(start, min(start + 10, len(source_lines))):
        sig_lines.append(source_lines[i])
        if source_lines[i].rstrip().endswith(":"):
            break

    sig = "\n".join(sig_lines)

    # Get docstring if present
    docstring = ast.get_docstring(node)
    if docstring:
        # Use only first 3 lines of docstring
        doc_lines = docstring.split("\n")[:3]
        indent = "    "
        sig += f'\n{indent}"""{chr(10).join(doc_lines)}"""'

    sig += "\n    ..."
    return sig


def _summarize_class(node: ast.ClassDef, source: str) -> str:
    """Extract class signature, docstring, and method signatures."""
    source_lines = source.split("\n")
    start = node.lineno - 1

    # Get class def line
    class_lines = []
    for i in range(start, min(start + 5, len(source_lines))):
        class_lines.append(source_lines[i])
        if source_lines[i].rstrip().endswith(":"):
            break

    parts = ["\n".join(class_lines)]

    # Get class docstring
    docstring = ast.get_docstring(node)
    if docstring:
        doc_lines = docstring.split("\n")[:3]
        parts.append(f'    """{chr(10).join(doc_lines)}"""')

    # Get method signatures
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_sig = _summarize_function(item, source)
            parts.append(method_sig)

    return "\n\n".join(parts)


def is_large_file(content: str) -> bool:
    """Check if file content exceeds size thresholds.

    Issue #324: Large files (500+ lines OR 15KB+) should use diff mode
    instead of full file regeneration.

    Args:
        content: The file content to check.

    Returns:
        True if file exceeds either threshold.
    """
    if not content:
        return False

    # Check line count (500+ lines = large)
    line_count = len(content.split("\n"))
    if line_count > LARGE_FILE_LINE_THRESHOLD:
        return True

    # Check byte size (15KB+ = large)
    byte_count = len(content.encode("utf-8"))
    if byte_count > LARGE_FILE_BYTE_THRESHOLD:
        return True

    return False


def select_generation_strategy(change_type: str, existing_content: str | None) -> str:
    """Select code generation strategy based on change type and file size.

    Issue #324: Use diff mode for large file modifications.

    Args:
        change_type: "Add", "Modify", or "Delete".
        existing_content: Current file content (None for new files).

    Returns:
        "standard" or "diff".
    """
    # Add and Delete always use standard mode
    if change_type.lower() in ("add", "delete"):
        return "standard"

    # Modify: check file size
    if existing_content and is_large_file(existing_content):
        return "diff"

    return "standard"
