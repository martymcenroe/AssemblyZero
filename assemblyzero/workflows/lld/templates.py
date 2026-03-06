"""LLD template structures for mechanical assembly.

Issue #607: Mechanical Document Assembly Node
"""
from typing import TypedDict

class SectionTemplate(TypedDict):
    id: str
    header: str
    prompt_instruction: str

class CompletedSection(TypedDict):
    id: str
    header: str
    content: str
    attempts: int

LLD_TEMPLATE: list[SectionTemplate] = [
    {
        "id": "context",
        "header": "## 1. Context & Goal",
        "prompt_instruction": "Summarize the objective based on the issue description. Do NOT output the section header, just provide the content."
    },
    {
        "id": "changes",
        "header": "## 2. Proposed Changes",
        "prompt_instruction": "Describe exactly what will be built. Detail file changes and paths. Do NOT output the section header, just provide the content."
    },
    {
        "id": "requirements",
        "header": "## 3. Requirements",
        "prompt_instruction": "List the functional and non-functional requirements. Do NOT output the section header, just provide the content."
    }
]