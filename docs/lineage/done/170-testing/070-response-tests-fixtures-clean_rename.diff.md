```python
diff --git a/agentos/types.py b/agentos/types.py
index 1234567..abcdef0 100644
--- a/agentos/types.py
+++ b/agentos/types.py
@@ -10,9 +10,9 @@ from typing import Any, TypedDict
 
 logger = logging.getLogger(__name__)
 
-class OldClassName:
-    """This class was renamed properly."""
+class NewClassName:
+    """This class was renamed and all usages updated."""
     pass
 
 
 class WorkflowState(TypedDict):
diff --git a/agentos/utils.py b/agentos/utils.py
index abcdef0..9876543 100644
--- a/agentos/utils.py
+++ b/agentos/utils.py
@@ -1,6 +1,6 @@
 """Utility functions."""
 
-from agentos.types import OldClassName
+from agentos.types import NewClassName
 
 
-def process(obj: OldClassName) -> None:
+def process(obj: NewClassName) -> None:
     """Process an object."""
     pass
```
