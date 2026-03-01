# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_initial_state()` | `parse_args(["--reporter", "local"])` | `JanitorState` with `scope=["links","worktrees","harvest","todo"]`, `reporter_type="local"`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_links()` | mock repo with broken `./docs/old-guide.md` link | `ProbeResult(status="findings")` with `fixable=True` finding

### test_t030
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_links()` | mock README with `https://example.com` only | `ProbeResult(status="ok")`, no findings

### test_t040
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_links()` | mock repo with valid `./docs/guide.md` link | `ProbeResult(status="ok")`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_worktrees()` | mocked 15-day-old merged worktree | `ProbeResult(status="findings")` with `fixable=True`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_worktrees()` | mocked 1-day-old active worktree | `ProbeResult(status="ok")`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_todo()` | mocked TODO 45 days old | `ProbeResult(status="findings")` with `fixable=False`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `probe_todo()` | mocked TODO added today | `ProbeResult(status="ok")`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `probe_harvest()` | no harvest script in repo | `ProbeResult(status="findings")` with `harvest_missing` info

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_probe_safe()` | probe raises `RuntimeError` | `ProbeResult(status="error", error_message="RuntimeError: ...")`

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `fix_broken_links()` | finding + real file, `dry_run=False` | File updated, `FixAction(applied=True)`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `fix_broken_links()` | finding + real file, `dry_run=True` | File unchanged, `FixAction(applied=False)`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `fix_stale_worktrees()` | worktree finding, `dry_run=False` | `subprocess.run` called with `git worktree remove`

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `generate_commit_message()` | `"broken_link"`, `3` | `"chore: fix 3 broken markdown link(s) (ref #94)"`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LocalFileReporter.create_report()` | title, body, severity | File created in `janitor-reports/`

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LocalFileReporter.update_report()` | existing path, new body | File overwritten

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LocalFileReporter.find_existing_report()` | report from today exists | Returns file path

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `build_report_body()` | mixed findings + actions | Markdown with all sections

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_sweep()` | `{"all_findings": []}` | `"__end__"`

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_sweep()` | fixable finding + `auto_fix=True` | `"n1_fixer"`

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_sweep()` | unfixable only | `"n2_reporter"`

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_fix()` | `{"unfixable_findings": []}` | `"__end__"`

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `route_after_fix()` | non-empty unfixable | `"n2_reporter"`

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_args()` | `[]` | defaults: scope=all, auto_fix=True, etc.

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_args()` | all flags | all values parsed correctly

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_args()` | `["--scope", "invalid"]` | `SystemExit`

### test_t270
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `main()` | mocked clean run | return `0`

### test_t280
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `main()` | mocked unfixable findings | return `1`

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `graph.invoke()` | integration with `LocalFileReporter` | report created, correct exit code

### test_t300
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `main()` | mocked probes returning mixed | sweeper→fixer→reporter chain executes

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `graph.invoke()` | `dry_run=True` with fixable | `FixAction(applied=False)`, file unchanged

### test_t320
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `graph.invoke()` | broken link finding + real file | file updated, commit mocked

### test_t330
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `graph.invoke()` | mixed findings | fix applied + report for unfixable

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `["--silent"]` + clean | no stdout

### test_t350
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | not in git repo | return `2`

### test_t360
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `GitHubReporter.__init__()` | `GITHUB_TOKEN` set, gh auth fails | reporter initializes successfully

### test_t370
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `GitHubReporter.find_existing_report()` | existing issue found | returns URL, `update_report` would be called

### test_t380
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `LocalFileReporter.create_report()` | standard inputs | file in `janitor-reports/`

