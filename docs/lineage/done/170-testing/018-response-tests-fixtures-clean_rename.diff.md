```python
diff --git a/agentos/types.py b/agentos/types.py
index 1234567..abcdefg 100644
--- a/agentos/types.py
+++ b/agentos/types.py
@@ -10,7 +10,7 @@
 from typing import TypedDict
 
-class WorkflowConfig:
+class WorkflowConfiguration:
     """Configuration for workflow."""
     pass
diff --git a/agentos/workflow.py b/agentos/workflow.py
index 2345678..bcdefgh 100644
--- a/agentos/workflow.py
+++ b/agentos/workflow.py
@@ -1,7 +1,7 @@
 """Workflow implementation."""
 
-from agentos.types import WorkflowConfig
+from agentos.types import WorkflowConfiguration
 
-def create_workflow(config: WorkflowConfig) -> None:
+def create_workflow(config: WorkflowConfiguration) -> None:
     """Create a workflow."""
     pass
diff --git a/agentos/validator.py b/agentos/validator.py
index 3456789..cdefghi 100644
--- a/agentos/validator.py
+++ b/agentos/validator.py
@@ -1,9 +1,9 @@
 """Validator module."""
 
-from agentos.types import WorkflowConfig
+from agentos.types import WorkflowConfiguration
 
-def validate(cfg: WorkflowConfig) -> bool:
+def validate(cfg: WorkflowConfiguration) -> bool:
     """Validate configuration."""
     return True
diff --git a/tests/test_workflow.py b/tests/test_workflow.py
index 4567890..defghij 100644
--- a/tests/test_workflow.py
+++ b/tests/test_workflow.py
@@ -1,7 +1,7 @@
 """Test workflow."""
 
-from agentos.types import WorkflowConfig
-from agentos.workflow import create_workflow
+from agentos.types import WorkflowConfiguration
+from agentos.workflow import create_workflow
 
 def test_workflow_creation():
     """Test workflow creation."""
-    config = WorkflowConfig()
+    config = WorkflowConfiguration()
     create_workflow(config)
     assert True
```
