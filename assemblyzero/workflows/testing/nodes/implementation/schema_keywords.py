"""The keywords of each JSON Schema draft, and the check that a schema keeps
to its own (#4522).

A real run rewrote a line of a target's normative schema nobody asked it to
touch, as

    "step_minutes": { "integer": { "type": "integer", "minimum": 1 }, "type": "integer", "minimum": 1 },

`"integer"` is no keyword, and a validator ignores a key it does not know, so
every test passed, all fourteen steps passed, and adversarial review passed.
Only a person reading the diff found it.

The keyword sets are closed and authored: each is the list of keywords its
draft's specification defines, written out in full. A draft not listed here is
not checked, and neither is a JSON file that declares no `$schema`.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

_DRAFT_04 = frozenset({
    "id", "$schema", "$ref", "title", "description", "default", "multipleOf",
    "maximum", "exclusiveMaximum", "minimum", "exclusiveMinimum", "maxLength",
    "minLength", "pattern", "additionalItems", "items", "maxItems", "minItems",
    "uniqueItems", "maxProperties", "minProperties", "required",
    "additionalProperties", "definitions", "properties", "patternProperties",
    "dependencies", "enum", "type", "format", "allOf", "anyOf", "oneOf", "not",
})

_DRAFT_06 = (_DRAFT_04 - {"id"}) | frozenset({
    "$id", "examples", "const", "contains", "propertyNames",
})

_DRAFT_07 = _DRAFT_06 | frozenset({
    "$comment", "readOnly", "writeOnly", "contentMediaType", "contentEncoding",
    "if", "then", "else",
})

#: 2019-09 replaced `definitions` and `dependencies`, and its specification
#: keeps them for compatibility, so a schema still carrying them is not
#: refused for it.
_DRAFT_2019_09 = _DRAFT_07 | frozenset({
    "$anchor", "$recursiveRef", "$recursiveAnchor", "$vocabulary", "$defs",
    "dependentSchemas", "dependentRequired", "unevaluatedItems",
    "unevaluatedProperties", "maxContains", "minContains", "deprecated",
    "contentSchema",
})

_DRAFT_2020_12 = (_DRAFT_2019_09 - {"$recursiveRef", "$recursiveAnchor"}) | frozenset({
    "$dynamicRef", "$dynamicAnchor", "prefixItems",
})

#: `$schema` value, normalised, to its draft's keywords.
DRAFTS: dict[str, frozenset[str]] = {
    "json-schema.org/draft-04/schema": _DRAFT_04,
    "json-schema.org/draft-06/schema": _DRAFT_06,
    "json-schema.org/draft-07/schema": _DRAFT_07,
    "json-schema.org/draft/2019-09/schema": _DRAFT_2019_09,
    "json-schema.org/draft/2020-12/schema": _DRAFT_2020_12,
}

#: Keywords whose value is one schema.
_ONE_SCHEMA = frozenset({
    "additionalItems", "additionalProperties", "unevaluatedItems",
    "unevaluatedProperties", "contains", "propertyNames", "if", "then", "else",
    "not", "contentSchema", "items",
})

#: Keywords whose value maps names to schemas.
_NAMED_SCHEMAS = frozenset({
    "properties", "patternProperties", "$defs", "definitions",
    "dependentSchemas", "dependencies",
})

#: Keywords whose value is a list of schemas.
_LISTED_SCHEMAS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems", "items"})


def _draft(schema: dict) -> frozenset[str] | None:
    declared = schema.get("$schema")
    if not isinstance(declared, str):
        return None
    key = declared.split("://", 1)[-1].rstrip("#").rstrip("/")
    return DRAFTS.get(key)


def _pointer(parent: str, key: str) -> str:
    return f"{parent}/{key.replace('~', '~0').replace('/', '~1')}"


def unknown_schema_keywords(schema: Any) -> list[str]:
    """JSON pointers to every key, where a keyword belongs, that is no keyword
    of the schema's declared draft. [] for a document that is not a schema of
    a draft listed here.

    A key under `properties` or `$defs` is a name, never a keyword, and the
    value of `const`, `enum`, `default` or `examples` is data.
    """
    if not isinstance(schema, dict):
        return []
    keywords = _draft(schema)
    if keywords is None:
        return []
    found: list[str] = []

    def walk(node: Any, here: str) -> None:
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{here}/{index}")
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            where = _pointer(here, key)
            if key not in keywords:
                found.append(where)
                continue
            if key in _NAMED_SCHEMAS and isinstance(value, dict):
                for name, sub in value.items():
                    if isinstance(sub, dict):
                        walk(sub, _pointer(where, name))
            elif (key in _LISTED_SCHEMAS and isinstance(value, list)) or (
                key in _ONE_SCHEMA and isinstance(value, dict)
            ):
                walk(value, where)

    walk(schema, "")
    return found


#: What a document says when it declares a draft this module knows.
_DRAFT_MARK = "json-schema.org/draft"


def _parse_failed(exc: ValueError) -> str:
    """The refusal for a reply that declares a draft and is not JSON."""
    return (
        f"The file declares a JSON Schema draft and does not parse as JSON: "
        f"{exc}. A schema is strict JSON (#4522)."
    )


def schema_keyword_problem(
    code: str, base_text: Callable[[], str], spec_text: str, filepath: str = "",
) -> str:
    """The refusal for a key a schema's draft does not have, or "" (#4522).

    Only a document that declares a draft this module knows is judged, so a
    JSON-with-comments file such as a tsconfig is never read here. A key the
    file already had before this write stays, and so does one the spec quotes:
    neither is the reply's to answer for. `base_text` reads the file before
    this write, only when there is something to compare; a base that declares
    a draft and does not parse stops the check, named (ADR 0236).
    """
    if _DRAFT_MARK not in code:
        return ""
    try:
        schema = json.loads(code)
    except ValueError as exc:
        return _parse_failed(exc)
    unknown = unknown_schema_keywords(schema)
    if not unknown:
        return ""
    base = base_text()
    before: set[str] = set()
    if _DRAFT_MARK in base:
        try:
            before = set(unknown_schema_keywords(json.loads(base)))
        except ValueError as exc:
            print(
                f"ERROR [N4] {filepath}: the file before this write declares a "
                f"JSON Schema draft and does not parse ({exc}), so the keys it "
                f"already had cannot be read (#4522)",
                file=sys.stderr, flush=True,
            )
            raise
    new = [
        where for where in unknown
        if where not in before
        and f'"{where.rsplit("/", 1)[-1]}"' not in spec_text
    ]
    if not new:
        return ""
    return (
        f"JSON Schema keys that are no keyword of the file's declared draft, "
        f"where a keyword belongs: {', '.join(new)}. A validator ignores a key "
        f"it does not know, so the schema would accept what it was written to "
        f"refuse. Write only the keywords the change needs (#4522)."
    )
