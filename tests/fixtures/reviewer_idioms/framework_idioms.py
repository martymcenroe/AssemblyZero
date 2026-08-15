"""Framework idioms the spec reviewer recommends, which the symbol checker must accept.

Issue #2397. This corpus is the contract between two gates that have twice
deadlocked the drafter against each other:

* the spec reviewer (N5) tells the drafter to write a framework call;
* the symbol checker (N3) rejects it as a hallucinated API, because the method
  is absent from the target repo's gathered symbols.

Neither gate's own suite can see the disagreement — each pins its own behaviour
against its own fixtures, and the fault lives in the relationship. When the sets
diverge the drafter is handed a contradiction it cannot satisfy at any iteration
count, so the loop burns its budget and the stage dies at the cap. That has cost
two rolls: 91 seconds (#2391) and 13m 12s (#2396).

PROVENANCE, and a correction to #2397's own proposal
----------------------------------------------------
The issue proposed sourcing this list from the reviewer's prompt "where it
enumerates them". No such enumeration exists. Neither `review_spec.py` nor
`generate_spec.py` names these idioms; the reviewer is a general model applying
its own knowledge of pytest best practice, so the population is not derivable
from our code at all.

The corpus is therefore sourced EMPIRICALLY, from readiness verdicts the
reviewer actually produced, harvested by `tools/harvest_reviewer_idioms.py`.
Entries marked OBSERVED are verbatim reviewer instructions from a real run.
Entries marked SURFACE are the rest of the documented API of a fixture the
checker already exempts — included because a reviewer that recommended one
method of an object can recommend its siblings, and the point of this file is to
stop meeting shapes one roll at a time.

Each entry is a complete snippet, not a bare expression: `tmp_path.replace()` is
only exempt when `tmp_path` is a declared parameter, which is exactly the
distinction the checker draws and the contract must preserve.

ADDING TO THIS CORPUS
---------------------
When a roll dies on a reviewer-dictated idiom, add it here with its run and
verdict line. Run `poetry run python tools/harvest_reviewer_idioms.py --repo
<target>` to list candidates in that repo's verdicts that this corpus does not
yet cover.
"""

#: (name, provenance, snippet). The snippet is a complete Python fence body.
FRAMEWORK_IDIOMS: list[tuple[str, str, str]] = [
    (
        "pytest_addoption registration",
        "OBSERVED — run-issue1-173403, the #2391 deadlock. Reviewer demanded a "
        "conftest.py registering the custom flag; boostgauge ruling #271 "
        "mandates it and pytest crashes on unregistered flags.",
        'def pytest_addoption(parser):\n'
        '    parser.addoption(\n'
        '        "--generate-baselines",\n'
        '        action="store_true",\n'
        '        default=False,\n'
        '        help="Generate visual regression baseline images",\n'
        '    )\n',
    ),
    (
        "request.config.getoption",
        "OBSERVED — run-issue1-193349, the #2396 deadlock. "
        "012-readiness-verdict.md line 7, verbatim: 'use "
        '`request.config.getoption("--generate-baselines", False)` to read the '
        "custom flag reliably'.",
        'def test_req_120_visual(request, tmp_path):\n'
        '    generate = request.config.getoption("--generate-baselines", False)\n'
        '    return generate\n',
    ),
    (
        "tmp_path filesystem methods",
        "OBSERVED — `tmp_path.replace()` appears in a boostgauge readiness "
        "verdict. tmp_path is a pathlib.Path supplied by pytest.",
        'def test_writes(tmp_path):\n'
        '    target = tmp_path / "cfg.json"\n'
        '    target.write_text("{}")\n'
        '    target.replace(tmp_path / "cfg.bak")\n',
    ),
    (
        "monkeypatch",
        "SURFACE — pytest builtin fixture already exempt by name; these are its "
        "documented core methods, which a reviewer recommending one can "
        "recommend instead.",
        'def test_env(monkeypatch, tmp_path):\n'
        '    monkeypatch.setenv("BG_HOME", str(tmp_path))\n'
        '    monkeypatch.delenv("BG_DEBUG", raising=False)\n'
        '    monkeypatch.setattr("sys.platform", "linux")\n'
        '    monkeypatch.chdir(tmp_path)\n',
    ),
    (
        "capsys / capfd",
        "SURFACE — pytest builtin output-capture fixtures.",
        'def test_output(capsys):\n'
        '    captured = capsys.readouterr()\n'
        '    return captured.out\n',
    ),
    (
        "caplog",
        "SURFACE — pytest builtin logging fixture.",
        'def test_logs(caplog):\n'
        '    caplog.set_level("INFO")\n'
        '    return caplog.records\n',
    ),
    (
        "request attributes beyond config",
        "SURFACE — the #2396 class at other depths. `request` is exempt; every "
        "attribute reached from it is pytest's, not the target repo's.",
        'def test_meta(request):\n'
        '    request.config.getoption("--x")\n'
        '    request.node.get_closest_marker("slow")\n'
        '    request.config.option.verbose\n'
        '    request.addfinalizer(lambda: None)\n',
    ),
    (
        "pytest_collection_modifyitems hook",
        "SURFACE — pluggy hook; pytest supplies every argument.",
        'def pytest_collection_modifyitems(config, items):\n'
        '    if config.getoption("--slow"):\n'
        '        return\n'
        '    for item in items:\n'
        '        item.add_marker("skip")\n',
    ),
    (
        "Pillow object returned by a repo function",
        "OBSERVED — `img.getpixel(px)[3] == int(255 * 0.2)` and "
        "`draw.arc(..., start=-val_to_angle(100), ...)` appear verbatim in "
        "boostgauge readiness verdicts. Carried in its real import-bearing "
        "form, which is what draft 013 has. The import-less form deadlocks "
        "today — see #2399 and the xfail in test_gate_agreement.py.",
        'from PIL import Image, ImageDraw\n'
        'from boostgauge.gauge import render, val_to_angle\n'
        '\n'
        'def test_req_070():\n'
        '    img = render(50, [], 256)\n'
        '    draw = ImageDraw.Draw(img)\n'
        '    draw.arc((0, 0, 10, 10), start=-val_to_angle(100), end=0)\n'
        '    assert img.getpixel((10, 10)) == (255, 255, 255, 255)\n',
    ),
    (
        "pytest_configure hook",
        "SURFACE — pluggy hook; the marker-registration idiom a reviewer "
        "recommends alongside pytest_addoption.",
        'def pytest_configure(config):\n'
        '    config.addinivalue_line("markers", "visual: visual regression")\n',
    ),
]
