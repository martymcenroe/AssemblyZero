# Extracted Test Plan

## Scenarios

### test_010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse LLD verdict | Auto | Sample LLD verdict markdown | VerdictRecord with correct fields | All fields populated, type='lld'

### test_020
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parse Issue verdict | Auto | Sample Issue verdict markdown | VerdictRecord with correct fields | All fields populated, type='issue'

### test_030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Extract blocking issues | Auto | Verdict with Tier 1/2/3 issues | List of BlockingIssue | Correct tier, category, description

### test_040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Content hash change detection | Auto | Same file, modified file | needs_update=False, True | Correct boolean return

### test_050
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Pattern normalization | Auto | Various descriptions | Normalized patterns | Consistent output for similar inputs

### test_060
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Category mapping | Auto | All categories | Correct template sections | Matches CATEGORY_TO_SECTION

### test_070
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Template section parsing | Auto | 0102 template | Dict of 11 sections | All sections extracted

### test_080
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Recommendation generation | Auto | Pattern stats with high counts | Recommendations list | Type, section, content populated

### test_090
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Atomic write with backup | Auto | Template path + content | .bak created, content written | Both files exist, content correct

### test_100
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Multi-repo discovery | Auto | Mock project-registry.json | List of repo paths | All repos found

### test_110
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Missing repo handling | Auto | Registry with nonexistent repo | Warning logged, continue | No crash, other repos scanned

### test_120
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Database migration | Auto | Old schema DB | Updated schema | New columns exist

### test_130
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Dry-run mode (default) | Auto | Preview only, no file changes | Template unchanged

### test_140
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Stats output formatting | Auto | Database with verdicts | Formatted statistics | Readable output

### test_150
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Auto | Registry found at /path/to/dir/project-registry.json | Correct path resolution

### test_160
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Auto | Registry found at explicit path

### test_170
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Auto | DB with existing verdicts | All verdicts re-parsed | Hash check bypassed

### test_180
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Verbose logging (-v) | Auto | Filename logged at DEBUG | Parsing error includes filename

### test_190
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Path traversal prevention (verdict) | Auto | Verdict path with ../../../etc/passwd | Path rejected, error logged | is_relative_to() check fails

### test_195
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Path traversal prevention (template) | Auto | Path rejected, error logged | validate_template_path() fails

### test_200
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Parser version upgrade re-parse | Auto | DB with old parser_version | Verdict re-parsed despite unchanged content | needs_update returns True when parser_version outdated

### test_210
- Type: unit
- Requirement: 
- Mock needed: False
- Description: Symlink loop handling | Auto | Directory with recursive symlink | Scanner completes without hanging | No infinite recursion, warning logged

### test_220
- Type: unit
- Requirement: 
- Mock needed: True
- Description: Database directory creation | Auto | .agentos/ does not exist | Directory created, DB initialized | No error, DB file exists

