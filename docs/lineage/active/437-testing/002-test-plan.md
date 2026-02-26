# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_consolidate_detects_file_exceeding_threshold` | File with mocked size 52_428_801 | Backup `.1` exists, active file < threshold

### test_t020
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_consolidate_skips_file_below_threshold` | File with mocked size 10_485_760 | No backup files, original file unchanged

### test_t030
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_consolidate_exact_threshold_boundary` | File with mocked size 52_428_800 | Consistent with `>` or `>=` semantics

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_rotation_creates_numbered_backup` | Large file, no existing backups | `history.log.1` exists with original content

### test_t050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_rotation_increments_existing_backups` | Large file + `.1` + `.2` | `.1`→`.2`→`.3` cascade, new `.1` = old active

### test_t060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_rotation_preserves_content_integrity` | 500 numbered lines, trigger rotation | All 500 lines present across all files

### test_t070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_rotation_creates_fresh_active_file` | Large file triggers rotation | Active file exists, size < 1024 bytes

### test_t080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_consolidate_large_file_with_multiple_sources` | 3 source files + large history | All source content preserved

### test_t090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_consolidate_handles_concurrent_rotation_gracefully` | Large file + existing backups, rotate twice | No crash, files exist

### test_t100
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `test_consolidate_large_file_read_only_filesystem` | Read-only directory | `PermissionError` or `OSError` raised, original intact

### test_t110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_consolidate_large_file_disk_full_simulation` | `shutil.move` raises `OSError` | `OSError` raised, original file intact

### test_t120
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_no_actual_large_files_created` | Post-rotation tmp_path walk | All files < 1MB on disk

### test_t130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `test_operations_confined_to_tmp_path` | Parent dir snapshot before/after | No new files outside tmp_path

