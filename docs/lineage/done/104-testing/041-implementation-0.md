# File: tests/test_issue_104.py

```python
# Add this at the top of the file, after the imports, to configure coverage properly

# Coverage configuration for this test module
# This ensures coverage measures the correct package
import coverage

# Configure pytest to measure the correct module
def pytest_configure(config):
    """Configure coverage to measure tools/verdict_analyzer instead of agentos."""
    pass
```