```diff
--- a/mymodule.py
+++ b/mymodule.py
@@ -1,5 +1,5 @@
-class OldClassName:
+class NewClassName:
     def method(self):
         pass
     
+# Usage in another file
+from mymodule import OldClassName
```
