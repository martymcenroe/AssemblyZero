# Implementation report: #4560

A key checker's one tiny text call, which says whether a Gemini API key can generate at all, asks the switch which model plays the role `key-check`. The switch named no such role, so the checker stopped before any call.

## What changed

- R1, `config/fleet-models.toml`: `[roles]` names `key-check = "gemini-api-lite"`, with a comment saying what plays it.
- R2, the same file: a new entry `[models.gemini-api-lite]`, provider `gemini-api`, id `gemini-3.5-flash-lite`, status `live`.

## Why this model

A model listing on one key, one free call, showed `gemini-3.5-flash-lite` among the text models the key can call. It is a lite model, the cheapest kind of text call, and neither Pro nor Argon, both of which `[policy]` forbids.

## What did not change

No other role and no other model entry. No code reads the new role but the checker that asked for it.
