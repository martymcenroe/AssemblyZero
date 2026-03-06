# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"ls -la"` | Returns `None`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"git push --force"` | Raises `SecurityException`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"gh pr merge --admin"` | Raises `SecurityException`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"git branch -D feat"` | Raises `SecurityException`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"git reset --hard HEAD"` | Raises `SecurityException`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"git push --force-with-lease"` | Returns `None`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `'git commit -m "Do not use --force"'` | Returns `None`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `['git', 'push', '--force']` | Raises `SecurityException`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_shell_command` | `"git push --force=true"` | Raises `SecurityException`

