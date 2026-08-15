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

    # ---- STANDARD, seeded rather than harvested (#2411) -------------------
    #
    # Harvesting from readiness verdicts has a structural blind spot: an idiom
    # too standard for any reviewer to bother demanding never appears in a
    # verdict, so it never enters this corpus, so nothing covers it, so it kills
    # a roll. `@pytest.mark.parametrize` did exactly that, on the fifth kill of
    # the receiver-resolution class. These entries are seeded from pytest's
    # documented surface independent of the harvest, and the parametrize shape
    # is carried in BOTH decorator and expression position, because the defect
    # turned out to be about attribute-chain depth rather than AST position.
    (
        "pytest.mark.parametrize, decorator position",
        "STANDARD — the #2411 kill. run-issue1-114223 flagged `parametrize`, "
        'exemplar `@pytest.mark.parametrize("value,expected_angle", '
        "[(0, 225.0), (50, 90.0), (100, ...`. Two hops from an imported root.",
        'import pytest\n'
        '\n'
        '@pytest.mark.parametrize("value,expected_angle", [(0, 225.0), (50, 90.0)])\n'
        'def test_val_to_angle(value, expected_angle):\n'
        '    assert value >= 0\n',
    ),
    (
        "pytest.mark.parametrize, expression position",
        "STANDARD — the same chain outside a decorator. Proves the exemption "
        "is about provenance, not position.",
        'import pytest\n'
        '\n'
        'def test_builds_marks():\n'
        '    marker = pytest.mark.parametrize("value", [1, 2])\n'
        '    return marker\n',
    ),
    (
        "pytest.mark custom marker chains",
        "STANDARD — `@pytest.mark.<anything>` is open-ended by design; a "
        "marker name is never a repo symbol and can be arbitrary.",
        'import pytest\n'
        '\n'
        '@pytest.mark.slow\n'
        '@pytest.mark.visual\n'
        '@pytest.mark.usefixtures("tmp_path")\n'
        'def test_marked():\n'
        '    pass\n',
    ),
    (
        "pytest.fixture, bare and parameterised",
        "STANDARD — one hop, so it already cleared; carried so that a future "
        "refactor cannot lose it silently.",
        'import pytest\n'
        '\n'
        '@pytest.fixture\n'
        'def plain():\n'
        '    return 1\n'
        '\n'
        '@pytest.fixture(scope="module", params=[1, 2])\n'
        'def parameterised(request):\n'
        '    return request.param\n',
    ),
    (
        "pytest.raises / warns / approx",
        "STANDARD — the assertion surface essentially every test file uses.",
        'import pytest\n'
        '\n'
        'def test_assertions():\n'
        '    with pytest.raises(ValueError):\n'
        '        raise ValueError("x")\n'
        '    with pytest.warns(UserWarning):\n'
        '        pass\n'
        '    assert 0.1 + 0.2 == pytest.approx(0.3)\n',
    ),
    (
        "pytest.mark.skip / skipif / xfail",
        "STANDARD — two hops from an imported root, the #2411 shape exactly.",
        'import sys\n'
        'import pytest\n'
        '\n'
        '@pytest.mark.skip(reason="not ready")\n'
        'def test_skipped():\n'
        '    pass\n'
        '\n'
        '@pytest.mark.skipif(sys.platform == "win32", reason="posix only")\n'
        'def test_conditional():\n'
        '    pass\n'
        '\n'
        '@pytest.mark.xfail(strict=True)\n'
        'def test_expected_failure():\n'
        '    pass\n',
    ),
    (
        "pytest.skip / xfail / fail called in a body",
        "STANDARD — the imperative forms, one hop, expression position.",
        'import pytest\n'
        '\n'
        'def test_imperative(flag):\n'
        '    if flag:\n'
        '        pytest.skip("nope")\n'
        '        pytest.xfail("known")\n'
        '        pytest.fail("boom")\n',
    ),
]
