# Extracted Test Plan

## Scenarios

### test_t010
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `assemble_final_document()` | `[{"header": "## 1", "content": "text"}]` | `"## 1\n\ntext\n"`

### test_t020
- Type: unit
- Requirement: 
- Mock needed: True
- Description: `assemble_document_node()` | Mocked 3x failure in `ChatAnthropic` | Raises `AssemblyError`

### test_t030
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `assemble_document_node()` | `completed_sections=[...]` | Prior context included in prompt string

### test_t040
- Type: unit
- Requirement: 
- Mock needed: False
- Description: `strip_hallucinated_headers()` | `content="**2. Target**\nText"`, `header="2. Target"` | `"Text"`

