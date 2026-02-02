# Issue #53: Migrate from google.generativeai to google.genai

## Context

The `google.generativeai` package used in `agentos/core/gemini_client.py` is deprecated:

```
FutureWarning: All support for the `google.generativeai` package has ended.
Please switch to the `google.genai` package as soon as possible.
```

## Scope

- Replace `import google.generativeai as genai` with `google.genai`
- Update `GeminiClient.invoke()` to use new SDK API
- Verify credential rotation logic still works
- Update tests

## References

- Deprecation notice: https://github.com/google-gemini/deprecated-generative-ai-python/blob/main/README.md
- Parent: #50