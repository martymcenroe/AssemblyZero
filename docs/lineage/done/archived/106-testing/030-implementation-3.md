# File: agentos/workflows/parallel/output_prefixer.py

```python
"""Stdout/stderr wrapper with prefix injection for workflow identification."""

import sys
import threading
from typing import Optional, TextIO


class OutputPrefixer:
    """Wraps a stream to add prefixes to each line."""
    
    def __init__(self, prefix: str, stream: Optional[TextIO] = None):
        """Initialize the output prefixer.
        
        Args:
            prefix: Prefix to add to each line (e.g., "[LLD-001]")
            stream: Output stream (default: sys.stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self._buffer = ""
        self._lock = threading.Lock()
        
    def write(self, text: str) -> int:
        """Write text with prefix.
        
        Args:
            text: Text to write
            
        Returns:
            Number of characters written
        """
        if not text:
            return 0
            
        with self._lock:
            self._buffer += text
            
            # Process complete lines
            lines = self._buffer.split('\n')
            
            # Keep incomplete line in buffer
            self._buffer = lines[-1]
            
            # Write complete lines with prefix
            for line in lines[:-1]:
                if line or self._buffer:  # Write non-empty or if buffer had content
                    prefixed = f"{self.prefix} {line}\n"
                    self.stream.write(prefixed)
                    
        return len(text)
        
    def flush(self) -> None:
        """Flush any buffered content."""
        with self._lock:
            if self._buffer:
                prefixed = f"{self.prefix} {self._buffer}\n"
                self.stream.write(prefixed)
                self._buffer = ""
                
            if hasattr(self.stream, 'flush'):
                self.stream.flush()
                
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.flush()
        return False
```