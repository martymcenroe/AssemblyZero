```python
diff --git a/src/types.py b/src/types.py
index 3456789..cdef012 100644
--- a/src/types.py
+++ b/src/types.py
@@ -1,11 +1,6 @@
 from typing import TypedDict
 
-UserData = TypedDict('UserData', {
-    'name': str,
-    'email': str,
-    'age': int,
-})
-
 ConfigData = TypedDict('ConfigData', {
     'host': str,
     'port': int,
@@ -15,7 +10,7 @@ ConfigData = TypedDict('ConfigData', {
 def process_config(config: ConfigData) -> None:
     pass
 
-def process_user(user: UserData) -> None:
+def process_user(user: dict) -> None:
     pass
 
 def get_default_config() -> ConfigData:
diff --git a/src/services.py b/src/services.py
index 4567890..def0123 100644
--- a/src/services.py
+++ b/src/services.py
@@ -1,8 +1,4 @@
-from types import UserData
-
 def handle_user(data: dict) -> None:
     pass
 
-def validate_user(user: UserData) -> bool:
-    return True
-
+# UserData type removed but still referenced above
```
