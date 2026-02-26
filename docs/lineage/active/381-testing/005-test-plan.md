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
- Description: `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.spec.ts` pattern | `TestFramework.PLAYWRIGHT`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with `.test.ts` and jest | `TestFramework.JEST`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with no indicators | `TestFramework.PYTEST`

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_framework_from_lld()` | `test_framework_detector.py` | LLD with "Test Framework: Playwright" | `TestFramework.PLAYWRIGHT`

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_framework_from_project()` | `test_framework_detector.py` | Dir with `playwright.config.ts` | `TestFramework.PLAYWRIGHT`

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `detect_framework_from_project()` | `test_framework_detector.py` | Dir with jest in package.json | `TestFramework.JEST`

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `resolve_framework()` | `test_framework_detector.py` | LLD=Playwright, project=Jest | `TestFramework.PLAYWRIGHT`

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | Config with npx playwright, .spec.ts, SCENARIO

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_framework_config()` | `test_runner_registry.py` | `TestFramework.PYTEST` | Config with pytest, test_*.py, LINE

### test_t100
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_runner()` | `test_runner_registry.py` | `TestFramework.PYTEST` | `PytestRunner` instance

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `get_runner()` | `test_runner_registry.py` | `TestFramework.PLAYWRIGHT` | `PlaywrightRunner` instance

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Valid Python test | `[]`

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PytestRunner.validate_test_file()` | `test_pytest_runner.py` | Python file, no imports | Error list

### test_t140
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | Valid .spec.ts | `[]`

### test_t150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PlaywrightRunner.validate_test_file()` | `test_playwright_runner.py` | .spec.ts missing import | Error list

### test_t160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `JestRunner.validate_test_file()` | `test_jest_runner.py` | Valid .test.ts | `[]`

### test_t170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `JestRunner.validate_test_file()` | `test_jest_runner.py` | .test.ts no describe/it | Error list

### test_t180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PlaywrightRunner.parse_results()` | `test_playwright_runner.py` | Fixture JSON | Correct counts

### test_t190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `JestRunner.parse_results()` | `test_jest_runner.py` | Fixture JSON | Correct counts

### test_t200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PytestRunner.parse_results()` | `test_pytest_runner.py` | pytest stdout | Correct counts + coverage

### test_t210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `compute_scenario_coverage()` | `test_check_coverage_node.py` | 35/38, 38/38, 0/0 | 92.1%, 100%, 0.0%

### test_t220
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `PlaywrightRunner.run_tests()` | `test_playwright_runner.py` | Mocked subprocess | npx playwright test --reporter=json

### test_t230
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `JestRunner.run_tests()` | `test_jest_runner.py` | Mocked subprocess | npx jest --json

### test_t240
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `PytestRunner.run_tests()` | `test_pytest_runner.py` | Mocked subprocess | pytest --tb=short -q

### test_t250
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `PlaywrightRunner.__init__()` | `test_playwright_runner.py` | npx missing | `EnvironmentError`

### test_t260
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_tests()` node | `test_run_tests_node.py` | Timeout result | Graceful handling

### test_t270
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | Playwright config | `.spec.ts` path

### test_t280
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `determine_test_file_path()` | `test_scaffold_tests_multifw.py` | No framework config | Not `.spec.ts`

### test_t290
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `run_tests()` node | `test_run_tests_node.py` | Playwright state | runner.validate called

### test_t300
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_coverage()` node | `test_check_coverage_node.py` | 38/38 SCENARIO | green=True

### test_t310
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_coverage()` node | `test_check_coverage_node.py` | 97% LINE | green=True

### test_t320
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `check_coverage()` node | `test_check_coverage_node.py` | NONE type | green=True

### test_t330
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Full chain | `test_run_tests_node.py` + `test_check_coverage_node.py` | Mocked full flow | All nodes succeed

### test_t340
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Full chain | `test_check_coverage_node.py` | Standard pytest state | Backward compat

