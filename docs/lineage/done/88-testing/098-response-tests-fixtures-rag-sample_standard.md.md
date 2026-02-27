

```markdown
# Standard 0099: Code Review Requirements

## 1. Overview

All code changes must undergo peer review before merging to the main branch. This standard defines the minimum requirements for code review.

## 2. Review Criteria

Reviewers must verify:
- Correctness: Code does what it claims to do
- Test coverage: New code has >= 95% test coverage
- Style: Code follows project naming conventions
- Security: No hardcoded secrets or SQL injection vulnerabilities
- Documentation: Public APIs have docstrings

## 3. Review Process

1. Author creates pull request with description
2. At least one reviewer approves
3. CI pipeline passes all checks
4. Author merges after approval
```
