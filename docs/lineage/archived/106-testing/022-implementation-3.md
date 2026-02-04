# File: agentos/workflows/parallel/output_prefixer.py

```python
"""Stdout/stderr wrapper with prefix injection for workflow identification."""

import sys
import threading
from typing import Optional, TextIO


class OutputPrefixer:
    """Wraps a stream to add prefixes to each line of output."""
    
    def __init__(self, prefix: str, stream: Optional[TextIO] = None):
        """Initialize the output prefixer.
        
        Args:
            prefix: Prefix to add to each line (e.g., "[LLD-001]")
            stream: Stream to write to (default: stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self._lock = threading.Lock()
        self._buffer = ""
    
    def write(self, text: str):
        """Write text with prefix to stream.
        
        Args:
            text: Text to write
        """
        with self._lock:
            # Add text to buffer
            self._buffer += text
            
            # Process complete lines
            while '\n' in self._buffer:
                line, self._buffer = self._buffer.split('\n', 1)
                if line:  # Skip empty lines
                    self.stream.write(f"{self.prefix} {line}\n")
                else:
                    self.stream.write("\n")
    
    def flush(self):
        """Flush any remaining buffered content."""
        with self._lock:
            if self._buffer:
                self.stream.write(f"{self.prefix} {self._buffer}\n")
                self._buffer = ""
            self.stream.flush()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.flush()
```