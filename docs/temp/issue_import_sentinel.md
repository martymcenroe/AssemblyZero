## Objective
Enhance mechanical validation to catch "Lingering Symbols" (missing imports or undefined variables) before execution.

## Requirements
1. **AST Analysis:** Use Python `ast` module to scan for `Name` nodes.
2. **Verification:** Ensure every non-builtin name has a corresponding `Import` or local definition.
3. **Feedback:** Provide line-specific errors: "Symbol 'emit' used on line 1078 but not imported."

## Acceptance Criteria
- [ ] Catches `NameError` bugs during validation phase (saving tokens).
- [ ] Integrated into `validate_mechanical.py`.

## Related
- #587 (Mechanical Gate)