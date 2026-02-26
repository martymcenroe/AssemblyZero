The file has been written. Here's the complete content:

```
{"session": {"percent_used": null, "resets_at": null}, "weekly_all": {"percent_used": null, "resets_at": null}, "weekly_sonnet": {"percent_used": null, "resets_at": null}}
```

This is the exact output captured from the current `parse_usage_data()` function when given the golden input. Since the golden input contains usage line data (session IDs, tokens, costs) but no `/status` TUI output with "Current session", "Current week (all models)", or "Current week (Sonnet only)" patterns, all parsed fields are `null`. The regression test (T300) strips the `timestamp` field before comparison, so no timestamp is included in the golden output.
