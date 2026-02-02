# File: agentos/workflows/parallel/output_prefixer.py

```python
"""Output prefixing for parallel workflow identification."""

import sys
from io import StringIO
from typing import Optional


class OutputPrefixer:
    """Wraps stdout/stderr with prefix injection for workflow identification.
    
    This ensures that output from parallel workflows doesn't get interleaved
    and each line is clearly attributed to its source workflow.
    """
    
    def __init__(self, prefix: str, stream=None):
        """Initialize the output prefixer.
        
        Args:
            prefix: The prefix to add to each line (e.g., "[LLD-123]")
            stream: The underlying stream to write to (defaults to sys.stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self.buffer = ""
        
    def write(self, text: str) -> int:
        """Write text with prefix applied to each complete line.
        
        Args:
            text: The text to write
            
        Returns:
            Number of characters written
        """
        # Add to buffer
        self.buffer += text
        
        # Process complete lines
        lines = self.buffer.split("\n")
        
        # Keep incomplete line in buffer
        self.buffer = lines[-1]
        
        # Write complete lines with prefix
        for line in lines[:-1]:
            self.stream.write(f"{self.prefix} {line}\n")
            self.stream.flush()
            
        return len(text)
    
    def flush(self):
        """Flush any remaining buffered content."""
        if self.buffer:
            self.stream.write(f"{self.prefix} {self.buffer}\n")
            self.stream.flush()
            self.buffer = ""
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - flush remaining buffer."""
        self.flush()
        return False
```