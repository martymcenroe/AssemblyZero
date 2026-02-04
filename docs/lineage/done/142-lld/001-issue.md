# Issue #142: fix: --select flag not implemented in unified requirements workflow

## Summary

The `--select` flag in `run_requirements_workflow.py` is defined but not implemented. It bypasses validation but provides no actual selection UI.

## Current Behavior

```bash
poetry run python tools/run_requirements_workflow.py --type lld --select --gates none
```

Output:
```
Type:     lld
Issue:    #None    <-- No selection happened
...
ERROR: No issue number provided
```

## Expected Behavior

`--select` should:
1. For `--type issue`: Show interactive picker of files in `ideas/active/`
2. For `--type lld`: Show interactive picker of open GitHub issues

## Code Location

`tools/run_requirements_workflow.py`:
- Lines 89-93: Flag defined
- Lines 318-324: Flag checked but not acted upon
- **Missing**: Actual selection implementation

## Workaround

Specify input directly:
```bash
--issue 42        # for LLD workflow
--brief path.md   # for issue workflow
```

## Impact

- Runbook (0907) documents `--select` as working
- CLI help shows `--select` as an option
- Users expect it to work

## Related

The old standalone workflows (`run_issue_workflow.py`, `run_lld_workflow.py`) may have had working `--select` implementations that weren't ported.