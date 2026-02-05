```python
diff --git a/mymodule.py b/mymodule.py
index abc123..def456 100644
--- a/mymodule.py
+++ b/mymodule.py
@@ -1,5 +1,5 @@
 from typing import TypedDict
 
-class OldClassName:
+class NewClassName:
     pass
 
diff --git a/usage.py b/usage.py
index xyz789..uvw012 100644
--- a/usage.py
+++ b/usage.py
@@ -1,3 +1,3 @@
-from mymodule import OldClassName
+from mymodule import NewClassName
 
-def process(obj: OldClassName):
+def process(obj: NewClassName):
     pass
```
