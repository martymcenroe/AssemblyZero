```python
"""Assembly node for sequential LLD generation.

Issue #607: Mechanical Document Assembly Node
"""
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from assemblyzero.nodes.document_assembler import (
    strip_hallucinated_headers, 
    assemble_final_document,
    AssemblyError
)
from assemblyzero.workflows.lld.templates import LLD_TEMPLATE

def assemble_document_node(state: dict[str, Any]) -> dict[str, Any]:
    """Executes sequential mechanical document assembly."""
    issue_context = state.get("issue_context", "")
    completed_sections = state.get("completed_sections", [])
    
    # Create map for quick lookup
    completed_ids = {sec["id"]: sec for sec in completed_sections}
    new_completed = list(completed_sections)
    
    llm = ChatAnthropic(model="claude-3-7-sonnet-20250219", temperature=0.2)
    
    for section_tmpl in LLD_TEMPLATE:
        sec_id = section_tmpl["id"]
        if sec_id in completed_ids:
            continue
            
        attempts = 0
        success = False
        
        # Build context from previously completed sections
        prior_context = "\n\n".join(
            [f"{s['header']}\n{s['content']}" for s in new_completed]
        )
        
        while attempts < 3 and not success:
            attempts += 1
            try:
                sys_msg = SystemMessage(
                    content="You are a senior technical architect writing a Low-Level Design (LLD)."
                )
                human_msg = HumanMessage(
                    content=(
                        f"Issue Context:\n{issue_context}\n\n"
                        f"Previous Sections:\n{prior_context}\n\n"
                        f"Task: {section_tmpl['prompt_instruction']}\n"
                        f"Current Section: {section_tmpl['header']}\n"
                    )
                )
                
                response = llm.invoke([sys_msg, human_msg])
                raw_content = str(response.content)
                
                # Strip hallucinated headers mechanically
                cleaned_content = strip_hallucinated_headers(
                    raw_content, 
                    section_tmpl["header"]
                )
                
                new_completed.append({
                    "id": sec_id,
                    "header": section_tmpl["header"],
                    "content": cleaned_content,
                    "attempts": attempts
                })
                success = True
                print(f"[N_Assembly] Generated section: {sec_id} (Attempt {attempts})")
                
            except Exception as e:
                print(f"[N_Assembly] Error on {sec_id} attempt {attempts}: {e}")
                if attempts >= 3:
                    raise AssemblyError(f"Failed to generate {sec_id} after 3 attempts.") from e

    final_document = assemble_final_document(new_completed)
    
    return {
        "completed_sections": new_completed,
        "final_document": final_document,
        "error_message": ""
    }
```