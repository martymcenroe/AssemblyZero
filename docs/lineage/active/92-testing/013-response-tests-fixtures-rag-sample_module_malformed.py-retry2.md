

```python
"""Malformed module for testing parse error handling.

Issue #92: Codebase Retrieval System (RAG Injection)

This file intentionally contains a syntax error.
"""

def broken(
    # Missing closing paren, colon, and body
```

Wait, that's the exact content from the LLD which causes a syntax error by design - but the validation is rejecting it. Let me provide a file that is intentionally malformed but passes any basic file-read check while still triggering a `SyntaxError` when parsed by `ast.parse()`:

```python
"""Malformed module for testing parse error handling.

Issue #92: Codebase Retrieval System (RAG Injection)

This file intentionally contains a syntax error.
"""

def broken(x, y
    return x + y
```
