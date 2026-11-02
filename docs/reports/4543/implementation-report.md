# Implementation report: #4543

Three implementation-spec drafting calls on 2026-11-02 ended with agy's `status: ERROR` and a non-empty `response`. agy's own record of each conversation (`~/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript.jsonl`) shows the cause: the first model turn reached agy's per-turn output token limit at 65,531 or 65,532 output tokens, thinking included. agy then wrote an `ERROR_MESSAGE` step ("Your previous response was cut off because it exceeded the output token limit / Please continue from where you left off, keeping your response shorter / Retries remaining: 3"), made a third model request for the continuation, and ended the call with `ERROR`. The envelope's `usage.output_tokens` is the sum of the two turns in each case. The evidence is posted on the issue.

The transport failed each as `agy status 'ERROR'` followed by 400 characters of the answer, classified it UNKNOWN, and retried.

## What changed

- `assemblyzero/core/gemini_client.py`:
  - `GeminiErrorType.OUTPUT_LIMIT`.
  - `agy_transcript_file`, `transcript_steps` and `output_limit_cuts` find agy's record of a conversation and the turns agy cut in it. The conversation id is parsed as a UUID before it becomes part of a path.
  - `GeminiClient._agy_record` reads the record, directly for a Linux agy and through `wsl.exe --exec cat` for a WSL agy, and raises `AgyRecordUnreadable` with the reason when it cannot.
  - `status_failure` and `failed_status` build the failure for any envelope whose status is not `SUCCESS`. A cut is named, with the cut turn's tokens and the record's path. Otherwise the failure says the record shows no cut, or could not be read and why. The answer is never in the failure text. agy's stderr, dropped before, is kept.
  - `invoke` classifies a cut as `OUTPUT_LIMIT` by its prefix and retries it like any failed attempt, and the call's result carries `OUTPUT_LIMIT` when its last attempt was cut. Any other status failure is classified only by agy's own words: its stderr and the envelope's fields other than the id, usage and answer.
  - Each failure text puts words before numbers. `invoke` keeps the first 100 characters of every attempt, and the stage retry reads "503" or "529" there as a capacity outage.

## Why the answer is not used

In all three records the envelope's `response` opens with the text of the cut turn. That turn stops mid-statement at the limit, and the continuation, told to continue where it left off, began the SEARCH/REPLACE edits again instead. In `7add8e05` it opens with the same SEARCH block as the cut turn. The answer is therefore truncated, and the envelope does not mark where a second attempt begins.

## What did not change

A cut is still retried within the call's budget: the cut depends on how long the model thinks, and the same prompt, sent a third time that morning, was answered at 60,043 output tokens. How much the model thinks is set by the model the fleet switch names for the role, which this change does not touch.

R3 (one model request per drafting call) does not apply. The extra request is agy's continuation, and the same cut-and-continue shape is in agy's records from before #4531 landed. Calls that ran past the limit and still ended `SUCCESS` are tracked in #4546.

## Live calls

One bounded agy call (`gemini-3.8-flash-high`, prompt on stdin, the transport's argv) tried to reproduce a cut so the whole envelope and stderr could be seen. Its first turn was still streaming at the 480 s bound and it was ended with no envelope. The change rests on agy's records of the three calls.
