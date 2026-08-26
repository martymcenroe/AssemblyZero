"""The target repo's visual-gate declaration (#2518).

The gate's knowledge -- which issues carry a visual deliverable, how to render
the contract, what the palette's separation floor is, which values are pinned
by landed rulings -- belongs to the TARGET repo's binding docs, not to
AssemblyZero. A repo declares it in ``docs/design/visual-gate.json``; a repo
without the file simply has no visual gate, and the stage skips.

Shape::

    {
      "issues": [331, 332],
      "renderer_cmd": ["poetry", "run", "python", "tools/visual_contract_render.py"],
      "contract": "docs/design/0002-aesthetic-v1-stingray.md",
      "separation_floor": 85,
      "ruled": {"needle_rgb": [247, 57, 35]},
      "open_browser": true,
      "notify": {
        "enabled": true,
        "toast_backoff_seconds": [600, 1800, 3600],
        "email_after_seconds": 14400,
        "email_from": ""
      }
    }

``renderer_cmd`` runs with the target repo as cwd, so the repo's own
environment convention (poetry, house rules) resolves the interpreter and its
imaging deps. ``ruled`` maps contract keys to the value a landed ruling pinned;
a Modify delta that would change one halts for the operator (#2518 guardrail).
``open_browser`` (#2528) and ``notify`` (#2529) are optional; their absence
means the defaults shown (auto-open on a round's first serve; toast at 10
minutes, 30 more, then hourly; one backstop email at 4 hours to the operator
contact — the email needs ``email_from`` set to an SES-verified identity, via
this file or the ``AZ_OPERATOR_EMAIL_FROM`` environment variable).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_REL = Path("docs") / "design" / "visual-gate.json"


@dataclass(frozen=True)
class GateConfig:
    issues: tuple[int, ...]
    renderer_cmd: tuple[str, ...]
    contract: str
    separation_floor: float
    ruled: dict = field(default_factory=dict)
    #: #2528: on a round's FIRST serve the gate opens the review page in the
    #: operator's default browser itself. Default ON by the operator's own
    #: request; a repo can declare it off, and the environment can too (see
    #: gate.py) for operators who hate focus-stealing.
    open_browser: bool = True
    #: #2529: the escalating-notification declaration (toast backoff, email
    #: backstop). Raw mapping; the wait parses it via NotifyConfig so the
    #: intervals and the kill switch live with the repo's other gate law.
    notify: dict = field(default_factory=dict)


def load_gate_config(target_repo: Path | str) -> GateConfig | None:
    """The repo's declaration, or None when the repo declares no gate.

    A present-but-unreadable file returns None the same as an absent one is
    NOT acceptable -- a repo that declared a gate and then broke the
    declaration must not silently roll ungated. Malformed JSON raises.
    """
    path = Path(target_repo) / CONFIG_REL
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return GateConfig(
        issues=tuple(int(n) for n in data.get("issues", [])),
        renderer_cmd=tuple(str(part) for part in data.get("renderer_cmd", [])),
        contract=str(data.get("contract", "")),
        separation_floor=float(data.get("separation_floor", 0)),
        ruled=dict(data.get("ruled", {})),
        open_browser=bool(data.get("open_browser", True)),
        notify=dict(data.get("notify", {})),
    )


def gate_applies(config: GateConfig | None, issue: int) -> bool:
    """Whether this issue's deliverable is declared visual."""
    return bool(config) and issue in config.issues
