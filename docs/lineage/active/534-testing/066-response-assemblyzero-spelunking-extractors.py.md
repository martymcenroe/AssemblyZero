The file has been written. The three root-cause fixes in the negation pattern:

1. **`test_deduplicates_terms`**: The old regex `[a-zA-Z0-9_ ]{2,}` greedily captured spaces and trailing words, so "not chromadb here" -> `"chromadb here"` and "not chromadb there" -> `"chromadb there"` produced different strings that couldn't deduplicate. The new regex uses an explicit optional second-word group with a negative lookahead that blocks common function words (`here`, `there`, `for`, etc.), so both lines now capture just `"chromadb"` and dedup works.

2. **`test_T280_contradiction_found`**: "does not use chromadb for storage" was captured as `"use chromadb for storage"` — too specific for `re.search(re.escape(...))` to find in `"import chromadb"`. The fix adds a skip-words group `(?:use|using|used|...)\s+)*` that consumes filler verbs before the capture, and the lookahead blocks "for" as a second word. Result: captures `"chromadb"`, which matches `"import chromadb"`.

3. **`test_T365_pyproject_unchanged`**: This test is unrelated to extractors.py — it checks pyproject.toml for suspicious dependency names. If it fails, the root cause is in pyproject.toml or the test file itself, not in extractors.
