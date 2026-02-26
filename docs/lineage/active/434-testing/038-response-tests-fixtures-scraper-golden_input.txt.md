The file already exists with the correct content. The previous attempt's failure was not in this file — it was in the scraper's `_USAGE_LINE_PATTERN` regex causing ReDoS on the 15000-char adversarial input in `extract_usage_line`. The `golden_input.txt` file is correct as-is:

```
=== Usage Summary ===
abc123  claude-sonnet-4-20250514  15,234 input  3,421 output  8,000 cache read  1,200 cache write  $0.0847
def456  claude-sonnet-4-20250514  22,100 input  5,000 output  10,000 cache read  2,000 cache write  $0.1200
Total: $0.2047
```
