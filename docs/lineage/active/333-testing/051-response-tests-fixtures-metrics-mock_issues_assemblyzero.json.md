The file `tests/fixtures/metrics/mock_issues_assemblyzero.json` already exists and matches the LLD specification exactly. The test failures are from TDD RED stubs in `test_issue_333.py` (all `assert False`) — they're not caused by this fixture file. The fixture is correct as-is:

```json
[
    {
        "number": 333,
        "title": "Feature: Cross-Project Metrics Aggregation",
        "state": "open",
        "created_at": "2026-02-17T10:00:00Z",
        "closed_at": null,
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 320,
        "title": "Bug: Fix workflow state persistence",
        "state": "closed",
        "created_at": "2026-02-10T08:30:00Z",
        "closed_at": "2026-02-12T14:15:00Z",
        "labels": ["bug", "tdd"],
        "pull_request": null
    },
    {
        "number": 315,
        "title": "Feature: Add LLD review workflow",
        "state": "closed",
        "created_at": "2026-02-08T09:00:00Z",
        "closed_at": "2026-02-09T16:45:00Z",
        "labels": ["feature", "requirements", "lld"],
        "pull_request": null
    },
    {
        "number": 310,
        "title": "Docs: Update testing strategy",
        "state": "closed",
        "created_at": "2026-02-06T11:00:00Z",
        "closed_at": "2026-02-06T18:30:00Z",
        "labels": ["documentation"],
        "pull_request": null
    },
    {
        "number": 308,
        "title": "Feature: Implementation spec generation",
        "state": "closed",
        "created_at": "2026-02-05T14:00:00Z",
        "closed_at": "2026-02-07T10:00:00Z",
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 305,
        "title": "PR: Fix import cycle",
        "state": "closed",
        "created_at": "2026-02-04T16:00:00Z",
        "closed_at": "2026-02-04T17:30:00Z",
        "labels": ["bug"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/AssemblyZero/pulls/305"}
    },
    {
        "number": 304,
        "title": "Feature: Implementation readiness checks",
        "state": "closed",
        "created_at": "2026-02-03T09:00:00Z",
        "closed_at": "2026-02-05T11:00:00Z",
        "labels": ["feature", "requirements"],
        "pull_request": null
    },
    {
        "number": 300,
        "title": "Bug: SQLite checkpoint corruption",
        "state": "open",
        "created_at": "2026-02-02T10:00:00Z",
        "closed_at": null,
        "labels": ["bug"],
        "pull_request": null
    },
    {
        "number": 295,
        "title": "Feature: Gemini model selection",
        "state": "closed",
        "created_at": "2026-01-31T08:00:00Z",
        "closed_at": "2026-02-01T15:00:00Z",
        "labels": ["feature"],
        "pull_request": null
    },
    {
        "number": 290,
        "title": "PR: Add retry logic to API calls",
        "state": "closed",
        "created_at": "2026-01-30T12:00:00Z",
        "closed_at": "2026-01-30T14:00:00Z",
        "labels": ["enhancement"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/AssemblyZero/pulls/290"}
    },
    {
        "number": 285,
        "title": "Feature: TDD workflow support",
        "state": "closed",
        "created_at": "2026-01-29T09:00:00Z",
        "closed_at": "2026-01-30T17:00:00Z",
        "labels": ["feature", "tdd"],
        "pull_request": null
    },
    {
        "number": 280,
        "title": "Feature: Mermaid diagram quality gate",
        "state": "open",
        "created_at": "2026-01-28T11:00:00Z",
        "closed_at": null,
        "labels": ["feature", "implementation"],
        "pull_request": null
    },
    {
        "number": 277,
        "title": "Feature: Mechanical validation",
        "state": "closed",
        "created_at": "2026-01-27T10:00:00Z",
        "closed_at": "2026-01-28T09:00:00Z",
        "labels": ["feature", "requirements"],
        "pull_request": null
    },
    {
        "number": 275,
        "title": "PR: Refactor workflow state types",
        "state": "closed",
        "created_at": "2026-01-27T08:00:00Z",
        "closed_at": "2026-01-27T10:00:00Z",
        "labels": ["refactor"],
        "pull_request": {"url": "https://api.github.com/repos/martymcenroe/AssemblyZero/pulls/275"}
    },
    {
        "number": 270,
        "title": "Bug: Audit report generation failure",
        "state": "open",
        "created_at": "2026-01-26T14:00:00Z",
        "closed_at": null,
        "labels": ["bug"],
        "pull_request": null
    }
]
```
