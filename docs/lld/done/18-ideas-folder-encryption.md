# LLD: Ideas Folder with git-crypt Encryption (Issue #18)

**Author:** Claude Opus 4.5
**Date:** 2026-01-15
**Status:** Approved (Security Review Passed 2026-01-15)

---

## 1. Problem Statement

Pre-issue ideation has no home. Currently, capturing a half-formed thought requires either:
- Opening a GitHub issue (too formal, clutters backlog)
- Keeping notes externally (doesn't travel with repo, different tool)
- Not capturing it (ideas lost)

For public repos, the problem is compounded: even if you had an `ideas/` folder, its contents would be visible to the world. This kills the willingness to capture rough drafts, speculative patent ideas, or exploratory concepts.

## 2. Goals

1. **Establish `ideas/` folder convention** - Standard location in every repo for pre-issue ideation
2. **Encrypt ideas in git** - Contents encrypted in remote, plaintext locally for authorized users
3. **Sync across machines** - Keys work on all user's machines (not just one)
4. **Defense in depth** - Encrypt even in private repos (private can become public, collaborators come and go)
5. **Integrate with repo generator** - New repos get `ideas/` setup automatically
6. **New audit tier** - `--ultimate` flag for expensive/rare audits including gitignore review

## 3. Non-Goals

- Encrypting other folders (this LLD focuses on `ideas/` pattern)
- Supporting collaborative encrypted editing (single-user or trusted-team only)
- Key rotation automation (manual process for now)
- Encrypting commit messages or branch names

---

## 4. Design

### 4.1 Tool Selection: git-crypt

**Decision:** Use git-crypt for transparent encryption.

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **git-crypt** | Transparent (auto encrypt/decrypt), battle-tested since 2012, GPG or symmetric key, files appear as binary blobs to unauthorized | Requires installation, GPG can be complex | **Selected** |
| age | Modern, simple, single binary | Manual encrypt/decrypt, no git integration | Rejected |
| GPG manual | Universal, no new tools | Terrible UX, manual every time | Rejected |
| SOPS | Great for YAML/JSON secrets | Overkill for markdown notes, complex setup | Rejected |
| .gitignore | Simplest | Ideas don't travel with repo, no backup | Rejected |

**Rationale:** git-crypt provides the best UX - you edit files normally, git handles encryption transparently. The 12-year track record and wide adoption make it the safe choice for "don't want my junk stolen" security requirements.

### 4.2 Folder Structure

```
repo/
├── ideas/                      # Encrypted folder
│   ├── README.md               # Placeholder (encrypted, explains folder purpose)
│   ├── 2026-01-hiking-sensor.md
│   ├── 2026-01-robotics-arm.md
│   └── someday/                # Subfolder for "maybe never" ideas
│       └── quantum-thing.md
├── .gitattributes              # Root gitattributes (encryption rules)
└── ...
```

**Naming convention:** `YYYY-MM-slug.md` for dated ideas, freeform for evergreen concepts.

### 4.3 Encryption Configuration

**File: `.gitattributes` (repo root)**

```gitattributes
# Encrypt ideas folder
ideas/** filter=git-crypt diff=git-crypt
ideas/**/* filter=git-crypt diff=git-crypt
```

**Why at repo root?** git-crypt requires `.gitattributes` patterns to be in the repo root or a parent directory. Patterns in `ideas/.gitattributes` alone won't work.

### 4.4 Key Management Strategy

**Primary approach: Symmetric key with secure storage**

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Machine A      │     │  1Password/      │     │  Machine B      │
│                 │     │  Secure Storage  │     │                 │
│  git-crypt      │────▶│                  │◀────│  git-crypt      │
│  unlock         │     │  symmetric.key   │     │  unlock         │
│                 │     │  (base64)        │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

**Setup flow (one-time per repo):**

```bash
# 1. Initialize git-crypt in repo
cd /path/to/repo
git-crypt init

# 2. Export symmetric key
git-crypt export-key ../repo-ideas.key

# 3. Store key in secure location (1Password, Bitwarden, etc.)
# Key is ~128 bytes binary, can be base64 encoded for storage

# 4. Delete local key file after storing securely
rm ../repo-ideas.key
```

**Unlock flow (per machine):**

```bash
# 1. Export key directly from password manager to file
#    (Most password managers have "export to file" or "copy to clipboard")

# Option A: Save from password manager UI directly to temp file
#    1Password: Right-click attachment → Save As → /tmp/repo.key

# Option B: Clipboard method (avoids shell history)
#    macOS:   pbpaste | base64 -d > /tmp/repo.key
#    Linux:   xclip -selection clipboard -o | base64 -d > /tmp/repo.key
#    Windows: powershell -c "Get-Clipboard" | base64 -d > /tmp/repo.key

# Option C: Interactive input (paste, then Ctrl+D)
cat > /tmp/repo.key
# [paste binary key content, then press Ctrl+D]

# 2. Unlock
git-crypt unlock /tmp/repo.key

# 3. Delete temp key file immediately
rm /tmp/repo.key    # Unix
# del /tmp/repo.key # Windows CMD
```

**SECURITY WARNING:** Never use `echo "KEY_HERE" | base64 -d > file` - this leaks the key to shell history (`~/.bash_history`, `~/.zsh_history`).

**Alternative: GPG keys**

For users with existing GPG infrastructure:

```bash
# Add GPG user to repo
git-crypt add-gpg-user USER_ID

# Unlock happens automatically if GPG key is in keyring
git-crypt unlock
```

**Recommendation:** Start with symmetric key (simpler), document GPG as alternative for power users.

### 4.5 Key Storage Options

| Storage | Pros | Cons | Recommendation |
|---------|------|------|----------------|
| 1Password | Cross-platform, secure, searchable | Paid service | **Primary** |
| Bitwarden | Open source, self-hostable | Slightly less polished | Good alternative |
| macOS Keychain | Built-in, secure | Mac only | Platform-specific |
| Windows Credential Manager | Built-in | Windows only, less ergonomic | Platform-specific |
| ~/.ssh/ folder | Already secured, familiar | Mixes keys, no UI | Acceptable |
| USB drive | Airgapped | Easy to lose, no sync | Not recommended |

**Key naming convention:** `{repo-name}-ideas-key` (e.g., `assemblyzero-ideas-key`)

### 4.6 Repo Generator Integration

**File: `AssemblyZero/tools/assemblyzero-generate.py`**

Add new function:

```python
def setup_ideas_folder(project_path: Path, encrypt: bool = True) -> None:
    """
    Create ideas folder with optional encryption setup.

    Args:
        project_path: Root of the project
        encrypt: Whether to set up git-crypt encryption
    """
    ideas_path = project_path / "ideas"
    ideas_path.mkdir(exist_ok=True)

    # Create README placeholder
    readme = ideas_path / "README.md"
    readme.write_text("""# Ideas

This folder contains pre-issue ideation - half-formed thoughts,
patent concepts, exploratory ideas not ready for the issue tracker.

**Encrypted:** This folder's contents are encrypted in git.
Only authorized users with the key can read these files.

## Naming Convention

- `YYYY-MM-slug.md` - Dated ideas
- `someday/` - "Maybe never" concepts
- Freeform names for evergreen ideas
""")

    # Create someday subfolder
    (ideas_path / "someday").mkdir(exist_ok=True)
    (ideas_path / "someday" / ".gitkeep").touch()

    if encrypt:
        # Add encryption rules to root .gitattributes
        gitattributes = project_path / ".gitattributes"
        rules = """
# Encrypt ideas folder (git-crypt)
ideas/** filter=git-crypt diff=git-crypt
ideas/**/* filter=git-crypt diff=git-crypt
"""
        if gitattributes.exists():
            content = gitattributes.read_text()
            if "ideas/**" not in content:
                gitattributes.write_text(content + "\n" + rules)
        else:
            gitattributes.write_text(rules.strip() + "\n")

        print(f"Created ideas/ folder with encryption rules")
        print(f"Run 'git-crypt init' to enable encryption")
    else:
        print(f"Created ideas/ folder (no encryption)")
```

**CLI flag:**

```bash
# With encryption (default)
poetry run python assemblyzero-generate.py --project myproject --ideas

# Without encryption (not recommended for public repos)
poetry run python assemblyzero-generate.py --project myproject --ideas --no-encrypt
```

### 4.7 New Audit: Gitignore Review (0833)

**Purpose:** Scan all `.gitignore` entries and recommend encryption vs ignore.

**Audit number:** 0833 (next available in Core Development)

**Trigger:** `--ultimate` flag only (expensive, rare)

**Logic:**

```python
def audit_gitignore_encryption():
    """
    Review all gitignored paths and recommend encrypt vs ignore.

    Categories:
    - ENCRYPT: Sensitive data that should travel with repo
    - IGNORE: Build artifacts, caches, truly local files
    - REVIEW: Needs human decision
    """
    recommendations = []

    # Patterns that suggest encryption
    encrypt_signals = [
        'ideas', 'notes', 'drafts', 'private', 'secrets',
        'credentials', 'keys', '.env', 'config.local'
    ]

    # Patterns that are clearly ignore-worthy
    ignore_signals = [
        'node_modules', '__pycache__', '.pytest_cache',
        'dist', 'build', '.next', 'coverage', '*.pyc',
        '.DS_Store', 'Thumbs.db', '*.log', 'tmp', 'temp'
    ]

    for pattern in parse_gitignore():
        if matches_any(pattern, encrypt_signals):
            recommendations.append({
                'pattern': pattern,
                'recommendation': 'ENCRYPT',
                'reason': 'Contains sensitive data that may need to travel with repo'
            })
        elif matches_any(pattern, ignore_signals):
            recommendations.append({
                'pattern': pattern,
                'recommendation': 'IGNORE',
                'reason': 'Build artifact or cache, correctly gitignored'
            })
        else:
            recommendations.append({
                'pattern': pattern,
                'recommendation': 'REVIEW',
                'reason': 'Unknown pattern, needs human decision'
            })

    return recommendations
```

**Output format:**

```markdown
## Gitignore Encryption Audit (0833)

| Pattern | Current | Recommendation | Reason |
|---------|---------|----------------|--------|
| `ideas/` | .gitignore | **ENCRYPT** | Sensitive data that should travel with repo |
| `node_modules/` | .gitignore | IGNORE | Build artifact, correctly gitignored |
| `local-notes/` | .gitignore | REVIEW | Unknown pattern, needs human decision |

### Recommended Actions
1. Move `ideas/` from .gitignore to git-crypt encryption
2. No action needed for `node_modules/`
3. Review `local-notes/` - encrypt if contains ideas, ignore if truly local
```

### 4.8 --ultimate Audit Tier

**Concept:** Some audits are expensive (time, API calls, computation) or rarely needed. These should only run when explicitly requested.

**Implementation:**

```python
# In audit runner
AUDIT_TIERS = {
    'standard': [801, 802, 803, ...],  # Normal audits
    'full': [801, 802, ..., 825, ...],  # All regular audits
    'ultimate': [833, ...]              # Expensive/rare audits
}

def run_audits(tier: str = 'standard', specific: list[int] = None):
    """
    Run audits based on tier or specific numbers.

    Args:
        tier: 'standard', 'full', or 'ultimate'
        specific: List of specific audit numbers to run
    """
    if specific:
        audits_to_run = specific
    elif tier == 'ultimate':
        audits_to_run = AUDIT_TIERS['full'] + AUDIT_TIERS['ultimate']
    else:
        audits_to_run = AUDIT_TIERS[tier]

    for audit_num in audits_to_run:
        run_audit(audit_num)
```

**CLI:**

```bash
# Standard audits
/audit

# Full audits (all standard)
/audit --full

# Ultimate (includes expensive audits like 0833)
/audit --ultimate

# Specific audit
/audit 0833
```

**Candidates for --ultimate tier:**
- 0833: Gitignore encryption review (new)
- Future: Full dependency license audit with API calls
- Future: Historical git analysis for leaked secrets

---

## 5. Security Considerations

| Concern | Mitigation | Status |
|---------|------------|--------|
| Key in plaintext on disk | Key only in memory during session, deleted after use | Addressed |
| Key leaked to shell history | Use clipboard/interactive methods, never `echo KEY` | Addressed |
| Key shared insecurely | Document secure storage options (1Password, etc.) | Addressed |
| Accidental commit before encryption | git-crypt init must happen before first ideas commit | Documentation |
| Key loss = data loss | Multiple key copies in secure storage, document backup | Documentation |
| Weak encryption | git-crypt uses AES-256, industry standard | Addressed |
| Encryption metadata leaked | File sizes visible, but contents encrypted | Acceptable |
| Clone before unlock = binary blobs | Expected behavior, clearly documented | Addressed |

**Fail Mode:** Fail Closed - If git-crypt is not unlocked, files appear as binary blobs. No plaintext leakage.

---

## 6. Performance Considerations

| Metric | Impact | Notes |
|--------|--------|-------|
| Clone time | Minimal | Encrypted files same size as plaintext |
| Checkout time | +50-100ms | Decryption on checkout |
| Commit time | +50-100ms | Encryption on commit |
| Disk space | Identical | Encrypted = same size as plaintext |

**Bottlenecks:** None expected. git-crypt is designed for transparent operation.

---

## 7. Migration Plan

### 7.1 Phase 1: Infrastructure (This Issue)

1. Add `setup_ideas_folder()` to assemblyzero-generate.py
2. Create 0833-audit-gitignore-encryption.md
3. Add `--ultimate` tier to audit system
4. Document git-crypt setup in AssemblyZero CLAUDE.md
5. Create template `.gitattributes` for ideas encryption

### 7.2 Phase 2: AssemblyZero Dogfood

1. Set up `ideas/` folder in AssemblyZero itself
2. Initialize git-crypt
3. Store key securely
4. Verify workflow on multiple machines

### 7.3 Phase 3: Roll Out to Projects

1. Run generator with `--ideas` flag on existing projects
2. Initialize git-crypt per project
3. Store keys with consistent naming

---

## 8. Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tools/assemblyzero-generate.py` | Modify | Add `setup_ideas_folder()` function |
| `docs/audits/0833-audit-gitignore-encryption.md` | New | Ultimate-tier audit for gitignore review |
| `docs/audits/0800-audit-index.md` | Modify | Add 0833, document --ultimate tier |
| `.claude/commands/audit.md` | Modify | Add --ultimate flag |
| `CLAUDE.md` | Modify | Add git-crypt setup instructions |
| `ideas/README.md` | New | Template README for ideas folder |
| `.gitattributes` | Modify | Add ideas/** encryption rules |

---

## 9. Verification & Testing

### 9.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | Fresh repo setup | Manual | New repo, run generator | ideas/ created with .gitattributes | Folder exists, rules in .gitattributes |
| 020 | git-crypt init | Manual | Run git-crypt init | Encryption initialized | .git/git-crypt/ exists |
| 030 | Write idea file | Manual | Create ideas/test.md | File saved normally | File readable locally |
| 040 | Push to remote | Manual | git push | Files encrypted in remote | GitHub shows binary blob |
| 050 | Clone without key | Manual | Clone on new machine | ideas/ contains binary blobs | Files not readable |
| 060 | Unlock with key | Manual | git-crypt unlock key.file | Files decrypted | ideas/test.md readable |
| 070 | Audit gitignore | Auto | Run 0833 on test repo | Recommendations generated | ENCRYPT/IGNORE/REVIEW categorized |
| 080 | --ultimate flag | Auto | Run /audit --ultimate | 0833 included | Audit 0833 executes |

### 9.2 Manual Test Justification

Most scenarios require git operations, file system changes, and multi-machine verification that cannot be unit tested. The audit components (070, 080) can be automated.

---

## 10. Definition of Done

### Code
- [ ] `setup_ideas_folder()` implemented in generator
- [ ] 0833 audit implemented
- [ ] --ultimate tier added to audit system

### Documentation
- [ ] git-crypt setup instructions in CLAUDE.md
- [ ] 0833-audit-gitignore-encryption.md created
- [ ] 0800-audit-index.md updated

### Testing
- [ ] Manual test scenarios 010-060 passed
- [ ] Automated tests for 0833 audit logic

### Deployment
- [ ] ideas/ folder created in AssemblyZero
- [ ] git-crypt initialized in AssemblyZero
- [ ] Key stored securely

---

## 11. Open Questions

- [ ] **Should we support per-idea encryption keys?** (Current design: one key per repo)
- [ ] **Should the audit recommend moving existing .gitignored folders to encryption?** (Current: yes, as recommendation only)
- [ ] **What's the recovery path if key is lost?** (Current: ideas are irrecoverable - document this clearly)

---

## Appendix: Quick Reference

### First-Time Setup (Per Repo)

```bash
# 1. Generate ideas folder
poetry run python assemblyzero-generate.py --project myproject --ideas

# 2. Initialize git-crypt
cd /path/to/myproject
git-crypt init

# 3. Export and store key
git-crypt export-key ../myproject-ideas.key
# Store in 1Password as "myproject-ideas-key"
# Then delete: rm ../myproject-ideas.key

# 4. Commit the setup
git add .gitattributes ideas/
git commit -m "feat: add encrypted ideas folder"
git push
```

### New Machine Setup

```bash
# 1. Clone repo
git clone https://github.com/user/myproject.git

# 2. Get key from secure storage, save to temp file
# (ideas/ will show as binary blobs until unlocked)

# 3. Unlock
git-crypt unlock /path/to/key
rm /path/to/key

# 4. Done - ideas/ now readable
```

### Windows Installation

```bash
# Via Chocolatey
choco install git-crypt

# Or via scoop
scoop install git-crypt

# Verify
git-crypt --version
```
