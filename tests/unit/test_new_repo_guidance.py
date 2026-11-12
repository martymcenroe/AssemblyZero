"""Guidance the new-repo path prints.

A defect that shipped for months without failing anything, because it is not
about behaviour: operator-facing prose. Nothing executes prose, so nothing
caught it.

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

Since #4728 the script deploys no Cerberus key at all (nothing reads the
per-repo secrets), so it prints no post-deploy advice. The keep-active rule
still binds, because the pr-sentinel Worker signs with the App key, and its
home is the rotation runbook 0939, where the operator meets the Revoke button.

The caller-template drift (#1193) this file also guarded went with the caller
itself: the scaffolder writes no Auto Review caller, and the tool that deployed
one is removed (#4719).
"""
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

NEW_REPO_SRC = (TOOLS / "new_repo.py").read_text(encoding="utf-8")


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

    def test_the_keep_active_rule_survives_in_the_rotation_runbook(self):
        # The inverse assertion. Deleting the bad advice without keeping the
        # rule would pass the test above and leave the operator with no
        # guidance at the exact moment they are looking at a Revoke button.
        # Since #4728 that moment is a rotation, never a new repo.
        runbook = (TOOLS.parent / "docs" / "runbooks"
                   / "0939-cerberus-key-rotation.md").read_text(encoding="utf-8")
        assert "deploy → observe → revoke" in runbook
        assert "Do NOT revoke K1 yet." in runbook

    def test_the_scaffolder_deploys_no_key_so_gives_no_deploy_advice(self):
        assert "Cerberus secrets deployed and verified" not in NEW_REPO_SRC
        assert "cerberus_status" not in NEW_REPO_SRC

    def test_advice_does_not_branch_on_which_pem_flow_ran(self):
        # The superseded #1536 split told the plaintext flow to revoke because
        # no on-disk credential survived. Wrong question: the key is deployed
        # either way, which is what makes revoking destructive.
        assert "belt-and-" not in NEW_REPO_SRC
        assert "no on-disk credential to retire" not in NEW_REPO_SRC
