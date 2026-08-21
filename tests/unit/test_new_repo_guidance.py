"""Guidance the new-repo path prints, and the caller template it deploys.

Two defects that shipped for months without failing anything, because neither
is about behaviour. One was operator-facing prose. The other was a duplicated
constant. Nothing executes prose and nothing compares duplicates, so nothing
caught either.

DEPLOY-THEN-REVOKE (#134)
-------------------------
The script told the operator to revoke the Cerberus App key after deploying it.
Revoking removes the PUBLIC half registered on the App, so GitHub can no longer
validate a JWT signed by that key -- and the REVIEWER_APP_PRIVATE_KEY secret
the run just deployed becomes dead bytes. No installation token, no approving
review, mergeable_state stuck at `blocked`, in the new repo and in every other
repo holding the same key.

Runbook 0927 was corrected and the script was not, so the two contradicted each
other, and the script is the copy the operator actually reads at 10pm.

CALLER-TEMPLATE DRIFT (#1193)
-----------------------------
deploy_auto_reviewer_workflow.py carried its own copy of the auto-reviewer
caller YAML. It went stale: pre-`workflow_call` format, no `with:` inputs,
`secrets: inherit` instead of the named secrets the reusable workflow declares
as required. Every repo it touched got a workflow that died at startup.

The copy is now gone -- it imports the constant from new_repo.py -- and this
asserts they cannot diverge again.
"""
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

NEW_REPO_SRC = (TOOLS / "new_repo.py").read_text(encoding="utf-8")
DEPLOY_SRC = (TOOLS / "deploy_auto_reviewer_workflow.py").read_text(encoding="utf-8")


class TestNoDeployThenRevoke:
    # Lines that TELL the operator to revoke. Prose explaining what revocation
    # does, or pointing at the rotation runbook, is fine and must stay -- the
    # rule is "never instruct a revoke right after a deploy", not "never say
    # the word".
    IMPERATIVE = re.compile(
        r"^\s*print\(.*(?:REMEMBER to revoke"
        r"|Revoke the key you just"
        r"|revoke the key in the app UI\""
        r"|,\s*revoke the key)",
        re.IGNORECASE | re.MULTILINE,
    )

    def test_new_repo_never_instructs_a_revoke(self):
        hits = self.IMPERATIVE.findall(NEW_REPO_SRC)
        assert not hits, f"deploy-then-revoke instruction present: {hits}"

    def test_the_keep_active_warning_is_actually_printed(self):
        # The inverse assertion. Deleting the bad advice without replacing it
        # would pass the test above and leave the operator with no guidance at
        # the exact moment they are looking at a Revoke button.
        assert "do NOT revoke" in NEW_REPO_SRC or "Do NOT revoke" in NEW_REPO_SRC
        assert "0939" in NEW_REPO_SRC, "must point at the rotation runbook"

    def test_advice_does_not_branch_on_which_pem_flow_ran(self):
        # The superseded #1536 split told the plaintext flow to revoke because
        # no on-disk credential survived. Wrong question: the key is deployed
        # either way, which is what makes revoking destructive.
        assert "belt-and-" not in NEW_REPO_SRC
        assert "no on-disk credential to retire" not in NEW_REPO_SRC


class TestCallerTemplateHasOneDefinition:
    def test_deploy_tool_imports_rather_than_redefines(self):
        assert "_CANONICAL_AUTO_REVIEWER_CALLER" in DEPLOY_SRC
        assert not re.search(r"^CALLER_WORKFLOW\s*=\s*[\"']", DEPLOY_SRC, re.MULTILINE), \
            "deploy tool redefines the caller instead of importing it (#1193)"

    def test_the_two_modules_agree_by_identity(self):
        new_repo = pytest.importorskip("new_repo")
        deploy = pytest.importorskip("deploy_auto_reviewer_workflow")
        assert deploy.CALLER_WORKFLOW is new_repo._CANONICAL_AUTO_REVIEWER_CALLER

    def test_the_canonical_caller_matches_the_reusable_workflow_contract(self):
        new_repo = pytest.importorskip("new_repo")
        caller = new_repo._CANONICAL_AUTO_REVIEWER_CALLER
        # The reusable workflow declares workflow_call with a required_checks
        # input and two REQUIRED secrets. `secrets: inherit` does not satisfy
        # a declared-secrets contract -- that mismatch is what produced
        # startup_failure in 0s on every PR.
        assert "workflows/auto-reviewer.yml@main" in caller
        assert "required_checks" in caller
        assert "REVIEWER_APP_ID" in caller
        assert "REVIEWER_APP_PRIVATE_KEY" in caller
        assert "secrets: inherit" not in caller

    def test_docstring_does_not_carry_a_third_copy(self):
        # The module docstring used to quote the YAML, and the quote went stale
        # alongside the code copy. A transcribed example is a copy nothing
        # tests and everyone trusts.
        head = DEPLOY_SRC.split('"""')[1] if '"""' in DEPLOY_SRC else ""
        assert "secrets: inherit" not in head
