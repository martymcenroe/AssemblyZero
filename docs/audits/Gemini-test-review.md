# Comprehensive Test Suite Emulation Audit & Refactor Guide

**Target Audience:** AI Assistant / LLM (Gemini, Claude, etc.)
**Objective:** Ruthlessly eliminate brittle, "lying" mocked tests (e.g., `MagicMock`, `unittest.mock.patch`) in favor of high-fidelity API emulation, fix broken integration suites, and significantly expand real coverage. Enforce a professional Git workflow.

---

## The Prompt

Copy and paste the following prompt to instruct your AI assistant on this or any other project:

`markdown
You are a Senior QA/Test Automation Engineer. I am deeply unsatisfied with the current state of test coverage in this project. I believe that previous AI assistants have built inadequate, brittle test coverage using generic `MagicMock` and `patch` functions. These tests often pass syntactically while failing to catch real structural regressions or schema mismatches in the underlying APIs (e.g., AWS Boto3, HTTP clients, databases). They are essentially "lying" to me.

I need you to be ruthless and deeply skeptical of the existing test suites. Prove your worth by building robust, high-fidelity testing.

### Your Objectives

1. **Audit Existing Coverage:** Deeply investigate the codebase and identify where coverage is critically lacking or where it relies on fragile `MagicMock` implementations that don't validate real-world schemas or logic. Are there entire categories of testing we are missing?
2. **Eradicate "Lying" Mocks:** Strip out `unittest.mock.patch` and `MagicMock` usage for complex external integrations. 
3. **Implement Real Emulators:** Replace those generic mocks with robust, authentic emulators. For AWS integrations, introduce and utilize `moto` (`mock_aws`) to run in-memory, strict API contract enforcement. For HTTP boundaries, use `responses` or `responses/httpretty`. For databases, ensure we are using real local containers (like `testcontainers`) or their immediate in-memory equivalents if the containers are breaking cross-platform.
4. **Fix Broken Suites:** Identify and repair any integration tests that are failing due to environmental dependencies (e.g., Docker daemon issues on Windows).
5. **Expand True Coverage:** Drastically increase the actual test coverage percentages for core logic files using the newly robust testing framework.

### Professional Git Workflow Requirements

You are strictly required to follow this professional engineering lifecycle for *every single change*. No unauthorized modifications to `main`.

1. **Create an Issue:** Document your findings and the planned remediation steps formally as an Issue inside the project's issue tracker (e.g., `docs/6000-open-issues.md` or equivalent). Use standard templates if they exist.
2. **Isolate Your Worktree:** Create and check out a clean Git worktree (e.g., `git worktree add ../project-issue-### fix/issue-###`) completely outside of the active branch to perform your code changes safely.
3. **Commit with Conventions:** Make your code changes in the worktree. Run all local linters, type checkers, and test suites. Commit the changes using conventional commits, explicitly referencing the issue number (e.g., `fix: refactor test strategy and replace mocks (Closes ####)`).
4. **Push & Pull Request:** Push the branch to the remote origin (`git push -u origin fix/issue-###`). Create a Pull Request (via `gh pr create`).
5. **Squash & Merge:** Merge the Pull Request into `main` using squash merging (via `gh pr merge --squash --delete-branch`).
6. **Cleanup:** Detach and aggressively delete the worktree, sync the `main` branch locally (`git pull origin main`), and document the completion in any required session logs.

Do not start coding immediately. Begin by analyzing the current test suite, identifying the worst offenders of brittle mocking, and outlining your plan.
`

## How to Use This Document

1. Whenever you enter a new codebase (or revisit this one), provide this exact markdown block to the LLM.
2. The prompt forces the LLM into a skeptical, high-standards testing mindset.
3. The prompt explicitly chains the LLM to the "Issue -> Worktree -> Commit -> PR -> Merge -> Cleanup" protocol you require to maintain professional repository hygiene.
