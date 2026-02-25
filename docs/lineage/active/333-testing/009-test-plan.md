# Extracted Test Plan

## Scenarios

### test_id
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Tests Function | File | Input Summary | Expected Output

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_config()` | `test_metrics_config.py` | Explicit path to fixture | Valid config with 3 repos

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `load_config()` | `test_metrics_config.py` | Env var path | Config from env var

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_config()` | `test_metrics_config.py` | `{"repos": []}` | `ValueError`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `validate_config()` | `test_metrics_config.py` | `{"repos": ["invalid"]}` | `ValueError`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_repo_string()` | `test_metrics_config.py` | `"martymcenroe/AssemblyZero"` | Correct `TrackedRepoConfig`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_filter_issues_only()` | `test_github_metrics_client.py` | 5 items (3 issues, 2 PRs) | 3 items

### test_t070
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `fetch_repo_contents()` | `test_github_metrics_client.py` | Mock 404 | `[]`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `fetch_issues()` | `test_github_metrics_client.py` | Mock 429 then 200 | Success after retry

### test_t090
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `collect_issue_metrics()` | `test_metrics_aggregator.py` | 3 mock issues | Correct counts, avg=18.0

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `collect_issue_metrics()` | `test_metrics_aggregator.py` | Empty list | All zeros, None avg

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Issues with workflow labels | Label counts match

### test_t120
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `collect_workflow_metrics()` | `test_metrics_aggregator.py` | Mock content listing | lld_count=4, report_count=2

### test_t130
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Mock verdict files | approvals=3, blocks=2, rate=0.6

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `collect_gemini_metrics()` | `test_metrics_aggregator.py` | Empty contents | All zeros, None rate

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `aggregate()` | `test_metrics_aggregator.py` | 2 PerRepoMetrics | Correct summed totals

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `aggregate()` | `test_metrics_aggregator.py` | 1 success, 1 failed | Failed listed, totals from success

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_collect_cross_project_metrics.py` | `dry_run=True` | Exit code 0, config printed

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_collect_cross_project_metrics.py` | 1 success, 1 exception | Exit code 1

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_collect_cross_project_metrics.py` | All exceptions | Exit code 2

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics, tmp_path | Date-stamped file

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Valid metrics | `latest.json` exists

### test_t220
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `format_summary_table()` | `test_collect_cross_project_metrics.py` | Table with repos + TOTALS

### test_t230
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `get_rate_limit_remaining()` | `test_github_metrics_client.py` | Mock remaining=50 | `{"remaining": 50}`

### test_t240
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_get_cache_key()` | `test_github_metrics_client.py` | Same params twice | Equal keys

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_is_cache_valid()` | `test_github_metrics_client.py` | Fresh cache entry | `True`

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_is_cache_valid()` | `test_github_metrics_client.py` | Expired entry | `False`

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `parse_args()` | `test_collect_cross_project_metrics.py` | All flags | Correct namespace

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_collect_cross_project_metrics.py` | `verbose=True` | DEBUG logs emitted

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `main()` | `test_collect_cross_project_metrics.py` | `lookback_days=7` | Config overridden

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `write_metrics_output()` | `test_collect_cross_project_metrics.py` | Custom output_path | File at custom path

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_resolve_token()` | `test_github_metrics_client.py` | GITHUB_TOKEN env set | Token from env

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `_resolve_token()` | `test_github_metrics_client.py` | GH_TOKEN fallback | Token from GH_TOKEN

### test_t330
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `fetch_issues()` | `test_github_metrics_client.py` | Mock authenticated client | Issues returned

### test_t340
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `fetch_issues()` | `test_github_metrics_client.py` | Mock 404 on private repo | `UnknownObjectException`

