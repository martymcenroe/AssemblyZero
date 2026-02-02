# File: agentos/workflows/parallel/output_prefixer.py

```python
"""Output stream wrapper for prefixing parallel workflow output."""

import sys
import threading
from io import StringIO
from typing import Optional, TextIO


class OutputPrefixer:
    """Wraps stdout/stderr to add prefixes to each line."""
    
    def __init__(self, prefix: str, stream: Optional[TextIO] = None):
        """Initialize the output prefixer.
        
        Args:
            prefix: Prefix to add to each line (e.g., "[LLD-001]")
            stream: Output stream (defaults to sys.stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self._buffer = StringIO()
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
            # Add text to buffer
            self._buffer.write(text)
            
            # Process complete lines
            buffer_value = self._buffer.getvalue()
            lines = buffer_value.split("\n")
            
            # Keep incomplete line in buffer
            if not buffer_value.endswith("\n"):
                incomplete_line = lines[-1]
                lines = lines[:-1]
                self._buffer = StringIO()
                self._buffer.write(incomplete_line)
            else:
                self._buffer = StringIO()
            
            # Write complete lines with prefix
            for line in lines:
                if line or text.endswith("\n"):  # Preserve blank lines if text ended with newline
                    try:
                        self.stream.write(f"{self.prefix} {line}\n")
                    except (OSError, IOError) as e:
                        # Handle stream errors gracefully
                        print(f"Warning: Failed to write to stream: {e}", file=sys.stderr)
                        return 0
            
            return len(text)
    
    def flush(self) -> None:
        """Flush any buffered output."""
        with self._lock:
            # Write any remaining buffered content
            buffer_value = self._buffer.getvalue()
            if buffer_value:
                try:
                    self.stream.write(f"{self.prefix} {buffer_value}\n")
                except (OSError, IOError) as e:
                    print(f"Warning: Failed to flush stream: {e}", file=sys.stderr)
                self._buffer = StringIO()
            
            # Flush underlying stream
            try:
                self.stream.flush()
            except (OSError, IOError) as e:
                print(f"Warning: Failed to flush underlying stream: {e}", file=sys.stderr)
```