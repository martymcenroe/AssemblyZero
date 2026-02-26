# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tests Function | File | Input | Expected Output

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_config()` | `test_metrics_config.py` | `tracked_repos_valid.json` fixture | Config with 3 repos, `cache_ttl_minutes=60`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_config()` | `test_metrics_config.py` | Non-existent path | `ConfigError` with path in message

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_config()` | `test_metrics_config.py` | `tracked_repos_malformed.json` fixture | `ConfigError("Failed to parse...")`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_config()` | `test_metrics_config.py` | `tracked_repos_empty.json` fixture | `ConfigError("repos list cannot be empty")`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_default_config_path()` | `test_metrics_config.py` | No args | Path ending in `.assemblyzero/tracked_repos.json`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `count_issues_in_period()` | `test_metrics_collector.py` | Mock repo: 4 created, 2 closed, 2 open | `(4, 2, 2)`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `detect_workflows_used()` | `test_metrics_collector.py` | Mock issues with `workflow:requirements` x2, `workflow:tdd` x2 | `{"requirements": 2, "tdd": 2}`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 2 active + 3 done dirs | `5`

### test_t090
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `count_gemini_verdicts()` | `test_metrics_collector.py` | Mock 4 verdict files: 3 APPROVE, 1 BLOCK | `(4, 3, 1)`

### test_t100
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `collect_repo_metrics()` | `test_metrics_collector.py` | Mock `UnknownObjectException` | `CollectionError` with repo name

### test_t110
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `count_lineage_artifacts()` | `test_metrics_collector.py` | Mock 404 on both dirs | `0`

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `aggregate_metrics()` | `test_metrics_aggregator.py` | 3 RepoMetrics | Sums: (87, 72, 25, 40, 35), rate=0.857

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `aggregate_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, empty per_repo

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `aggregate_metrics()` | `test_metrics_aggregator.py` | 1 RepoMetrics | Identity with single repo

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_approval_rate()` | `test_metrics_aggregator.py` | `(0, 0)` | `0.0`

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `save_cached_metrics()` + `load_cached_metrics()` | `test_metrics_cache.py` | Save then load within TTL | Identical metrics dict

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_cached_metrics()` | `test_metrics_cache.py` | TTL=0, sleep 0.1s | `None`

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_cached_metrics()` | `test_metrics_cache.py` | Corrupt JSON file | `None`

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate 1 | 2 remain, 1 is None

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `invalidate_cache()` | `test_metrics_cache.py` | 3 cached, invalidate all (`None`) | All 3 return None

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_json_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Valid JSON with all required keys

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_markdown_table()` | `test_metrics_formatters.py` | AggregatedMetrics fixture | Markdown with ` | Repo | ` table, repo names, `85.7%`

### test_t230
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_snapshot()` | `test_metrics_formatters.py` | AggregatedMetrics + tmp_path | File at `cross-project-{date}.json` with valid JSON

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_repo_metrics()` + `create_repo_metrics()` | `test_metrics_models.py` | `issues_created=-1` | `ValueError("issues_created must be non-negative, got -1")`

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_repo_name()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` valid, `"'; DROP TABLE--"` invalid | `True` / `False`

### test_t260
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `collect_repo_metrics()` | `test_metrics_collector.py` | Mock with token `"ghp_real_token"` | `Github("ghp_real_token")` called

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `collect_repo_metrics()` | `test_metrics_collector.py` | Empty token `""` | `Github()` called without args

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_metrics_cli.py` | 3 repos config, 1 unreachable | Exit code `1`

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_metrics_cli.py` | 3 repos config, all unreachable | Exit code `2`

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `count_issues_in_period()` | `test_metrics_collector.py` | Correct filtering: 1 created, 1 closed

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_workflows_used()` | `test_metrics_collector.py` | No workflow labels, LLD filenames present | Dict populated via heuristic

