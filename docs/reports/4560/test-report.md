# Test report: #4560

## Unit

`tests/unit/test_fleet_models.py`, 15 passed. T1 (R1, R2) is `test_t6_the_real_file_defines_every_model_each_role_names`, which reads the real file and fails on a role naming an undefined model.

## The switch's own check

T2 (R3): `python assemblyzero/fleet_models.py --check` on the real file exits 0 and lists `key-check  gemini-api-lite  gemini-api  gemini-3.5-flash-lite  live`.

## Full suite

`tests/unit/`: 14,364 passed, 66 skipped, 7 deselected, 7 xfailed.

## Real calls

None. The model listing that chose the model was made before this change, by the checker in the repository that asked for the role.
