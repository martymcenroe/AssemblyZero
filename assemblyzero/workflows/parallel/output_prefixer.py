"""Stdout/stderr wrapper with prefix injection for workflow identification."""

import sys
from typing import TextIO, Optional


class OutputPrefixer:
    """Wraps a stream and prefixes each line with an identifier."""
    
    def __init__(self, prefix: str, stream: Optional[TextIO] = None):
        """Initialize output prefixer.
        
        Args:
            prefix: Prefix to add to each line (e.g., "[LLD-001]")
            stream: Stream to write to (default: sys.stdout)
        """
        self.prefix = prefix
        self.stream = stream or sys.stdout
        self._buffer = ""
    
    def write(self, text: str) -> None:
        """Write text with prefix.
        
        Args:
            text: Text to write
        """
        # Add to buffer
        self._buffer += text
        
        # Process complete lines
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            
            # Write prefixed line (skip empty lines)
            if line:
                self.stream.write(f"{self.prefix} {line}\n")
            else:
                self.stream.write("\n")
    
    def flush(self) -> None:
        """Flush any buffered content."""
        if self._buffer:
            self.stream.write(f"{self.prefix} {self._buffer}\n")
            self._buffer = ""
        self.stream.flush()