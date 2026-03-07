```markdown
# 999 - Sample LLD for Retry Prompt Testing

## 1. Context & Goal

This is a sample LLD used for testing retry prompt context pruning.
It contains multiple file-specific sections to verify that section extraction
correctly identifies the relevant section for a given target file.

General project context that spans multiple paragraphs to simulate
a realistic LLD preamble with substantial content that contributes
to overall token count.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.

Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore
eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt
in culpa qui officia deserunt mollit anim id est laborum.

## 2. Proposed Changes

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `assemblyzero/services/alpha_service.py` | Add | Alpha service implementation |
| `assemblyzero/services/beta_service.py` | Add | Beta service implementation |
| `assemblyzero/models/gamma_model.py` | Modify | Gamma model updates |
| `assemblyzero/utils/delta_helper.py` | Add | Delta helper utility |
| `assemblyzero/workflows/epsilon_flow.py` | Add | Epsilon workflow node |

## 3. Requirements

All services must implement the standard interface. Alpha service creates
Alpha instances with validated names. Beta service provides connectivity
to downstream systems. Gamma model receives new fields for tracking state.
Delta helper provides shared formatting utilities. Epsilon flow orchestrates
the end-to-end pipeline.

## Section for assemblyzero/services/alpha_service.py

### Function Signatures

```python
def create_alpha(name: str) -> Alpha:
    """Create a new Alpha instance with the given name."""
    ...

def validate_alpha_name(name: str) -> bool:
    """Return True if name meets Alpha naming constraints."""
    ...
```

### Data Structures

```python
class Alpha(TypedDict):
    name: str
    id: int
    created_at: str
```

Alpha service creates Alpha instances with validated names. The service
must enforce naming constraints before persisting. Error handling follows
the standard pattern: return error_message field on failure.

Additional implementation details for Alpha service spanning multiple
paragraphs to simulate realistic section length. The Alpha service
is the primary entry point for creating new tracked entities in the
system. It validates inputs, assigns unique IDs, and timestamps the
creation event.

## Section for assemblyzero/services/beta_service.py

### Function Signatures

```python
def connect_beta(host: str, port: int) -> BetaConnection:
    """Establish connection to a Beta downstream system."""
    ...

def disconnect_beta(conn: BetaConnection) -> None:
    """Gracefully close a Beta connection."""
    ...
```

### Constants

```python
BETA_TIMEOUT_SECONDS: int = 30
BETA_MAX_RETRIES: int = 3
```

Beta service provides connectivity and session management for
downstream Beta systems. It manages connection pooling and
automatic retry with exponential backoff.

## Section for assemblyzero/models/gamma_model.py

### Current State

```python
class GammaModel(TypedDict):
    id: int
    label: str
```

### Proposed Changes

Add `status` and `updated_at` fields to GammaModel:

```python
class GammaModel(TypedDict):
    id: int
    label: str
    status: str       # New: "active", "archived", "pending"
    updated_at: str   # New: ISO 8601 timestamp
```

The gamma model tracks entity lifecycle state. The new fields
enable querying by status and ordering by last update time.

## Section for assemblyzero/utils/delta_helper.py

### Function Signatures

```python
def format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 string."""
    ...

def sanitize_label(label: str) -> str:
    """Remove non-alphanumeric characters from label."""
    ...
```

Delta helper provides shared formatting and sanitization utilities
used across multiple services. It has no external dependencies.

## Section for assemblyzero/workflows/epsilon_flow.py

### Function Signatures

```python
def run_epsilon_flow(state: EpsilonState) -> dict[str, Any]:
    """Execute the Epsilon end-to-end workflow."""
    ...

def validate_epsilon_inputs(state: EpsilonState) -> list[str]:
    """Return list of validation errors, empty if valid."""
    ...
```

### Integration Points

Epsilon flow calls Alpha service, Beta service, and Delta helper
in sequence. It reads GammaModel for state tracking. The flow
is designed to be idempotent and can be safely retried.

## 4. Alternatives Considered

Several alternative approaches were evaluated before settling on
the current design. Option A used a monolithic service but was
rejected due to complexity. Option B used microservices but was
rejected due to operational overhead. The chosen approach balances
modularity with operational simplicity.

## 5. Security Considerations

No sensitive data is processed by these services. All inputs
are validated before use. No external API keys or credentials
are stored in service code. Connections to downstream systems
use TLS.

## Padding Section Alpha

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam
euismod, nisi vel consectetur interdum, nisl nunc egestas nisi,
vitae tincidunt nisl nunc euismod nisi. Donec auctor, nisi vel
consectetur interdum, nisl nunc egestas nisi, vitae tincidunt
nisl nunc euismod nisi.

Sed ut perspiciatis unde omnis iste natus error sit voluptatem
accusantium doloremque laudantium, totam rem aperiam, eaque ipsa
quae ab illo inventore veritatis et quasi architecto beatae vitae
dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas.

Curabitur at lacus ac velit ornare lobortis. Cras dapibus.
Vivamus elementum semper nisi. Aenean vulputate eleifend tellus.
Aenean leo ligula, porttitor eu, consequat vitae, eleifend ac, enim.

## Padding Section Beta

At vero eos et accusamus et iusto odio dignissimos ducimus qui
blanditiis praesentium voluptatum deleniti atque corrupti quos
dolores et quas molestias excepturi sint occaecati cupiditate
non provident, similique sunt in culpa qui officia deserunt
mollitia animi, id est laborum et dolorum fuga.

Et harum quidem rerum facilis est et expedita distinctio. Nam
libero tempore, cum soluta nobis est eligendi optio cumque nihil
impedit quo minus id quod maxime placeat facere possimus, omnis
voluptas assumenda est, omnis dolor repellendus.

## Padding Section Gamma

Temporibus autem quibusdam et aut officiis debitis aut rerum
necessitatibus saepe eveniet ut et voluptates repudiandae sint
et molestiae non recusandae. Itaque earum rerum hic tenetur a
sapiente delectus, ut aut reiciendis voluptatibus maiores alias
consequatur aut perferendis doloribus asperiores repellat.

Additional padding content to push total fixture size to approximately
400 lines, ensuring realistic token counts for tier 1 vs tier 2
comparison testing. This content should not match any target file
path and should be excluded from tier 2 prompts entirely.

## Padding Section Delta

Quis autem vel eum iure reprehenderit qui in ea voluptate velit
esse quam nihil molestiae consequatur, vel illum qui dolorem eum
fugiat quo voluptas nulla pariatur. Ut enim ad minima veniam,
quis nostrum exercitationem ullam corporis suscipit laboriosam.

More padding text to increase fixture size. This section contains
no file paths and should never be matched by the section extractor.
It exists purely to demonstrate that tier 2 pruning successfully
excludes irrelevant content from the retry prompt.

## Padding Section Epsilon

Sed ut perspiciatis unde omnis iste natus error sit voluptatem
accusantium doloremque laudantium, totam rem aperiam, eaque ipsa
quae ab illo inventore veritatis et quasi architecto beatae vitae
dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas
sit aspernatur aut odit aut fugit.

Final padding section. Combined with all preceding sections, the
total fixture should be approximately 400 lines, which when
tokenized produces a significant token count difference between
tier 1 (full LLD) and tier 2 (single section only).
```
