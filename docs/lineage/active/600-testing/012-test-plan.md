# Extracted Test Plan

## Scenarios

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Happy path valid AST Analysis (REQ-1) | `import os; os.path.join()` | No errors | No errors emitted

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Missing import verified (REQ-2) | `json.dumps({})` | `SentinelError` | Error for 'json'

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Feedback to stderr (REQ-3) | `json.dumps({})` | Error in stderr | Exact string in stderr

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Mechanical validation fail (REQ-4) | Bad file | `sys.exit(1)` | Exit code 1

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Local scope resilience (REQ-5) | `def foo(a): b = a; return b` | No errors | Args/locals recognized

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Comprehensions (REQ-5) | `[x for x in y]` | No errors | 'x' isolated

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Walrus Operators (REQ-5) | `if (n := len(a)) > 1: print(n)` | No errors | 'n' recognized

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Star imports banned (REQ-6) | `from typing import *` | "Star imports are not allowed" | REQ-6 failure

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Global/Nonlocal tracking (REQ-5) | `global x; x = 1` | No errors | No false positives

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: TYPE_CHECKING support (REQ-7) | `if TYPE_CHECKING: from x import y` | No errors | 'y' registered

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Ignore comments (REQ-8) | `var # sentinel: disable-line` | No errors | Symbol ignored

