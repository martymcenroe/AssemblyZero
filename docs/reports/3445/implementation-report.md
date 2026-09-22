# Implementation Report — Schema Lists `data-dl/README.md` (#3445)

## The Change

Four lines added to the `files` section of
`docs/standards/0009-structure-schema.json`:

```json
    "data-dl/README.md": {
      "required": true,
      "description": "Explanation of data-dl usage"
    }
```

Nothing else. No code, no behaviour, no other file.

## Why

The schema's own opening line calls it the single source of truth — "when this
schema and 0009-canonical-project-structure.md disagree, the schema is
authoritative." It did not list a file that `tools/new_repo.py` treats as
required in three separate places:

| where | what it does |
|---|---|
| scaffolding | creates it — `Created data-g/README.md and data-dl/README.md` |
| gitignore emission | carries `!data-dl/README.md`, deliberately un-ignoring the one file in an otherwise-ignored directory |
| post-scaffold verification | prints `[FAIL] data-dl/README.md missing` when it is absent |

The tool creates it, protects it from its own ignore rule, and fails without it.
The authoritative schema did not mention it.

## What This Actually Fixes

`audit_project_structure()` checks a project against the schema's `files` list.
Before this change a repo missing `data-dl/README.md` audited as valid.

That README is the reason the drop-zone is self-explaining (#2485). Without it
the directory is a bare gitignored folder with no statement of what belongs in
it, which is precisely the state the audit exists to catch and could not.

## Origin

#3428 landed the `data-dl` substructure and added the *directories* block to the
schema. This *files* entry was written at the same time and did not land with it
— it sat in a local stash until now. Nothing suggests it was considered and
rejected; that commit's message says the substructure was "included in the 0009
structure schema", which was true of the directories half only.

The other half of that stash, a change to `tools/new_repo.py`, is byte-identical
to what is already on main and was therefore dropped rather than re-landed.

## Scaffolder Behaviour Is Unchanged

`create_structure` touches an empty placeholder for every `files` entry and
`main()` then writes the real content. That is the existing pattern for every
templated file in the schema, `CLAUDE.md` included, so this entry joins a path
that already works rather than introducing one.
