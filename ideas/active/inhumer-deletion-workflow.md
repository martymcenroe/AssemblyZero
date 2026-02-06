# Maintenance Workflow: The Inhumer (Safe Deletion)

**Status:** Brief
**Priority:** Medium (prevents zombie code accumulation)
**Created:** 2026-02-02
**Persona:** Lord Downey (Head of the Assassins' Guild)
**Inspiration:** Terry Pratchett's Discworld - *Men at Arms*, *Pyramids*

---

## Philosophy

> *"We prefer the word 'inhumed'. 'Deleted' implies a lack of style."*

The Assassins' Guild of Ankh-Morpork are not thugs. They are the most well-educated, refined, and *professional* gentlemen in the city. They refer to killing as "**Inhumation**." It is neat, it is contractual, and most importantly, they pride themselves on **tidiness**.

When you delete a tool, you don't just `rm` it (that's for thugs). You want to:

1. **Isolate the Target:** Ensure nothing else depends on it (no witnesses)
2. **Remove the Entourage:** Delete the regression tests that guarded it
3. **Clean the Scene:** Remove imports and references so the build doesn't break
4. **Escape:** Run the test suite to prove you were never there

---

## Problem Statement

**The "Zombie Code" Failure Mode:**

We have a robust "Software Factory" for creating code, but no safe process for destroying it. As we iterate, we leave behind:

- **Zombie Code** — Tools we stopped using but were afraid to delete
- **Ghost Tests** — Tests that guard features which no longer exist
- **Haunted Imports** — References to deleted modules that break the build

**Specific failure patterns:**

| Pattern | Symptom | Cost |
|---------|---------|------|
| **Orphaned Tests** | Delete `tools/old_script.py`, but `tests/test_old_script.py` remains | ImportError or useless passing tests |
| **Dependency Hell** | Delete a utility, but 5 files import it | Immediate build breakage |
| **Fear of Deletion** | Leave old files "just in case" | Codebase rot, confusion, maintenance burden |

---

## Proposed Solution: The Inhumer

A precision agent that performs **Targeted Inhumation** — complete removal of a target file along with all evidence of its existence.

**Core Philosophy:** "No witnesses, no survivors." When a target file is marked for death, its tests and references must die with it.

---

## Architecture

### State Definition (`assemblyzero/workflows/inhumer/state.py`)

```python
from typing import TypedDict, List, Optional

class InhumerState(TypedDict):
    # Contract
    target_path: str
    dry_run: bool

    # Intelligence (from N0)
    target_exists: bool
    related_tests: List[str]          # Tests that import/exercise target
    referencing_files: List[str]      # Source files that import target

    # Risk Assessment
    witness_count: int                # len(referencing_files)
    collateral_damage: List[str]      # Files that will be modified/deleted

    # Execution
    inhumation_status: str            # PENDING, AUTHORIZED, STAGED, COMMITTED, ROLLED_BACK
    authorization_received: bool

    # Verification
    test_exit_code: Optional[int]
    test_output: str

    # Audit Trail
    git_operations: List[str]         # Commands executed
    commit_sha: Optional[str]         # SHA of inhumation commit (only after success)
```

### State Graph (`assemblyzero/workflows/inhumer/graph.py`)

```
N0_Contract_Review (The Scout)
    │
    ├── Target doesn't exist → END (Nothing to inhume)
    │
    ▼
N1_Authorization_Gate (The Client)
    │
    ├── User declines → END (Contract cancelled)
    │
    ▼
N2_Execution (The Hit)
    │
    ▼
N3_Getaway (The Verification)
    │
    ├── Tests pass → END (Clean getaway)
    │
    └── Tests fail → N4_Rollback (Abort mission)
                         │
                         ▼
                     END (Rolled back, witnesses detected)
```

### Node Implementations

#### N0: Contract Review (The Scout)

```python
def contract_review(state: InhumerState) -> dict:
    """
    Reconnaissance phase. Identify the target and all connections.

    The Scout reports:
    - Does the target exist?
    - What tests guard this target?
    - What files reference this target?
    """
    target = Path(state["target_path"])

    # Does target exist?
    if not target.exists():
        return {"target_exists": False, "inhumation_status": "CANCELLED"}

    # Find the bodyguards (tests)
    related_tests = find_related_tests(target)

    # Find the witnesses (importing files)
    referencing_files = find_references(target)

    return {
        "target_exists": True,
        "related_tests": related_tests,
        "referencing_files": referencing_files,
        "witness_count": len(referencing_files),
        "collateral_damage": related_tests + referencing_files,
        "inhumation_status": "PENDING",
    }
```

#### N1: Authorization Gate (The Client)

```python
def authorization_gate(state: InhumerState) -> dict:
    """
    Present the contract to the client for authorization.

    The Assassins' Guild is professional. We don't act without a contract.
    """
    print("=" * 70)
    print("              THE ASSASSINS' GUILD - CONTRACT REVIEW")
    print("           'Nil Mortifi Sine Lucre' (No killing without profit)")
    print("=" * 70)
    print(f"\nTARGET: {state['target_path']}")
    print(f"\nBODYGUARDS (tests to remove): {len(state['related_tests'])}")
    for test in state["related_tests"]:
        print(f"  - {test}")

    print(f"\nWITNESSES (files with references): {state['witness_count']}")
    for ref in state["referencing_files"]:
        print(f"  - {ref}")

    if state["witness_count"] > 0:
        print("\n⚠️  WARNING: References must be cleaned from witness files.")

    print("\n" + "=" * 70)

    if state.get("dry_run"):
        print("DRY RUN: Contract review only. No inhumation will occur.")
        return {"authorization_received": False, "inhumation_status": "DRY_RUN"}

    response = input("Proceed with inhumation? [y/N]: ").strip().lower()
    authorized = response == "y"

    return {
        "authorization_received": authorized,
        "inhumation_status": "AUTHORIZED" if authorized else "CANCELLED",
    }
```

#### N2: Execution (The Hit)

```python
def execution(state: InhumerState) -> dict:
    """
    Perform the inhumation. Clean. Professional. Complete.

    IMPORTANT: Stage changes but DO NOT COMMIT yet.
    Commit only happens in N3 after tests pass.
    This allows safe rollback via `git restore` if tests fail.

    1. Remove target file (staged)
    2. Remove test files (staged)
    3. Clean references from witness files (staged)
    """
    operations = []

    # Remove the target (stages deletion)
    git_rm(state["target_path"])
    operations.append(f"git rm {state['target_path']}")

    # Remove the bodyguards (stages deletions)
    for test in state["related_tests"]:
        git_rm(test)
        operations.append(f"git rm {test}")

    # Clean the scene (remove imports from witnesses)
    for witness in state["referencing_files"]:
        remove_import(witness, state["target_path"])
        git_add(witness)  # Stage the cleaned file
        operations.append(f"Cleaned reference in {witness}")

    return {
        "git_operations": operations,
        "inhumation_status": "STAGED",  # Not committed yet!
    }
```

#### N3: Getaway (The Verification)

```python
def getaway(state: InhumerState) -> dict:
    """
    Verify clean escape. Run tests to ensure no witnesses remain.

    A true professional leaves no trace.

    IMPORTANT: Only COMMIT if tests pass. Changes are staged but
    not committed until we verify success. This is the safe pattern.
    """
    result = subprocess.run(
        ["poetry", "run", "pytest", "-x", "-q"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        # Tests pass - NOW we commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", f"chore: inhume {state['target_path']}"],
            capture_output=True,
            text=True,
        )
        commit_sha = get_current_commit_sha()

        print("\n✓ Inhumation complete. The system is stable.")
        print("  No witnesses. No evidence. Professional.")
        return {
            "test_exit_code": 0,
            "test_output": result.stdout,
            "commit_sha": commit_sha,
            "inhumation_status": "COMMITTED",
        }
    else:
        print("\n✗ Witnesses detected! Build is broken.")
        print("  Initiating rollback...")
        return {
            "test_exit_code": result.returncode,
            "test_output": result.stdout + result.stderr,
            "inhumation_status": "FAILED",
        }
```

#### N4: Rollback (Abort Mission)

```python
def rollback(state: InhumerState) -> dict:
    """
    Abort mission. Restore previous state.

    Even the best professionals sometimes need to retreat.

    NOTE: We use git restore, not git reset --hard.
    The Inhumer stages but doesn't commit until tests pass,
    so rollback is simply unstaging and restoring files.
    """
    # Unstage all changes
    subprocess.run(["git", "restore", "--staged", "."], check=True)

    # Restore deleted files
    subprocess.run(["git", "restore", "."], check=True)

    print("\n⟲ Inhumation aborted. All targets restored.")
    print("  The target survives... for now.")

    return {"inhumation_status": "ROLLED_BACK"}
```

---

## CLI Interface (`tools/run_inhumer_workflow.py`)

```bash
# Standard inhumation (with authorization prompt)
python tools/run_inhumer_workflow.py --target tools/deprecated_tool.py

# Dry run (reconnaissance only)
python tools/run_inhumer_workflow.py --target tools/deprecated_tool.py --dry-run

# Force mode (skip authorization - dangerous!)
python tools/run_inhumer_workflow.py --target tools/deprecated_tool.py --force

# Verbose mode (show all operations)
python tools/run_inhumer_workflow.py --target tools/deprecated_tool.py --verbose
```

---

## Output Example

```
======================================================================
              THE ASSASSINS' GUILD - CONTRACT REVIEW
           'Nil Mortifi Sine Lucre' (No killing without profit)
======================================================================

TARGET: tools/deprecated_tool.py

BODYGUARDS (tests to remove): 2
  - tests/test_deprecated_tool.py
  - tests/integration/test_deprecated_integration.py

WITNESSES (files with references): 3
  - tools/__init__.py
  - tools/main_workflow.py
  - assemblyzero/utils/helpers.py

⚠️  WARNING: References must be cleaned from witness files.

======================================================================
Proceed with inhumation? [y/N]: y

Executing contract...
  ✓ git rm tools/deprecated_tool.py
  ✓ git rm tests/test_deprecated_tool.py
  ✓ git rm tests/integration/test_deprecated_integration.py
  ✓ Cleaned reference in tools/__init__.py
  ✓ Cleaned reference in tools/main_workflow.py
  ✓ Cleaned reference in assemblyzero/utils/helpers.py

Verifying clean escape...
  Running pytest...

✓ Inhumation complete. The system is stable.
  No witnesses. No evidence. Professional.

======================================================================
                    CONTRACT FULFILLED
           "We do not 'delete'. We inhume with style."
======================================================================
```

---

## Success Criteria

- [ ] **Complete Removal:** Target file AND corresponding test files deleted
- [ ] **Reference Cleanup:** Import statements removed from all referencing files
- [ ] **Stability:** Workflow refuses to commit if `pytest` fails after deletion
- [ ] **Safety:** Requires explicit "Yes" from human before `git rm`
- [ ] **Rollback:** Automatic `git reset --hard` if tests fail post-deletion
- [ ] **Audit Trail:** Full log of all operations performed
- [ ] **Dry Run:** `--dry-run` flag shows what would be deleted without acting

---

## Integration Points

### With The Watch (Regression Guardian)

The Inhumer should notify The Watch when tests are intentionally deleted:

```python
# After successful inhumation
watch.acknowledge_removed_tests(state["related_tests"])
```

This prevents The Watch from creating issues for "missing" tests.

### With The Janitor

The Janitor (Lu-Tze) handles ongoing maintenance. The Inhumer handles targeted removal. They complement each other:

| Workflow | Scope | Trigger |
|----------|-------|---------|
| **The Janitor** | Broad hygiene (links, worktrees, drift) | Scheduled |
| **The Inhumer** | Targeted deletion of specific files | On-demand |

---

## Future Enhancements

- **Batch Inhumation:** Accept multiple targets in one contract
- **Pattern Matching:** `--target "tools/deprecated_*.py"` for bulk cleanup
- **Impact Analysis:** Show downstream effects before authorization
- **Undo Log:** Store inhumation history for potential resurrection
- **Integration with Issue Tracker:** Auto-close related issues when code is inhumed

---

## References

- [Workflow Personas](../wiki/Workflow-Personas.md) - Lord Downey entry
- [The Watch Brief](./city-watch-regression-guardian.md) - Test notification integration
- Issue #94: The Janitor (complementary maintenance workflow)
- *Men at Arms* by Terry Pratchett (Assassins' Guild introduction)
- *Pyramids* by Terry Pratchett (Guild operations detailed)

---

*"The Assassins' Guild: where every death is a work of art, and every deletion is an inhumation."*

**Nil Mortifi Sine Lucre** — No killing without profit
