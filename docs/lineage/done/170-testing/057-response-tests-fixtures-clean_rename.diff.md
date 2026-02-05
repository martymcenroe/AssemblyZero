```python
diff --git a/src/models.py b/src/models.py
index 1234567..abcdef0 100644
--- a/src/models.py
+++ b/src/models.py
@@ -1,10 +1,10 @@
 from typing import TypedDict
 
-class OldClassName:
-    """Original class that was renamed."""
+class NewClassName:
+    """Renamed version of the class."""
     def __init__(self):
         self.value = 42
 
-class NewClassName:
-    """Renamed version of the class."""
+class AnotherClass:
+    """Another class in the module."""
     def __init__(self):
@@ -15,7 +15,7 @@ def process_data(data: dict) -> None:
     pass
 
 def create_instance():
     return NewClassName()
 
 def get_type_hint() -> type:
     return NewClassName
diff --git a/src/usage.py b/src/usage.py
index 2345678..bcdef01 100644
--- a/src/usage.py
+++ b/src/usage.py
@@ -1,8 +1,8 @@
 from models import NewClassName
 
 def use_class():
     instance = NewClassName()
     return instance
 
 def annotated_function(obj: NewClassName) -> None:
     pass
```
