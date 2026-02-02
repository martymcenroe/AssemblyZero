# File: agentos/workflows/parallel/output_prefixer.py

```python
"""Stdout/stderr wrapper with prefix injection for workflow identification."""

import sys
import threading
from typing import Optional, TextIO


class OutputPrefixer:
    """Wraps an output stream and prefixes each line with an identifier.
    
    Thread-safe output prefixing to prevent line interleaving in parallel execution.
    """
    
    def __init__(self, prefix: str, stream: Optional[TextIO] = None):
        """Initialize the output prefixer.
        
        Args:
            prefix: The prefix to add to each line (e.g., "[LLD-001]")
            stream: The output stream to wrap (defaults to sys.stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self._lock = threading.Lock()
        self._buffer = ""
    
    def write(self, text: str) -> None:
        """Write text to the stream with prefix added to each complete line.
        
        Args:
            text: The text to write
        """
        with self._lock:
            self._buffer += text
            
            # Process complete lines
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line:  # Don't prefix empty lines
                    self.stream.write(f"{self.prefix} {line}\n")
                else:
                    self.stream.write("\n")
            
            # Flush after processing
            self.stream.flush()
    
    def flush(self) -> None:
        """Flush any remaining buffered content and the underlying stream."""
        with self._lock:
            if self._buffer:
                self.stream.write(f"{self.prefix} {self._buffer}")
                self._buffer = ""
            self.stream.flush()
```