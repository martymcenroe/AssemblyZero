```python
--- a/types.py
+++ b/types.py
@@ -1,3 +1,3 @@
-OldType = TypedDict('OldType', {'field': str})
+NewType = TypedDict('NewType', {'field': str})
 
 # Orphaned usage in another file still references OldType
+from types import OldType
```
