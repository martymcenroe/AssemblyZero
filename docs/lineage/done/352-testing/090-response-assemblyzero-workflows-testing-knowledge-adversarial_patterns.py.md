

```python
"""Knowledge base of adversarial testing patterns.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""


def get_adversarial_patterns() -> list[str]:
    """Return curated list of adversarial testing pattern descriptions.

    Categories:
    - Boundary: off-by-one, empty input, max-size input, type limits
    - Injection: special characters, unicode, null bytes, path traversal
    - Concurrency: race conditions, shared state mutation
    - State: invalid state transitions, partial initialization
    - Contract: violating documented preconditions, postcondition verification
    - Resource: memory exhaustion, file handle leaks, timeout scenarios
    """
    return [
        (
            "Boundary: Test with empty strings, None values, zero-length "
            "collections, maximum integer values, extremely long strings "
            "(>1MB), negative numbers where positive expected, off-by-one "
            "on sequence indices, single-element and two-element collections"
        ),
        (
            "Injection: Test with special characters (quotes, backslashes, "
            "null bytes \\x00), Unicode edge cases (RTL marks, zero-width "
            "joiners, emoji, combining characters), path traversal sequences "
            "(../), SQL-like strings ('; DROP TABLE), HTML/XML tags"
        ),
        (
            "Concurrency: Test shared state mutation under concurrent access, "
            "race conditions in file I/O operations, thread-safety of global "
            "or module-level state, async/await cancellation mid-operation"
        ),
        (
            "State: Test invalid state transitions, partially initialized "
            "objects, state after error recovery, double-initialization, "
            "use-after-close patterns, accessing attributes before setup"
        ),
        (
            "Contract: Test violations of documented preconditions, verify "
            "documented postconditions hold after every call, test invariants "
            "under mutation, check return type contracts match docstrings, "
            "verify error messages match documented error specifications"
        ),
        (
            "Resource: Test behavior under memory pressure with large inputs, "
            "verify file handles are closed after operations, test timeout "
            "behavior for long-running operations, verify cleanup on exception "
            "in context managers and finally blocks"
        ),
    ]
```
