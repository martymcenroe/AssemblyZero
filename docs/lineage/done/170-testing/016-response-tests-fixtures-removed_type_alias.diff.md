```python
diff --git a/agentos/state.py b/agentos/state.py
index 1234567..abcdefg 100644
--- a/agentos/state.py
+++ b/agentos/state.py
@@ -5,7 +5,7 @@
 from typing import TypedDict
 
-WorkflowState = TypedDict('WorkflowState', {
+AgentState = TypedDict('AgentState', {
     'messages': list[str],
     'current_step': str,
     'data': dict
 })
diff --git a/agentos/nodes/base.py b/agentos/nodes/base.py
index 2345678..bcdefgh 100644
--- a/agentos/nodes/base.py
+++ b/agentos/nodes/base.py
@@ -1,7 +1,7 @@
 """Base node implementations."""
 
-from agentos.state import WorkflowState
+from agentos.state import AgentState
 
-def process_node(state: WorkflowState) -> WorkflowState:
+def process_node(state: AgentState) -> AgentState:
     """Process a workflow node."""
     return state
diff --git a/agentos/workflows/main.py b/agentos/workflows/main.py
index 3456789..cdefghi 100644
--- a/agentos/workflows/main.py
+++ b/agentos/workflows/main.py
@@ -2,8 +2,8 @@
 
 # This import was NOT updated - creating an orphaned usage
 # This simulates a TypedDict alias removal without updating all references
-from agentos.state import WorkflowState
+from agentos.state import AgentState
 
-def initialize() -> WorkflowState:
+def initialize() -> AgentState:
     """Initialize workflow state."""
-    return WorkflowState(messages=[], current_step='start', data={})
+    return AgentState(messages=[], current_step='start', data={})
diff --git a/tests/test_state.py b/tests/test_state.py
index 4567890..defghij 100644
--- a/tests/test_state.py
+++ b/tests/test_state.py
@@ -1,10 +1,10 @@
 """Test state management."""
 
 # This usage was NOT updated - orphaned reference to old TypedDict name
-from agentos.state import WorkflowState
+from agentos.state import AgentState
 
 def test_state_creation():
     """Test state creation."""
-    state: WorkflowState = {
+    state: AgentState = {
         'messages': ['hello'],
         'current_step': 'test',
         'data': {}
```
