# Extracted Test Plan

## Scenarios

### test_010
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Happy path: 3 LLDs processed in parallel | Auto | 3 mock LLDs, --parallel 3 | All complete, progress report shows 3/3 | Exit code 0, all DBs cleaned up

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Dry run lists without executing | Auto | 5 pending items, --dry-run | List of 5 items printed | No subprocess spawned, no DBs created

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Path traversal rejected | Auto | Issue number "../etc/passwd" | ValueError raised | Clear error message, no file access

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Credential exhaustion pauses workers | Auto | 5 items, 2 credentials, --parallel 5 | Workers pause, resume on release | Log shows "[COORDINATOR] Credential pool exhausted"

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: HTTP 429 triggers backoff | Auto | AGENTOS_SIMULATE_429=true | Key marked rate-limited | Backoff applied, different key used or wait

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Single workflow failure isolated | Auto | 1 invalid spec among 3 | 2 succeed, 1 fails | Failed item in report, others complete

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Graceful shutdown on SIGINT | Auto | SIGINT during execution | Workers checkpoint and exit | All checkpoint DBs written within 5s

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Output prefix prevents interleaving | Auto | 3 parallel workflows | All lines prefixed correctly | No partial line mixing

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Performance benchmark | Auto-Live | 6 items, sequential vs --parallel 3 | Parallel < 50% sequential time | Timing comparison logged

### test_100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Max parallelism enforced | Auto | Capped to 10 | Warning logged, runs with 10

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Default parallelism applied | Auto | Uses 3 | Config shows max_parallelism=3

