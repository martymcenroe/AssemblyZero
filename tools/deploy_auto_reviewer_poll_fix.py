#!/usr/bin/env python3
"""One-shot: land the auto-reviewer poll-loop fix (Closes #2627).

The change is to `.github/workflows/auto-reviewer.yml`, which needs `workflow`
scope. The fine-grained PAT behind `gh` and `git push` deliberately does not
carry it (ADR-0216 section 1), so the file goes in through the Contents API
using the in-process classic-PAT pattern.

WHAT IT FIXES

The "Wait for required checks" step treated every conclusion except `failure`
and `cancelled` as still-pending and polled 30 times at 20-second intervals.
GitHub sets `conclusion` only when a check has COMPLETED, so any non-empty
conclusion was a finished answer being re-asked for ten minutes. Measured
across the private fleet in August: 29 runs died that way, about 300 billed
minutes -- roughly 10% of the monthly Actions allowance -- spent waiting.

Two changes:

  1. Any non-empty conclusion is terminal. Inverted rather than extended: an
     allowlist is how `action_required` was missed, and the next unlisted
     conclusion would be found the same way, ten minutes at a time. No outcome
     changes -- every state that used to time out already ended in failure, it
     just gets there in ~20s instead of ~600s.

  2. The ceiling drops from 30 attempts to 15 (10 minutes to 5). With (1) in
     place the only remaining path to the ceiling is a check that was never
     created at all.

THE WORKFLOW IS EMBEDDED BASE64, and this file was generated from the tested
file rather than typed. The content carries backticks, quotes and non-ASCII
glyphs; every hand-transport through a quoted string is a chance to corrupt it
silently. The script verifies its own payload before sending.

Tested by tests/test_auto_reviewer_wait_loop.py, which extracts this exact step
from the YAML and executes it under bash against a stub `gh`. Reverting the
terminal test to the old allowlist fails 7 of those tests.

THE OPERATOR RUNS THIS, NOT AN AGENT (ADR-0216). A script an agent invokes is a
process the agent parents, and the decrypted PAT lives in that process's heap.

Required classic PAT scopes: repo (full), workflow.

Usage, in bash:

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/deploy_auto_reviewer_poll_fix.py

Idempotent: skips whatever already exists. One-shot -- safe to delete after the
PR merges, at which point the workflow file itself is the only copy that matters.
"""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "AssemblyZero"
ISSUE_NUMBER = 2627
BRANCH = f"{ISSUE_NUMBER}-auto-reviewer-poll-fix"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

TITLE = (
    "fix(auto-reviewer): treat any completed conclusion as terminal instead of "
    f"polling it for 10 minutes (Closes #{ISSUE_NUMBER})"
)

# Generated from the tested file. Do not hand-edit -- regenerate instead.
WORKFLOW_B64 = (
    "bmFtZTogYXV0by1yZXZpZXdlcgoKIyBSZXVzYWJsZSB3b3JrZmxvdzogYXV0by1hcHByb3ZlcyBQ"
    "UnMgd2hlbiBhbGwgcmVxdWlyZWQgY2hlY2tzIHBhc3MuCiMKIyBUaGlzIHVzZXMgYSBHaXRIdWIg"
    "QXBwIGlkZW50aXR5IChub3QgdGhlIHJlcG8gb3duZXIpIHRvIHN1Ym1pdCBhbgojIGFwcHJvdmlu"
    "ZyByZXZpZXcsIGJyZWFraW5nIHRoZSBzZWxmLWF1dGhvcml6YXRpb24gbG9vcCB3aGVyZSBhZ2Vu"
    "dHMKIyBjcmVhdGUgaXNzdWVzLCBjcmVhdGUgUFJzLCBhbmQgbWVyZ2UgdGhlaXIgb3duIFBScy4K"
    "IwojIFByZXJlcXVpc2l0ZXM6CiMgICAxLiBHaXRIdWIgQXBwICJBc3NlbWJseVplcm8gUmV2aWV3"
    "ZXIiIGNyZWF0ZWQgYW5kIGluc3RhbGxlZCBvbiBhbGwgcmVwb3MKIyAgIDIuIEFwcCBJRCBzdG9y"
    "ZWQgYXMgb3JnL3JlcG8gdmFyaWFibGU6IFJFVklFV0VSX0FQUF9JRAojICAgMy4gQXBwIHByaXZh"
    "dGUga2V5IHN0b3JlZCBhcyBvcmcvcmVwbyBzZWNyZXQ6IFJFVklFV0VSX0FQUF9QUklWQVRFX0tF"
    "WQojICAgNC4gQnJhbmNoIHByb3RlY3Rpb246IHJlcXVpcmUgMSBhcHByb3ZpbmcgcmV2aWV3LCBl"
    "bmZvcmNlIGFkbWlucwojCiMgQ2FsbGVkIGZyb20gZWFjaCByZXBvIHZpYToKIyAgIHVzZXM6IG1h"
    "cnR5bWNlbnJvZS9Bc3NlbWJseVplcm8vLmdpdGh1Yi93b3JrZmxvd3MvYXV0by1yZXZpZXdlci55"
    "bWxAbWFpbgojCiMgSXNzdWU6ICM3MzYgfCBSZWxhdGVkOiAjNzMyCgpvbjoKICB3b3JrZmxvd19j"
    "YWxsOgogICAgaW5wdXRzOgogICAgICByZXF1aXJlZF9jaGVja3M6CiAgICAgICAgZGVzY3JpcHRp"
    "b246ID4KICAgICAgICAgIENvbW1hLXNlcGFyYXRlZCBsaXN0IG9mIGNoZWNrIG5hbWVzIHRoYXQg"
    "bXVzdCBwYXNzIGJlZm9yZSBhcHByb3ZhbC4KICAgICAgICAgIERlZmF1bHQ6IHByLXNlbnRpbmVs"
    "LiBPdmVycmlkZSBwZXItcmVwbyBpZiBhZGRpdGlvbmFsIGNoZWNrcyBleGlzdC4KICAgICAgICBy"
    "ZXF1aXJlZDogZmFsc2UKICAgICAgICB0eXBlOiBzdHJpbmcKICAgICAgICBkZWZhdWx0OiAiaXNz"
    "dWUtcmVmZXJlbmNlIgogICAgc2VjcmV0czoKICAgICAgUkVWSUVXRVJfQVBQX0lEOgogICAgICAg"
    "IHJlcXVpcmVkOiB0cnVlCiAgICAgIFJFVklFV0VSX0FQUF9QUklWQVRFX0tFWToKICAgICAgICBy"
    "ZXF1aXJlZDogdHJ1ZQoKcGVybWlzc2lvbnM6CiAgcHVsbC1yZXF1ZXN0czogd3JpdGUKICBjaGVj"
    "a3M6IHJlYWQKCmpvYnM6CiAgYXV0by1yZXZpZXc6CiAgICBydW5zLW9uOiB1YnVudHUtbGF0ZXN0"
    "CiAgICAjIE9ubHkgcnVuIG9uIFBScywgbm90IG9uIHRoZSBQUiBjcmVhdGVkIGJ5IHRoZSBBcHAg"
    "aXRzZWxmIChwcmV2ZW50IGxvb3BzKS4KICAgICMKICAgICMgQ2VyYmVydXMgaXMgdGhlIEFHRU5U"
    "IGZlbmNlLCBub3QgdGhlIERlcGVuZGFib3QgZW5hYmxlciAoIzEyNTEpLgogICAgIyBPbiBhbiBh"
    "Z2VudCBQUiB0aGUgYXV0aG9yIGlzIHRoZSByZXBvIG93bmVyLCBzbyBHaXRIdWIncyBuby1zZWxm"
    "LWFwcHJvdmFsCiAgICAjIHJ1bGUgbGVhdmVzIG5vIGVsaWdpYmxlIHJldmlld2VyIGFuZCBvbmUg"
    "aGFzIHRvIGJlIG1hbnVmYWN0dXJlZCAtLSB0aGF0IGlzCiAgICAjIHdoYXQgdGhpcyB3b3JrZmxv"
    "dyBpcyBmb3IuIE9uIGEgRGVwZW5kYWJvdCBQUiB0aGUgYXV0aG9yIGlzIERlcGVuZGFib3QsIHNv"
    "CiAgICAjIHRoZSBvd25lciBhbHJlYWR5IElTIGFuIGVsaWdpYmxlIHRoaXJkLXBhcnR5IHJldmll"
    "d2VyIGFuZCB0aGVyZSBpcyBub3RoaW5nCiAgICAjIGF0IHRoYXQgZ2F0ZSB0byBndWFyZC4gRGVw"
    "ZW5kYWJvdCBnZXRzIGl0cyBvd24gbGFuZTogdG9vbHMvZGVwZW5kYWJvdF9yZXZpZXcucHkKICAg"
    "ICMgcnVucyB0aGUgc3VpdGUgYW5kIGFwcHJvdmVzIGFzIHRoZSBvd25lci4KICAgIGlmOiAoZ2l0"
    "aHViLmV2ZW50X25hbWUgPT0gJ3B1bGxfcmVxdWVzdCcgfHwgZ2l0aHViLmV2ZW50X25hbWUgPT0g"
    "J3dvcmtmbG93X2NhbGwnKSAmJiBnaXRodWIuZXZlbnQucHVsbF9yZXF1ZXN0LnVzZXIubG9naW4g"
    "IT0gJ2RlcGVuZGFib3RbYm90XScKICAgIHN0ZXBzOgogICAgICAtIG5hbWU6IEdlbmVyYXRlIEFw"
    "cCB0b2tlbgogICAgICAgIGlkOiBhcHAtdG9rZW4KICAgICAgICB1c2VzOiBhY3Rpb25zL2NyZWF0"
    "ZS1naXRodWItYXBwLXRva2VuQHYzCiAgICAgICAgd2l0aDoKICAgICAgICAgIGFwcC1pZDogJHt7"
    "IHNlY3JldHMuUkVWSUVXRVJfQVBQX0lEIH19CiAgICAgICAgICBwcml2YXRlLWtleTogJHt7IHNl"
    "Y3JldHMuUkVWSUVXRVJfQVBQX1BSSVZBVEVfS0VZIH19CgogICAgICAtIG5hbWU6IFdhaXQgZm9y"
    "IHJlcXVpcmVkIGNoZWNrcwogICAgICAgIGVudjoKICAgICAgICAgIEdIX1RPS0VOOiAke3sgZ2l0"
    "aHViLnRva2VuIH19CiAgICAgICAgICBQUl9OVU1CRVI6ICR7eyBnaXRodWIuZXZlbnQucHVsbF9y"
    "ZXF1ZXN0Lm51bWJlciB9fQogICAgICAgICAgUkVRVUlSRURfQ0hFQ0tTOiAke3sgaW5wdXRzLnJl"
    "cXVpcmVkX2NoZWNrcyB9fQogICAgICAgICAgUkVQTzogJHt7IGdpdGh1Yi5yZXBvc2l0b3J5IH19"
    "CiAgICAgICAgICBIRUFEX1NIQTogJHt7IGdpdGh1Yi5ldmVudC5wdWxsX3JlcXVlc3QuaGVhZC5z"
    "aGEgfX0KICAgICAgICBydW46IHwKICAgICAgICAgIGVjaG8gIlBSICMke1BSX05VTUJFUn0g4oCU"
    "IHdhaXRpbmcgZm9yIHJlcXVpcmVkIGNoZWNrczogJHtSRVFVSVJFRF9DSEVDS1N9IgoKICAgICAg"
    "ICAgIElGUz0nLCcgcmVhZCAtcmEgQ0hFQ0tTIDw8PCAiJFJFUVVJUkVEX0NIRUNLUyIKICAgICAg"
    "ICAgICMgIzI2Mjc6IHdhcyAzMCAoMTAgbWludXRlcykuIFdpdGggdGhlIHRlcm1pbmFsLXN0YXRl"
    "IHRlc3QgYmVsb3csIHRoZQogICAgICAgICAgIyBvbmx5IHBhdGggdGhhdCBzdGlsbCByZWFjaGVz"
    "IHRoaXMgY2VpbGluZyBpcyAidGhlIGNoZWNrIHdhcyBuZXZlcgogICAgICAgICAgIyBjcmVhdGVk"
    "IGF0IGFsbCIgLS0gYSBuYW1lIG1pc21hdGNoLCBvciB0aGUgcmVwb3J0aW5nIHNlcnZpY2UgYmVp"
    "bmcKICAgICAgICAgICMgdW5yZWFjaGFibGUuIEZpdmUgbWludXRlcyBpcyBmYXIgYmV5b25kIG5v"
    "cm1hbCByZXBvcnRpbmcgbGF0ZW5jeSBhbmQKICAgICAgICAgICMgaGFsdmVzIHdoYXQgYW4gb3V0"
    "YWdlIGNvc3RzIGluIGJpbGxlZCBtaW51dGVzLgogICAgICAgICAgTUFYX0FUVEVNUFRTPTE1ICAg"
    "IyAxNSDDlyAyMHMgPSA1IG1pbnV0ZXMgbWF4IHdhaXQKICAgICAgICAgIEFUVEVNUFQ9MAoKICAg"
    "ICAgICAgIHdoaWxlIFsgJEFUVEVNUFQgLWx0ICRNQVhfQVRURU1QVFMgXTsgZG8KICAgICAgICAg"
    "ICAgQUxMX1BBU1NFRD10cnVlCgogICAgICAgICAgICBmb3IgY2hlY2tfbmFtZSBpbiAiJHtDSEVD"
    "S1NbQF19IjsgZG8KICAgICAgICAgICAgICBjaGVja19uYW1lPSQoZWNobyAiJGNoZWNrX25hbWUi"
    "IHwgeGFyZ3MpICAjIHRyaW0gd2hpdGVzcGFjZQoKICAgICAgICAgICAgICAjIFF1ZXJ5IGNoZWNr"
    "IHJ1bnMgZm9yIHRoaXMgU0hBIGFuZCBjaGVjayBuYW1lCiAgICAgICAgICAgICAgU1RBVFVTPSQo"
    "Z2ggYXBpIFwKICAgICAgICAgICAgICAgICJyZXBvcy8ke1JFUE99L2NvbW1pdHMvJHtIRUFEX1NI"
    "QX0vY2hlY2stcnVucyIgXAogICAgICAgICAgICAgICAgLS1qcSAiLmNoZWNrX3J1bnNbXSB8IHNl"
    "bGVjdCgubmFtZSB8IGNvbnRhaW5zKFwiJHtjaGVja19uYW1lfVwiKSkgfCAuY29uY2x1c2lvbiIg"
    "XAogICAgICAgICAgICAgICAgMj4vZGV2L251bGwgfCBoZWFkIC0xKQoKICAgICAgICAgICAgICAj"
    "ICMyNjI3OiBBTlkgbm9uLWVtcHR5IGNvbmNsdXNpb24gaXMgdGVybWluYWwuIEdpdEh1YiBwb3B1"
    "bGF0ZXMKICAgICAgICAgICAgICAjIGBjb25jbHVzaW9uYCBvbmx5IHdoZW4gYSBjaGVjayBydW4g"
    "aGFzIENPTVBMRVRFRCAtLSB3aGlsZSBvbmUgaXMKICAgICAgICAgICAgICAjIGdlbnVpbmVseSBp"
    "biBmbGlnaHQgdGhlIGZpZWxkIGlzIG51bGwgLS0gc28gcG9sbGluZyBhIG5vbi1lbXB0eQogICAg"
    "ICAgICAgICAgICMgY29uY2x1c2lvbiBjYW5ub3QgY2hhbmdlIHRoZSBhbnN3ZXIsIGl0IGp1c3Qg"
    "c3BlbmRzIG1pbnV0ZXMuCiAgICAgICAgICAgICAgIwogICAgICAgICAgICAgICMgVGhpcyB3YXMg"
    "cHJldmlvdXNseSBhbiBhbGxvd2xpc3Qgb2YgYGZhaWx1cmVgIGFuZCBgY2FuY2VsbGVkYCwKICAg"
    "ICAgICAgICAgICAjIHdoaWNoIG1lYW50IGBhY3Rpb25fcmVxdWlyZWRgICh3aGF0IHRoZSBzZW50"
    "aW5lbCBwb3N0cyB3aGVuIGl0cwogICAgICAgICAgICAgICMgaXNzdWUtcmVmZXJlbmNlIHJlZ2V4"
    "IGV4dHJhY3RzIGEgcmVmIGl0IGNhbm5vdCB2YWxpZGF0ZSkgZmVsbAogICAgICAgICAgICAgICMg"
    "dGhyb3VnaCB0byAicGVuZGluZyIgYW5kIHdhcyBwb2xsZWQgZm9yIHRoZSBmdWxsIHRlbiBtaW51"
    "dGVzLgogICAgICAgICAgICAgICMgTWVhc3VyZWQgYWNyb3NzIHRoZSBmbGVldCBpbiBBdWd1c3Q6"
    "IDI5IHJ1bnMgZGllZCB0aGlzIHdheSwKICAgICAgICAgICAgICAjIH4zMDAgYmlsbGVkIG1pbnV0"
    "ZXMsIHJvdWdobHkgMTAlIG9mIHRoZSBtb250aGx5IGFsbG93YW5jZS4KICAgICAgICAgICAgICAj"
    "CiAgICAgICAgICAgICAgIyBEZWxpYmVyYXRlbHkgYSB0ZXN0IGZvciAiY29tcGxldGVkIGFuZCBu"
    "b3Qgc3VjY2VzcyIgcmF0aGVyIHRoYW4KICAgICAgICAgICAgICAjIGEgbG9uZ2VyIGFsbG93bGlz"
    "dC4gRW51bWVyYXRpbmcgc3RhdGVzIGlzIGhvdyBhY3Rpb25fcmVxdWlyZWQKICAgICAgICAgICAg"
    "ICAjIHdhcyBtaXNzZWQgaW4gdGhlIGZpcnN0IHBsYWNlLCBhbmQgdGhlIG5leHQgdW5saXN0ZWQg"
    "Y29uY2x1c2lvbgogICAgICAgICAgICAgICMgd291bGQgYmUgZGlzY292ZXJlZCB0aGUgc2FtZSB3"
    "YXksIGluIHRlbi1taW51dGUgaW5jcmVtZW50cy4KICAgICAgICAgICAgICAjCiAgICAgICAgICAg"
    "ICAgIyBObyBvdXRjb21lIGNoYW5nZXM6IGV2ZXJ5IHN0YXRlIHRoYXQgdXNlZCB0byB0aW1lIG91"
    "dCBhbHJlYWR5CiAgICAgICAgICAgICAgIyBlbmRlZCBpbiBzdGVwIGZhaWx1cmUuIEl0IG5vdyBn"
    "ZXRzIHRoZXJlIGluIH4yMHMgaW5zdGVhZCBvZgogICAgICAgICAgICAgICMgfjYwMHMuCiAgICAg"
    "ICAgICAgICAgaWYgWyAiJFNUQVRVUyIgPSAic3VjY2VzcyIgXTsgdGhlbgogICAgICAgICAgICAg"
    "ICAgZWNobyAiICDinIUgJHtjaGVja19uYW1lfTogcGFzc2VkIgogICAgICAgICAgICAgIGVsaWYg"
    "WyAtbiAiJFNUQVRVUyIgXTsgdGhlbgogICAgICAgICAgICAgICAgZWNobyAiICDinYwgJHtjaGVj"
    "a19uYW1lfTogJHtTVEFUVVN9IChjb21wbGV0ZWQsIG5vdCBzdWNjZXNzKSDigJQgd2lsbCBOT1Qg"
    "YXBwcm92ZSIKICAgICAgICAgICAgICAgIGV4aXQgMQogICAgICAgICAgICAgIGVsc2UKICAgICAg"
    "ICAgICAgICAgIGVjaG8gIiAg4o+zICR7Y2hlY2tfbmFtZX06IG5vIGNvbmNsdXNpb24geWV0IChh"
    "dHRlbXB0ICQoKEFUVEVNUFQrMSkpLyR7TUFYX0FUVEVNUFRTfSkiCiAgICAgICAgICAgICAgICBB"
    "TExfUEFTU0VEPWZhbHNlCiAgICAgICAgICAgICAgZmkKICAgICAgICAgICAgZG9uZQoKICAgICAg"
    "ICAgICAgaWYgWyAiJEFMTF9QQVNTRUQiID0gdHJ1ZSBdOyB0aGVuCiAgICAgICAgICAgICAgZWNo"
    "byAiIgogICAgICAgICAgICAgIGVjaG8gIkFsbCByZXF1aXJlZCBjaGVja3MgcGFzc2VkLiIKICAg"
    "ICAgICAgICAgICBleGl0IDAKICAgICAgICAgICAgZmkKCiAgICAgICAgICAgIEFUVEVNUFQ9JCgo"
    "QVRURU1QVCsxKSkKICAgICAgICAgICAgc2xlZXAgMjAKICAgICAgICAgIGRvbmUKCiAgICAgICAg"
    "ICBlY2hvICLinYwgVGltZWQgb3V0IGFmdGVyICQoKE1BWF9BVFRFTVBUUyAqIDIwKSlzIOKAlCBy"
    "ZXF1aXJlZCBjaGVjayBuZXZlciByZXBvcnRlZCBhIGNvbmNsdXNpb24uIgogICAgICAgICAgZWNo"
    "byAiICAgTW9zdCBsaWtlbHkgdGhlIGNoZWNrIHdhcyBuZXZlciBjcmVhdGVkOiB2ZXJpZnkgdGhl"
    "IG5hbWUgaW4iCiAgICAgICAgICBlY2hvICIgICB0aGUgcmVxdWlyZWRfY2hlY2tzIGlucHV0IG1h"
    "dGNoZXMgd2hhdCB0aGUgcmVwb3J0aW5nIHNlcnZpY2UgcG9zdHMuIgogICAgICAgICAgZXhpdCAx"
    "CgogICAgICAtIG5hbWU6IEFwcHJvdmUgUFIKICAgICAgICBlbnY6CiAgICAgICAgICBHSF9UT0tF"
    "TjogJHt7IHN0ZXBzLmFwcC10b2tlbi5vdXRwdXRzLnRva2VuIH19CiAgICAgICAgICBQUl9OVU1C"
    "RVI6ICR7eyBnaXRodWIuZXZlbnQucHVsbF9yZXF1ZXN0Lm51bWJlciB9fQogICAgICAgICAgUkVQ"
    "TzogJHt7IGdpdGh1Yi5yZXBvc2l0b3J5IH19CiAgICAgICAgcnVuOiB8CiAgICAgICAgICBlY2hv"
    "ICJTdWJtaXR0aW5nIGFwcHJvdmluZyByZXZpZXcgYXMgR2l0SHViIEFwcC4uLiIKCiAgICAgICAg"
    "ICBnaCBhcGkgXAogICAgICAgICAgICAicmVwb3MvJHtSRVBPfS9wdWxscy8ke1BSX05VTUJFUn0v"
    "cmV2aWV3cyIgXAogICAgICAgICAgICAtZiBldmVudD0iQVBQUk9WRSIgXAogICAgICAgICAgICAt"
    "ZiBib2R5PSJBdXRvLWFwcHJvdmVkOiBhbGwgcmVxdWlyZWQgY2hlY2tzIHBhc3NlZC4g8J+kliIK"
    "CiAgICAgICAgICBlY2hvICLinIUgUFIgIyR7UFJfTlVNQkVSfSBhcHByb3ZlZCBieSBBc3NlbWJs"
    "eVplcm8gUmV2aWV3ZXIiCg=="
)

# Sanity-checked before anything is sent: a corrupted payload must not reach the
# API looking like a successful deploy.
EXPECTED_MARKERS = (
    'elif [ -n "$STATUS" ]; then',
    "MAX_ATTEMPTS=15",
    "name: auto-reviewer",
)

PR_BODY = f"""## The defect

`auto-reviewer.yml`'s "Wait for required checks" step treated every conclusion
except `failure` and `cancelled` as still-pending, and polled 30 times at
20-second intervals before giving up.

**GitHub sets `conclusion` only when a check run has completed.** A non-empty
conclusion is a finished answer, so the loop was re-asking a settled question
for ten minutes. `action_required` -- what the sentinel posts when its
issue-reference regex extracts a ref it cannot validate -- landed squarely in
that gap.

Observed step timing:

```
- Generate App token         [success]     1s
- Wait for required checks   [FAILURE]   611s
- Approve PR                 [skipped]     0s
```

Measured across the private fleet in August: **29 runs died this way, about 300
billed minutes** -- roughly 10% of the monthly Actions allowance, spent entirely
on waiting. 22 of the 29 fell inside one three-day window, which is the shape of
checks not being reported rather than routine per-PR error. The ten-minute price
tag is paid identically either way, and that part is ours.

## The change

**Any non-empty conclusion is terminal.** Inverted rather than extended.
Enumerating states is how `action_required` was missed in the first place; a
longer allowlist leaves the next unlisted conclusion to be discovered the same
way, in ten-minute increments.

**No outcome changes.** Every state that previously timed out already ended in
step failure. It now gets there in ~20 seconds instead of ~600.

**The ceiling drops 30 -> 15 attempts** (10 minutes -> 5). With the above, the
only remaining path to the ceiling is a check that was never created at all --
a name mismatch, or the reporting service being unreachable. Five minutes is far
beyond normal reporting latency.

## Verification

`tests/test_auto_reviewer_wait_loop.py` extracts this exact `run:` block from
the YAML and executes it under bash against a stub `gh`, so what is asserted is
the shipped text rather than a paraphrase. The loop cannot move to a script file
-- this is a reusable workflow, and a caller repo has no checkout of this one.

16 tests: each terminal conclusion exits in under 15s, `success` still approves,
an empty conclusion still polls (asserted by letting it poll and killing it, not
by sitting through the ceiling), and the ceiling is pinned at 15.

Proven non-vacuous by reverting the terminal test to the old allowlist, which
fails 7 of them -- all six terminal states plus the structural check that the
fix is not simply a longer list.

Landed via the Contents API because `.github/workflows/*` requires `workflow`
scope (ADR-0216). Script: `tools/deploy_auto_reviewer_poll_fix.py`, generated
from the tested file with the workflow embedded base64 so the landed bytes are
the tested bytes.

Closes #{ISSUE_NUMBER}
"""


def _request(pat: str, method: str, url: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "assemblyzero-deploy-auto-reviewer-poll-fix",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, {}
        detail = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"HTTP {e.code} on {method} {url}\n{detail}") from e


def exists(pat: str, url: str) -> bool:
    status, _ = _request(pat, "GET", url)
    return status != 404


def main() -> int:
    content = base64.b64decode(WORKFLOW_B64)
    text = content.decode("utf-8")
    for marker in EXPECTED_MARKERS:
        if marker not in text:
            raise SystemExit(f"ABORT: embedded workflow is missing {marker!r} -- regenerate")
    if b"\r\n" in content:
        raise SystemExit("ABORT: embedded workflow has CRLF line endings")
    print(f"Payload verified: {len(content)} bytes, {len(text.splitlines())} lines")

    base = f"{GH_API}/repos/{GITHUB_USER}/{REPO}"
    print(f"Target: {GITHUB_USER}/{REPO}  branch: {BRANCH}")
    print()

    with classic_pat_session() as pat:
        _, open_prs = _request(
            pat, "GET", f"{base}/pulls?state=open&head={GITHUB_USER}:{BRANCH}&per_page=10"
        )
        if open_prs:
            pr = open_prs[0]
            print(f"  Open PR already exists: #{pr['number']} {pr['html_url']}")
            print("  No-op. Merge through the normal flow.")
            return 0

        if not exists(pat, f"{base}/git/refs/heads/{BRANCH}"):
            _, ref = _request(pat, "GET", f"{base}/git/refs/heads/main")
            sha = ref["object"]["sha"]
            print(f"  Creating branch {BRANCH} from main@{sha[:7]}...")
            _request(pat, "POST", f"{base}/git/refs",
                     {"ref": f"refs/heads/{BRANCH}", "sha": sha})
        else:
            print(f"  Branch {BRANCH} already on origin.")

        _, current = _request(pat, "GET", f"{base}/contents/{WORKFLOW_PATH}?ref={BRANCH}")
        blob_sha = current.get("sha")
        if blob_sha and base64.b64decode(current.get("content", "")) == content:
            print("  Workflow already up to date on the branch.")
        else:
            print(f"  PUT {WORKFLOW_PATH} on {BRANCH}...")
            payload = {
                "message": TITLE,
                "content": base64.b64encode(content).decode("ascii"),
                "branch": BRANCH,
            }
            if blob_sha:
                payload["sha"] = blob_sha
            _request(pat, "PUT", f"{base}/contents/{WORKFLOW_PATH}", payload)
            print("    succeeded.")

        print("  Opening PR...")
        _, pr = _request(pat, "POST", f"{base}/pulls", {
            "title": TITLE, "head": BRANCH, "base": "main", "body": PR_BODY,
        })
        print()
        print(f"PR #{pr['number']} opened: {pr['html_url']}")
        print()
        print("This changes the workflow EVERY repo calls, so watch the first")
        print("agent PR that merges after it: the wait step should now settle in")
        print("seconds, and a stuck check should fail in ~20s rather than 10 min.")
        print()
        print(f"  gh pr merge {pr['number']} --squash --repo {GITHUB_USER}/{REPO}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
