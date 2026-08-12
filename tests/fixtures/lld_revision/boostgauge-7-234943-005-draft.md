# Issue #7 - Feature: configuration file and CLI arguments

## 1. Context & Goal
* **Issue:** #7
* **Objective:** Implement a configuration system for thresholds, polling intervals, and window behavior, managed via a config file and CLI arguments with specific precedence and write-back rules.
* **Status:** Draft
* **Related Issues:** N/A

### Open Questions
- [ ] None

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/boostgauge/config.py` | Add | Implement Config class, config loading, merging, and saving logic |
| `src/boostgauge/app.py` | Add | Integrate CLI argument parsing and Config initialization |
| `tests/unit/test_config.py` | Add | Add unit tests for configuration loading, precedence, and persistence |

### 2.1.1 Path Validation (Mechanical - Auto-Checked)

Mechanical validation automatically checks paths.

### 2.2 Dependencies

```toml

# No new dependencies required.
```

### 2.3 Data Structures

```python
class ConfigState(TypedDict):
    polling_interval_seconds: int
    theme: str
    size: int
    opacity: float
    always_on_top: bool
    position: dict[str, int]
    thresholds: dict[str, dict[str, int]]
    telltale_windows: dict[str, int]
    show_driver_label: bool
    show_digital_readout: bool
    show_session_count: bool

class SessionConfig:
    file_path: Path
    file_state_at_launch: ConfigState
    current_state: ConfigState
    cli_overrides: set[str]
    hand_changed_keys: set[str]
```

### 2.4 Function Signatures

```python
def load_config(config_path: Path, reset: bool) -> SessionConfig:
    """Loads configuration, handling auto-create and reset logic."""
    ...

def apply_cli_overrides(config: SessionConfig, overrides: dict[str, Any]) -> None:
    """Applies CLI arguments in memory, marking them as overrides."""
    ...

def record_hand_change(config: SessionConfig, key: str, value: Any) -> None:
    """Records a user-driven hand change during the session (e.g. position, size)."""
    ...

def reload_thresholds(config: SessionConfig) -> None:
    """Re-reads thresholds from file mid-session without modifying the file."""
    ...

def save_config_on_exit(config: SessionConfig) -> None:
    """Writes back only hand-changed keys to the config file, preserving external direct edits."""
    ...
```

### 2.5 Logic Flow (Pseudocode)

```
1. Parse CLI arguments
2. Determine config file path (default or --config)
3. IF --reset-config:
     Write defaults to file
4. Read file (IF missing, write defaults to file and read)
5. Apply CLI overrides to session in memory
6. Run session
7. ON external file change:
     Read threshold values into memory
8. ON drag/resize:
     Record hand change for 'position' or 'size'
9. ON exit:
     IF no hand changes:
       Exit without writing
     ELSE:
       Read current file from disk
       Apply only hand-changed keys to the read data
       Write file to disk
```

### 2.6 Technical Approach

* **Module:** `src/boostgauge/config.py`
* **Pattern:** State composition (File State + Overrides + Hand Changes)
* **Key Decisions:** The session config must track which keys were overridden by CLI (to prevent write-back) and which keys were hand-changed during the session (to trigger write-back). The exit write must read the file immediately before writing to ensure any direct edits made during the session are not blindly overwritten, applying only the `hand_changed_keys` as a patch.

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Config File Format | JSON, TOML, YAML | JSON | Simple, built-in standard library, matches issue description. |
| Persistence Tracking | Boolean flags, dirty sets | Set of hand-changed keys | Precisely isolates only the keys that the app has permission to write back on exit. |

**Architectural Constraints:**
- Must use purely standard library for configuration (JSON) to avoid dependency bloat.
- Must read file mid-session to support threshold hot-reloading without independent process walks.

## 3. Requirements

1. First run with no config file creates one with defaults.
2. Launch order is reset, then read, then CLI overrides in memory; CLI value overrides govern the session and the app never writes them to the file.
3. With no CLI overrides, the window opens at the file's position and size.
4. Launched with `--reset-config` and no `--size`, the window opens at the default position and default size; launched with `--reset-config --size N`, it opens at the default position and size N while the file holds the default size.
5. Threshold values edited directly in the config file take effect without restart, and reading them never modifies the file.
6. The exit write touches only hand-changed keys: a direct file edit made while the app ran survives an exit that also writes a new position or size.
7. With a direct file edit during the session, the edited key holds the edited value after quit, unless the user also hand-changed that same key, in which case the hand-made value wins.
8. A session with no hand-made changes performs no exit write; if the session also found an existing config file at launch, was launched without `--reset-config`, and the file was not edited directly, the file is byte-identical after quit.
9. Position, no reset, not moved, no direct edits: `position` unchanged.
10. Position, no reset, moved, no direct edits: `position` holds the new position.
11. Position, reset, not moved, no direct edits: `position` holds the default.
12. Position, reset, moved, no direct edits: `position` holds the new position.
13. Size, no reset, no `--size`, not resized, no direct edits: `size` unchanged.
14. Size, no reset, no `--size`, resized, no direct edits: `size` holds the new size.
15. Size, no reset, `--size` given, not resized, no direct edits: `size` unchanged; the CLI value is not written.
16. Size, no reset, `--size` given, resized, no direct edits: `size` holds the new size.
17. Size, reset, no `--size`, not resized, no direct edits: `size` holds the default.
18. Size, reset, no `--size`, resized, no direct edits: `size` holds the new size.
19. Size, reset, `--size` given, not resized, no direct edits: `size` holds the default; the CLI value is not written.
20. Size, reset, `--size` given, resized, no direct edits: `size` holds the new size.
21. Invalid config values produce clear error messages.
22. `--config PATH` selects which config file is in play for the session and writes nothing by itself; the three write moments apply to the selected file.

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Overwrite file fully on exit | Simple to implement | Destroys manual user edits during session | **Rejected** |
| Patch file on exit based on hand-changes | Preserves user edits, meets all criteria | Requires tracking state and re-reading before write | **Selected** |

**Rationale:** The strict persistence criteria necessitate a patch-based write model that respects external user modifications to the JSON file.

## 5. Data & Fixtures

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Local config file (`config.json` in project root) |
| Format | JSON |
| Size | < 1 KB |
| Refresh | On launch, on file modification (thresholds) |
| Copyright/License | N/A |

### 5.2 Data Pipeline

```
Local File ──read──► SessionConfig ──CLI overrides──► Memory
SessionConfig ──hand changes──► Patch ──write──► Local File
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Mock Config JSON | Hardcoded in tests | Represents default and edge-case states |

### 5.4 Deployment Pipeline

No external deployment required. Operates entirely locally.

## 6. Diagram
N/A

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Malicious config file injection | Validate JSON schema on read | Addressed |
| Symlink attacks on config path | Ensure path resolution does not follow insecure links | Addressed |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Config corruption on exit write | Write to temporary file, then atomic rename | Addressed |
| Invalid manual config edits | Fallback to defaults or fail with clear error message, leaving file intact | Addressed |

**Fail Mode:** Fail Closed - If the config file is corrupted and unparseable, print a clear error and exit rather than implicitly deleting the user's file.

**Recovery Strategy:** Users can delete the config file or use `--reset-config` to restore the system to a clean state.

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| Config Load | < 50ms | Use standard `json` library, lazy load where possible |
| Exit Write | < 50ms | Only write if hand-changed keys exist |

**Bottlenecks:** Minimal. Config read/write is rare.

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| N/A | N/A | N/A | $0 |

**Cost Controls:**
- [ ] N/A

**Worst-Case Scenario:** Config polling could thrash disk if interval is abused. Use file-system watchers or mtime checks instead of continuous reads.

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Config stores only UI preferences |
| Third-Party Licenses | No | N/A |
| Terms of Service | No | N/A |
| Data Retention | No | N/A |
| Export Controls | No | N/A |

**Data Classification:** Public / Internal (Local only)

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

**Testing Philosophy:** Strive for 100% automated test coverage. Manual tests are a last resort for scenarios that genuinely cannot be automated.

### 10.0 Test Plan (TDD - Complete Before Implementation)

**Coverage Target:** ≥95% for all new code

| Test ID | Test Description | Expected Behavior | Status |
|---------|------------------|-------------------|--------|
| T010 | First run no config | Creates file with size 300 | RED |
| T020 | Launch order reset and read | File rewritten, CLI args apply | RED |
| T030 | Read window defaults | Opens at size 300 without overrides | RED |
| T040 | Reset with size N | File size 300, session size 400 | RED |
| T050 | Threshold reload | File unchanged, memory updated | RED |
| T060 | Exit write tracking | Only moved position is written | RED |
| T070 | Direct edit conflict | Hand change wins over direct edit | RED |
| T080 | Byte identical quit | No changes leaves file byte-identical | RED |
| T090 | Position rules (no reset) | Position persists only if moved | RED |
| T100 | Position rules (reset) | Position holds default unless moved | RED |
| T110 | Size rules (no reset) | Size persists only if resized, CLI ignored | RED |
| T120 | Size rules (reset) | Size holds default unless resized | RED |
| T130 | Invalid config | Outputs error message | RED |
| T140 | Custom path flag | Path resolves and behavior applies | RED |

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | First run with no config (REQ-1) | Auto | No config file present | File created with defaults | File exists, contains `"size": 300` |
| 020 | Launch order reset/read (REQ-2) | Auto | `--reset-config --size 400` | Session size is 400, file holds 300 | Memory `size` is `400`, JSON `size` is `300` |
| 030 | Open at file position/size (REQ-3) | Auto | File holds `size` 500, no CLI args | App memory gets size 500 | Memory `size` is `500` |
| 040 | Reset with CLI size (REQ-4) | Auto | `--reset-config --size 400` | File defaults to 300, app memory 400 | Memory `size` is `400`, JSON `size` is `300` |
| 050 | Threshold reload without write (REQ-5) | Auto | Write new threshold to file mid-session | Memory updates, file mtime unchanged | Memory `process_count.red` is `600`, file mtime identical |
| 060 | Exit write patch (REQ-6) | Auto | Direct edit `theme` to `light`, move window to `x: 50` | File retains `light`, gets `x: 50` | JSON `theme` is `"light"`, JSON `position.x` is `50` |
| 070 | Hand change wins (REQ-7) | Auto | Direct edit `size` to 400, hand resize to 500 | File gets size 500 | JSON `size` is `500` |
| 080 | Byte-identical exit (REQ-8) | Auto | Launch without changes, exit | File checksum is identical | MD5 before == MD5 after |
| 090 | Pos: No reset, not moved (REQ-9) | Auto | File `x: 200`, no action | File `x: 200` | JSON `position.x` is `200` |
| 100 | Pos: No reset, moved (REQ-10) | Auto | File `x: 200`, window moved to 50 | File `x: 50` | JSON `position.x` is `50` |
| 110 | Pos: Reset, not moved (REQ-11) | Auto | `--reset-config`, no move | File `x: 100` (default) | JSON `position.x` is `100` |
| 120 | Pos: Reset, moved (REQ-12) | Auto | `--reset-config`, move to 50 | File `x: 50` | JSON `position.x` is `50` |
| 130 | Size: No reset, no CLI, not resized (REQ-13) | Auto | File `size` 200, no action | File `size` 200 | JSON `size` is `200` |
| 140 | Size: No reset, no CLI, resized (REQ-14) | Auto | File `size` 200, resize 500 | File `size` 500 | JSON `size` is `500` |
| 150 | Size: No reset, CLI, not resized (REQ-15) | Auto | File `size` 200, `--size 400` | File `size` 200 | JSON `size` is `200` |
| 160 | Size: No reset, CLI, resized (REQ-16) | Auto | File `size` 200, `--size 400`, resize 500 | File `size` 500 | JSON `size` is `500` |
| 170 | Size: Reset, no CLI, not resized (REQ-17) | Auto | `--reset-config`, no action | File `size` 300 (default) | JSON `size` is `300` |
| 180 | Size: Reset, no CLI, resized (REQ-18) | Auto | `--reset-config`, resize 500 | File `size` 500 | JSON `size` is `500` |
| 190 | Size: Reset, CLI, not resized (REQ-19) | Auto | `--reset-config --size 400`, no action | File `size` 300 (default) | JSON `size` is `300` |
| 200 | Size: Reset, CLI, resized (REQ-20) | Auto | `--reset-config --size 400`, resize 500 | File `size` 500 | JSON `size` is `500` |
| 210 | Invalid config values (REQ-21) | Auto | Corrupt JSON file | App exits with error | Exit code `1`, stdout contains `"Error"` |
| 220 | Config path selection (REQ-22) | Auto | `--config custom.json` | Write and read from `custom.json` | `custom.json` exists, default missing |

### 10.2 Test Commands

```bash

# Run all automated tests
poetry run pytest tests/unit/test_config.py -v

# Run only fast/mocked tests (exclude live)
poetry run pytest tests/unit/test_config.py -v -m "not live"

# Run live integration tests
poetry run pytest tests/unit/test_config.py -v -m live
```

### 10.3 Manual Tests (Only If Unavoidable)

N/A - All scenarios automated.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| JSON parsing failure | High | Low | Catch `json.JSONDecodeError` and print human-readable message, exiting gracefully without overwriting (`load_config`). |
| Concurrent file writes | Low | Low | Exit write uses patch logic; thresholds reloaded stat checks limit mid-session trashing (`save_config_on_exit`, `reload_thresholds`). |
| Missing permissions | High | Low | Validate directory existence and permissions before writing (`load_config`, `save_config_on_exit`). |

## 12. Definition of Done

### Code
- [ ] Implementation complete and linted
- [ ] Code comments reference this LLD

### Tests
- [ ] All test scenarios pass
- [ ] Test coverage meets threshold

### Documentation
- [ ] LLD updated with any deviations
- [ ] Implementation Report (0103) completed
- [ ] Test Report (0113) completed if applicable

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

### 12.1 Traceability (Mechanical - Auto-Checked)

Mechanical validation automatically checks cross-references.

---

## Appendix: Review Log

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| None | (auto) | PENDING | Initial draft |

**Final Status:** PENDING