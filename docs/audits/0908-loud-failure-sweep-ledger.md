# 0908 - Loud-Failure Sweep Ledger (#3581)

**Base commit:** `79e18ad1`
**Scope:** every tracked file under `assemblyzero/` and `tools/` (`git ls-files assemblyzero tools`)
**Files:** 466
**Lines:** 155893
**Standard:** `docs/standards/0034-loud-failure.md` (ADR 0236)

A file is marked read only after every line of it has been read. Each finding is recorded in the Findings section below with file:line, what fails, what the code does now, the property it violates (loud, logged, stops, alerts), and the fix: a PR with its test, or an open issue.

## Files

| File | Lines | Read | Findings |
|---|---|---|---|
| `assemblyzero/__init__.py` | 3 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/__init__.py` | 55 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/alert.py` | 213 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/audit.py` | 346 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 5 |
| `assemblyzero/core/call_recording.py` | 448 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 10 |
| `assemblyzero/core/capacity.py` | 278 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 7 |
| `assemblyzero/core/config.py` | 94 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/errors.py` | 388 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/exit_codes.py` | 30 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/fail_open_audit.py` | 746 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 5 |
| `assemblyzero/core/gate_registry.py` | 1560 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 4 |
| `assemblyzero/core/gemini_client.py` | 737 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 12 |
| `assemblyzero/core/github_writes.py` | 145 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/halt_evidence.py` | 330 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 7 |
| `assemblyzero/core/halt_node.py` | 387 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 6 |
| `assemblyzero/core/interaction_matrix.py` | 378 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/interface_surface.py` | 582 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 12 |
| `assemblyzero/core/llm_provider.py` | 2059 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 31 |
| `assemblyzero/core/loud_failure_check.py` | 256 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/merge_driver.py` | 168 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/model_record.py` | 127 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 4 |
| `assemblyzero/core/no_console.py` | 58 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/operator_notify.py` | 260 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 7 |
| `assemblyzero/core/operator_wait.py` | 70 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 2 |
| `assemblyzero/core/pr_poll.py` | 106 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/preflight.py` | 130 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 5 |
| `assemblyzero/core/projects_root.py` | 49 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/provider_storm.py` | 189 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/recovery_plan.py` | 345 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/resume_contract.py` | 229 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 8 |
| `assemblyzero/core/retry.py` | 115 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 3 |
| `assemblyzero/core/retry_gate.py` | 264 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/retry_mode.py` | 47 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/run_record.py` | 438 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 24 |
| `assemblyzero/core/scripted_provider.py` | 297 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 2 |
| `assemblyzero/core/seats.py` | 810 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 6 |
| `assemblyzero/core/section_utils.py` | 369 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 2 |
| `assemblyzero/core/settlement.py` | 344 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 5 |
| `assemblyzero/core/stage_watchdog.py` | 151 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/state.py` | 86 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/state_persistence.py` | 78 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 2 |
| `assemblyzero/core/tdd_path_tracking.py` | 193 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/text_sanitizer.py` | 81 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/utf8_console.py` | 84 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 1 |
| `assemblyzero/core/validation/__init__.py` | 34 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/core/validation/test_plan_validator.py` | 629 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 5 |
| `assemblyzero/core/verdict_schema.py` | 775 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 5 |
| `assemblyzero/core/workspace_context.py` | 73 | 2026-10-07, two delegated readers, every finding's quoted line verified by script | 0 |
| `assemblyzero/graphs/__init__.py` | 1 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/hooks/__init__.py` | 32 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/hooks/cascade_action.py` | 118 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/hooks/cascade_detector.py` | 202 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/hooks/cascade_patterns.py` | 292 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/hooks/file_write_validator.py` | 182 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/hooks/types.py` | 33 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/metrics/__init__.py` | 71 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/metrics/aggregator.py` | 61 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/metrics/cache.py` | 128 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/metrics/collector.py` | 241 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/metrics/config.py` | 102 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/metrics/formatters.py` | 99 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/metrics/models.py` | 125 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/nodes/__init__.py` | 13 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/nodes/anthropic_provider.py` | 99 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/nodes/check_type_renames.py` | 314 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/nodes/document_assembler.py` | 46 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/nodes/inventory.py` | 104 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/nodes/smoke_test_node.py` | 205 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `assemblyzero/profiles/claude.toml` | 53 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/profiles/gemini.toml` | 11 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/profiles/mock.toml` | 29 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/speedrun/__init__.py` | 1 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/speedrun/answer_key.py` | 397 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/archive.py` | 836 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 18 |
| `assemblyzero/speedrun/box_health.py` | 337 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `assemblyzero/speedrun/convergence.py` | 251 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `assemblyzero/speedrun/emergency_stop.py` | 311 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `assemblyzero/speedrun/factory_report.py` | 1665 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 15 |
| `assemblyzero/speedrun/golden_disasters.py` | 336 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/speedrun/healing.py` | 170 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/speedrun/leavings.py` | 351 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/speedrun/must_resolve.py` | 724 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 18 |
| `assemblyzero/speedrun/preserved.py` | 162 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/prompt_ranking.py` | 172 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/prompt_telemetry.py` | 254 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/replay.py` | 691 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/requirements_status.py` | 123 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/speedrun/restore.py` | 156 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/roll_blockers.py` | 251 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/speedrun/successes.py` | 139 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/timing.py` | 327 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/speedrun/worktrees.py` | 361 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 13 |
| `assemblyzero/spelunking/__init__.py` | 6 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/spelunking/engine.py` | 171 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/spelunking/extractors.py` | 241 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/spelunking/models.py` | 115 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/spelunking/report.py` | 174 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/spelunking/verifiers.py` | 343 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/telemetry/__init__.py` | 51 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/telemetry/__main__.py` | 5 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/telemetry/actor.py` | 62 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/telemetry/cascade_events.py` | 173 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/telemetry/cost.py` | 92 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/telemetry/emitter.py` | 243 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `assemblyzero/telemetry/instrumentation.py` | 133 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/telemetry/llm_call_record.py` | 67 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/telemetry/store.py` | 158 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/telemetry/sync.py` | 21 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/tracing.py` | 39 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/__init__.py` | 55 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/ast_sentinel.py` | 530 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/utils/codebase_reader.py` | 372 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/utils/cost_tracker.py` | 153 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/file_type.py` | 59 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/git.py` | 123 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/github_metrics_client.py` | 262 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/utils/lld_path_enforcer.py` | 221 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/utils/lld_section_extractor.py` | 146 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/lld_verification.py` | 361 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/utils/markdown_inventory.py` | 113 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/utils/metrics_aggregator.py` | 453 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/utils/metrics_config.py` | 207 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/metrics_models.py` | 97 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/pattern_scanner.py` | 493 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/process.py` | 43 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/utils/retry.py` | 265 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/utils/shell.py` | 112 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/utils/speedrun.py` | 337 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/utils/workflow_timeout.py` | 106 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/visual_gate/__init__.py` | 12 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/visual_gate/bundle.py` | 118 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/visual_gate/config.py` | 88 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/visual_gate/floor.py` | 39 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/visual_gate/gate.py` | 567 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/visual_gate/modify.py` | 227 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/visual_gate/server.py` | 288 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `assemblyzero/workflows/__init__.py` | 5 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/checkpoint.py` | 77 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/death/__init__.py` | 27 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/death/age_meter.py` | 191 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/death/constants.py` | 62 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/death/drift_scorer.py` | 274 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/death/hourglass.py` | 363 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `assemblyzero/workflows/death/models.py` | 115 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/death/reconciler.py` | 243 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/death/skill.py` | 138 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/__init__.py` | 44 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/assertion_manifest.py` | 464 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/implementation_spec/atlas.py` | 167 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/base_tree.py` | 99 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/implementation_spec/check_classification.py` | 352 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/criteria_coverage.py` | 302 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/implementation_spec/error_path_coverage.py` | 207 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/implementation_spec/graph.py` | 515 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/implementation_spec/lineage_seed.py` | 210 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/implementation_spec/message_addressability.py` | 168 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/nodes/__init__.py` | 77 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` | 1165 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 23 |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py` | 288 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 15 |
| `assemblyzero/workflows/implementation_spec/nodes/edit_script.py` | 235 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py` | 385 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` | 1486 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/implementation_spec/nodes/human_gate.py` | 207 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py` | 304 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` | 266 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py` | 872 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py` | 4508 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 35 |
| `assemblyzero/workflows/implementation_spec/review_progress.py` | 206 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/implementation_spec/revision_pinning.py` | 596 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/implementation_spec/spec_step_budget.py` | 76 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/state.py` | 283 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/implementation_spec/table_injection.py` | 228 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/janitor/__init__.py` | 8 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/janitor/fixers.py` | 204 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/janitor/graph.py` | 206 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/janitor/probes/__init__.py` | 63 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/janitor/probes/adr_collision.py` | 88 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/janitor/probes/dead_references.py` | 67 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/janitor/probes/drift.py` | 57 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/janitor/probes/harvest.py` | 101 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/janitor/probes/inventory_drift.py` | 75 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/janitor/probes/links.py` | 160 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/janitor/probes/persona_status.py` | 99 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/janitor/probes/readme_claims.py` | 67 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/janitor/probes/stale_timestamps.py` | 109 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/janitor/probes/todo.py` | 128 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/janitor/probes/worktrees.py` | 187 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/janitor/reporter.py` | 296 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `assemblyzero/workflows/janitor/state.py` | 74 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/lld/__init__.py` | 8 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/lld/nodes/assembly_node.py` | 83 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/lld/state.py` | 18 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/lld/templates.py` | 34 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/narration.py` | 187 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/orchestrator/__init__.py` | 40 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/orchestrator/artifacts.py` | 176 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/orchestrator/config.py` | 181 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/orchestrator/graph.py` | 745 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `assemblyzero/workflows/orchestrator/orchestrator.py` | 0 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/orchestrator/resume.py` | 182 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/orchestrator/stages.py` | 2502 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 41 |
| `assemblyzero/workflows/orchestrator/state.py` | 245 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/parallel/__init__.py` | 15 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/parallel/coordinator.py` | 188 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/parallel/credential_coordinator.py` | 127 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/parallel/input_sanitizer.py` | 39 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/parallel/output_prefixer.py` | 45 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/__init__.py` | 41 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/atlas.py` | 229 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/audit.py` | 1221 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 13 |
| `assemblyzero/workflows/requirements/best_of_n.py` | 189 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/requirements/config.py` | 264 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/requirements/contract_fidelity.py` | 1115 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 13 |
| `assemblyzero/workflows/requirements/discrimination_check.py` | 328 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/requirements/feedback_window.py` | 184 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/form_check.py` | 844 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/requirements/form_gate.py` | 287 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/requirements/git_operations.py` | 411 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/requirements/graph.py` | 687 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/requirements/nodes/__init__.py` | 56 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py` | 644 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py` | 828 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 11 |
| `assemblyzero/workflows/requirements/nodes/finalize.py` | 805 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 20 |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py` | 1206 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 11 |
| `assemblyzero/workflows/requirements/nodes/human_gate.py` | 236 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/requirements/nodes/lld_revision.py` | 123 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/nodes/load_input.py` | 363 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/requirements/nodes/ponder.py` | 108 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/requirements/nodes/ponder_rules.py` | 359 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/nodes/review.py` | 917 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | 1828 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 13 |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py` | 257 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/requirements/ownership_check.py` | 673 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/requirements/parsers/__init__.py` | 20 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/parsers/draft_updater.py` | 315 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/requirements/parsers/verdict_parser.py` | 295 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/requirements/precheck.py` | 374 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `assemblyzero/workflows/requirements/scope_coverage.py` | 504 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/requirements/state.py` | 485 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/requirements/step_budget.py` | 164 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/requirements/table_injection.py` | 222 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/requirements/verdict_summarizer.py` | 225 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/scout/__init__.py` | 25 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/scout/budget.py` | 76 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/scout/graph.py` | 76 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/scout/instrumentation.py` | 126 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/scout/nodes.py` | 332 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 13 |
| `assemblyzero/workflows/scout/prompts.py` | 94 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/scout/security.py` | 132 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/scout/templates.py` | 139 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/telemetry/__init__.py` | 16 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/telemetry/hallucination_log.py` | 124 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/__init__.py` | 24 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/adversarial_gemini.py` | 406 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/adversarial_prompts.py` | 180 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/adversarial_state.py` | 72 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/atlas.py` | 299 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/audit.py` | 331 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/checkpoints.py` | 256 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 14 |
| `assemblyzero/workflows/testing/circuit_breaker.py` | 139 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/completeness/__init__.py` | 31 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py` | 883 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `assemblyzero/workflows/testing/completeness/report_generator.py` | 444 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/testing/coverage_report.py` | 193 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/exit_code_router.py` | 106 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/testing/framework_detector.py` | 332 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/graph.py` | 793 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 16 |
| `assemblyzero/workflows/testing/knowledge/__init__.py` | 10 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/knowledge/adversarial_patterns.py` | 53 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/knowledge/patterns.py` | 192 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/testing/knowledge/types.yaml` | 241 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/nodes/__init__.py` | 68 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py` | 468 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 11 |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py` | 281 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py` | 180 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/testing/nodes/augment_tests.py` | 799 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 26 |
| `assemblyzero/workflows/testing/nodes/cleanup.py` | 157 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py` | 538 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py` | 439 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/testing/nodes/document.py` | 377 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py` | 464 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `assemblyzero/workflows/testing/nodes/finalize.py` | 314 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/testing/nodes/implement_code.py` | 106 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/nodes/implementation/__init__.py` | 129 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/nodes/implementation/claude_client.py` | 271 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/nodes/implementation/context.py` | 188 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/testing/nodes/implementation/deprecated.py` | 251 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/testing/nodes/implementation/edit_script_fix.py` | 527 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `assemblyzero/workflows/testing/nodes/implementation/import_validator.py` | 383 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py` | 269 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py` | 1269 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 26 |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py` | 449 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/testing/nodes/implementation/prompts.py` | 392 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/testing/nodes/implementation/routing.py` | 97 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/nodes/load_lld.py` | 1412 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `assemblyzero/workflows/testing/nodes/mechanical_hooks.py` | 110 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py` | 775 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `assemblyzero/workflows/testing/nodes/revise_test_plan.py` | 324 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py` | 1265 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 11 |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py` | 1047 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/testing/nodes/verify_phases.py` | 3918 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 33 |
| `assemblyzero/workflows/testing/path_validator.py` | 180 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/testing/runner_registry.py` | 150 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `assemblyzero/workflows/testing/runners/__init__.py` | 16 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/runners/base_runner.py` | 137 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `assemblyzero/workflows/testing/runners/jest_runner.py` | 206 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `assemblyzero/workflows/testing/runners/playwright_runner.py` | 194 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/testing/runners/pytest_runner.py` | 124 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/testing/state.py` | 374 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/step_budget.py` | 95 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/symbol_validator.py` | 188 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/templates/__init__.py` | 30 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/templates/cp_docs.py` | 295 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `assemblyzero/workflows/testing/templates/lessons.py` | 304 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `assemblyzero/workflows/testing/templates/runbook.py` | 259 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `assemblyzero/workflows/testing/templates/wiki_page.py` | 207 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/_gate.py` | 103 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/_gh_retry.py` | 132 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/_npm_manifest.py` | 108 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/_pat_session.py` | 445 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/answer_key_audit.py` | 66 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/append_session_log.py` | 194 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/archive_worktree_lineage.py` | 265 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/assemblyzero-generate.py` | 249 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/assemblyzero-harvest.py` | 514 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `tools/assemblyzero-permissions.py` | 958 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `tools/assemblyzero_config.py` | 342 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/audit_cerberus_health.py` | 274 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/audit_default_arg_patches.py` | 321 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/audit_deferred_scope.py` | 877 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/audit_fail_open.py` | 350 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/audit_fleet_auto_merge_readiness.py` | 290 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/audit_fleet_branch_protection.py` | 308 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 11 |
| `tools/audit_fleet_rulesets.py` | 360 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/audit_fully_landed.py` | 119 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/audit_gitignore_drift.py` | 233 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/audit_halt_sites.py` | 298 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/audit_loud_failure.py` | 99 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/audit_schedule_check.py` | 361 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `tools/audit_tracked_log_writers.py` | 252 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/auth-preflight.sh` | 20 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/backfill_assemblyzero_flag.py` | 396 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 22 |
| `tools/backfill_canonical_labels.py` | 237 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/backfill_issue_audit.py` | 844 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/backfill_telemetry.py` | 228 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `tools/banned_command_sweep.py` | 176 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/batch-workflow.sh` | 405 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/batch_cleanup_quality_hooks.py` | 280 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/batch_cleanup_security_hooks.py` | 319 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/batch_deploy_hooks.py` | 358 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/campaign_timing_dashboard.py` | 229 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/cerberus_worker_key.py` | 85 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/check_requirements.py` | 113 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/check_requirements_form.py` | 102 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/claude-usage-scraper.py` | 418 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/claude_spend_lock.py` | 293 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/claude_usage_compute.py` | 398 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/clean_transcript.py` | 364 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/collect-cross-project-metrics.py` | 194 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/collect_cross_project_metrics.py` | 351 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/compare_profiles.py` | 283 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/consolidate_logs.py` | 182 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/dependabot_morning_status.py` | 181 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/dependabot_review.py` | 2419 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 41 |
| `tools/deploy_auto_reviewer_fleet.py` | 416 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 14 |
| `tools/deploy_auto_reviewer_poll_fix.py` | 363 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/deploy_auto_reviewer_workflow.py` | 643 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 23 |
| `tools/deploy_boostgauge_landing_workflow.py` | 320 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `tools/deploy_boostgauge_release_yml.py` | 306 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/deploy_cerberus_secrets.py` | 419 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/derive_stage_nominals.py` | 149 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/enable_dependabot.py` | 310 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `tools/enable_wikis.py` | 124 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/factory_report.py` | 121 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/fix_az_workflow_concurrency.py` | 111 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/fix_branch_protections.py` | 378 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/fix_gemini_ack.py` | 239 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/fix_requires_python.py` | 256 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `tools/fixtures/README.md` | 70 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/fixtures/sample_comments.json` | 42 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/fixtures/sample_issues.json` | 44 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/fleet_delete_pr_sentinel.py` | 445 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/fleet_remove_claude_key.py` | 328 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/fleet_set_delete_branch_on_merge.py` | 268 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/fleet_set_permission_mode.py` | 409 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/generate_dependabot_yml.py` | 490 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/github_protection_audit.py` | 1407 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 19 |
| `tools/golden_disasters.py` | 92 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/harvest_reviewer_idioms.py` | 117 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/heal_report.py` | 171 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/hermes_add_ci_workflow.py` | 345 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `tools/hermes_pin_workflow_shas.py` | 413 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/land_1104_auto_reviewer_fix.py` | 297 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 12 |
| `tools/land_2283_ci_tiers.py` | 448 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/land_aletheia_775.py` | 230 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/land_aletheia_ci_oidc.py` | 269 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 16 |
| `tools/land_aletheia_ci_pipestatus.py` | 359 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/land_career_lint_workflow.py` | 191 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/land_career_test_ci.py` | 249 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/land_dependabot_skip_1251.py` | 314 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/land_polybolos_ci_workflow.py` | 322 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/land_staged_workflow.py` | 491 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/land_windows_ci_job.py` | 276 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/lint_per_repo_claude_md.py` | 670 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/merge_aletheia_603_audit_gate.py` | 375 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/merge_sentinel_permissions_prs.py` | 334 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/migrate_lineage_flat_to_run_scoped.py` | 139 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/mine_quality_patterns.py` | 374 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/mine_verdict_patterns.py` | 411 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/model_scorecard.py` | 309 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `tools/modernize_dependencies.py` | 321 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/new_repo.py` | 4004 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 68 |
| `tools/orchestrate.py` | 421 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/pat_smoke_test.py` | 100 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/prompt_failure_report.py` | 63 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/prompt_revision_rank.py` | 80 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/prove_idle_timeout.py` | 135 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/push_workflow_fixes.py` | 475 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 15 |
| `tools/readonly_attribute_audit.py` | 230 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 9 |
| `tools/remediate_fleet_branch_protection.py` | 260 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/remediate_patent_general_protection.py` | 230 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/replay_run.py` | 402 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/repo_drift_check.py` | 332 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/require_status_check.py` | 215 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/run_audit.py` | 852 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 19 |
| `tools/run_implement_from_lld.py` | 1489 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 23 |
| `tools/run_implementation_spec_workflow.py` | 750 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 10 |
| `tools/run_janitor_workflow.py` | 177 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/run_requirements_workflow.py` | 1698 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 36 |
| `tools/run_scout_workflow.py` | 256 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/secret-inventory.sh` | 169 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/send_test_alert.py` | 39 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/sentinel_migrate.py` | 275 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 8 |
| `tools/speedrun_archive.py` | 212 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/speedrun_clean_check.py` | 409 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 11 |
| `tools/speedrun_new_attempt.py` | 379 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/speedrun_overlay.py` | 141 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/speedrun_reset.py` | 859 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 32 |
| `tools/speedrun_roll.py` | 4202 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 85 |
| `tools/speedrun_summarize.py` | 131 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/stash_audit.py` | 246 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/test-gate.py` | 223 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 6 |
| `tools/test_gate/__init__.py` | 6 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/test_gate/auditor.py` | 193 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/test_gate/models.py` | 48 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/test_gate/parser.py` | 162 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/test_governance_system.py` | 996 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 32 |
| `tools/transcript_filters.py` | 376 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/update-doc-refs.py` | 303 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/update_clio_repo_metadata.py` | 176 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/upgrade_auto_reviewer_caller.py` | 235 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/upgrade_boostgauge_auto_reviewer.py` | 386 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/upgrade_comp_environ_auto_reviewer.py` | 434 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 7 |
| `tools/validate_skill.py` | 163 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/verdict-analyzer.py` | 258 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/verdict_analyzer/__init__.py` | 68 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/verdict_analyzer/database.py` | 353 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 2 |
| `tools/verdict_analyzer/parser.py` | 225 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/verdict_analyzer/patterns.py` | 89 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 1 |
| `tools/verdict_analyzer/scanner.py` | 197 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/verdict_analyzer/template_updater.py` | 178 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/verify_encrypted_secret.py` | 189 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 0 |
| `tools/verify_gpg_agent_ttl.py` | 163 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |
| `tools/view_audit.py` | 240 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 5 |
| `tools/wait_for_pr.py` | 128 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 3 |
| `tools/widen_boostgauge_auto_reviewer_trigger.py` | 187 | 2026-10-07, one delegated reader per file, every finding's quoted line verified by script | 4 |

## Findings

| Site | What fails | What the code does now | Violates | Fix |
|---|---|---|---|---|
| `assemblyzero/core/llm_provider.py:291` | .env read | None | loud, logged, alerts | raise |
| `assemblyzero/core/llm_provider.py:412` | idle timeout not int | default | loud, stops, alerts | raise |
| `assemblyzero/core/llm_provider.py:418` | idle timeout <=0 | default | loud, stops, alerts | raise |
| `assemblyzero/core/llm_provider.py:487` | stdin write | pass | all | record |
| `assemblyzero/core/llm_provider.py:505` | bad stream line | continue | loud, logged, stops | count |
| `assemblyzero/core/llm_provider.py:510` | stdout read | pass | all | record |
| `assemblyzero/core/llm_provider.py:517` | stderr read | pass | loud, logged | record |
| `assemblyzero/core/llm_provider.py:553` | reader alive | unchecked | stops, logged | check |
| `assemblyzero/core/llm_provider.py:723` | probe no cli | False | loud, logged, alerts | raise |
| `assemblyzero/core/llm_provider.py:757` | probe spawn | False | loud, logged, alerts | raise |
| `assemblyzero/core/llm_provider.py:765` | probe timeout | False | compliant | none |
| `assemblyzero/core/llm_provider.py:769` | drain | pass | loud, logged | ERROR |
| `assemblyzero/core/llm_provider.py:772` | communicate | False | loud, logged, alerts | raise |
| `assemblyzero/core/llm_provider.py:826` | no cli | failed result | loud, logged, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:953` | timeout | failed result | loud, alerts | stderr |
| `assemblyzero/core/llm_provider.py:1016` | nonzero | failed result | loud, alerts | stderr |
| `assemblyzero/core/llm_provider.py:1029` | capacity | stdout | loud, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1085` | odd json | success | loud, stops, alerts | fail |
| `assemblyzero/core/llm_provider.py:1103` | empty result | success | all | fail |
| `assemblyzero/core/llm_provider.py:1113` | non-json | success | all | fail |
| `assemblyzero/core/llm_provider.py:1145` | invoke | failed result | loud, logged, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1248` | unpriced | 0.0 | loud, logged | raise |
| `assemblyzero/core/llm_provider.py:1372` | no key | failed result | loud, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1387` | api exc | failed result | loud, logged, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1555` | breaker | stdout | loud, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1596` | primary | fallback | loud, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1609` | fallback | stdout | loud, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1617` | both | stdout | loud, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:1729` | contract | False | logged | direct |
| `assemblyzero/core/llm_provider.py:1756` | gemini invoke | failed result | loud, logged, alerts | ERROR |
| `assemblyzero/core/llm_provider.py:2009` | recording wrap | bare | all | raise |
| `assemblyzero/core/llm_provider.py:2010` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/verdict_schema.py:196` | missing rationale | "" | loud, logged, stops | reject |
| `assemblyzero/core/verdict_schema.py:199` | parse | None | compliant | none |
| `assemblyzero/core/verdict_schema.py:208` | missing rationale | "" | loud, logged, stops | reject |
| `assemblyzero/core/verdict_schema.py:211` | parse | None | compliant | none |
| `assemblyzero/core/verdict_schema.py:511` | verdict count | None | compliant | none |
| `assemblyzero/core/verdict_schema.py:651` | empty doc | False | all | raise |
| `assemblyzero/core/verdict_schema.py:703` | missing verdict | False | logged | raise |
| `assemblyzero/core/verdict_schema.py:716` | structured parse | heuristic | loud, logged | raise |
| `assemblyzero/core/gemini_client.py:174` | windows agy | None | logged | ERROR |
| `assemblyzero/core/gemini_client.py:199` | wsl.exe | None cached | loud, logged, alerts | raise |
| `assemblyzero/core/gemini_client.py:200` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/gemini_client.py:208` | printenv | None | logged | ERROR |
| `assemblyzero/core/gemini_client.py:454` | no agy | retried | stops | fail fast |
| `assemblyzero/core/gemini_client.py:514` | drain | pass | loud, logged | ERROR |
| `assemblyzero/core/gemini_client.py:520` | spawn | retried | loud, alerts | ERROR |
| `assemblyzero/core/gemini_client.py:598` | attempt | retry, no log | loud, alerts | ERROR |
| `assemblyzero/core/gemini_client.py:601` | programming error | failed result | all | re-raise |
| `assemblyzero/core/gemini_client.py:660` | retry | no log | loud | log |
| `assemblyzero/core/gemini_client.py:671` | exhausted | no log | loud, alerts | ERROR |
| `assemblyzero/core/gemini_client.py:730` | metadata | unknown | logged | raise |
| `assemblyzero/core/call_recording.py:153` | write | False | all | raise |
| `assemblyzero/core/call_recording.py:154` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/call_recording.py:179` | corrupt line | count | loud, logged | ERROR |
| `assemblyzero/core/call_recording.py:180` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/call_recording.py:187` | bad record | count | loud, logged | ERROR |
| `assemblyzero/core/call_recording.py:251` | write | discarded | loud, stops, alerts | check |
| `assemblyzero/core/call_recording.py:284` | unreadable count | discarded | logged, stops | raise |
| `assemblyzero/core/call_recording.py:353` | replay overrun | failed result | loud, alerts | ERROR |
| `assemblyzero/core/call_recording.py:372` | divergence | failed result | loud, alerts | ERROR |
| `assemblyzero/core/call_recording.py:388` | missing success | True | logged, stops | refuse |
| `assemblyzero/core/errors.py:365` | retry-after | None | logged | ERROR |
| `assemblyzero/core/recovery_plan.py:72` | unknown workflow | string | compliant | none |
| `assemblyzero/core/recovery_plan.py:144` | halt summary | stdout | loud | FIXED in #3581 core batch 1 (#3724): stderr |
| `assemblyzero/core/settlement.py:111` | hash | None | loud, logged, alerts | ERROR |
| `assemblyzero/core/settlement.py:112` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/settlement.py:176` | outside root | abs key | logged | raise |
| `assemblyzero/core/settlement.py:177` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/settlement.py:259` | hash | None | all | raise |
| `assemblyzero/core/capacity.py:74` | not object | {} | all | raise |
| `assemblyzero/core/capacity.py:75` | read | {} | all | raise |
| `assemblyzero/core/capacity.py:89` | write | pass | all | raise |
| `assemblyzero/core/capacity.py:113` | reset ts | fall through | compliant | none |
| `assemblyzero/core/capacity.py:121` | iso ts | fall through | compliant | none |
| `assemblyzero/core/capacity.py:212` | stored ts | None | all | raise |
| `assemblyzero/core/capacity.py:223` | no ts | available | logged, stops | raise |
| `assemblyzero/core/capacity.py:237` | unchecked | available | logged, stops | unchecked |
| `assemblyzero/core/capacity.py:264` | unknown provider | available | loud, logged, stops | raise |
| `assemblyzero/core/operator_notify.py:183` | non-windows | reason | loud, alerts | ERROR |
| `assemblyzero/core/operator_notify.py:199` | toast spawn | reason | loud, logged, alerts | raise |
| `assemblyzero/core/operator_notify.py:200` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/operator_notify.py:205` | toast exit | reason | loud, alerts | raise |
| `assemblyzero/core/operator_notify.py:231` | no sender | reason | loud, stops, alerts | raise |
| `assemblyzero/core/operator_notify.py:255` | ses | reason | loud, logged, alerts | raise |
| `assemblyzero/core/operator_notify.py:256` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/alert.py:78` | alert.json | raise | compliant | none |
| `assemblyzero/core/alert.py:164` | email fails | toast skipped | alerts | FIXED in #3581 core batch 1 (#3724): attempt toast |
| `assemblyzero/core/alert.py:170` | delivery | raise | compliant | none |
| `assemblyzero/core/alert.py:190` | ses | raise | compliant | none |
| `assemblyzero/core/alert.py:212` | log | raise | compliant | none |
| `assemblyzero/core/provider_storm.py:147` | probe raises | storm | loud, logged, alerts | ERROR |
| `assemblyzero/core/stage_watchdog.py:139` | stalled | stdout | loud, alerts | ERROR + alert |
| `assemblyzero/core/preflight.py:64` | unknown alias | default | logged, stops | raise |
| `assemblyzero/core/preflight.py:83` | no agy | failed | loud, alerts | ERROR |
| `assemblyzero/core/preflight.py:94` | probe | failed | loud, alerts | ERROR |
| `assemblyzero/core/preflight.py:95` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/preflight.py:102` | probe empty | failed | loud, alerts | ERROR |
| `assemblyzero/core/retry.py:66` | non-retryable | stdout, raise | loud | stderr |
| `assemblyzero/core/retry.py:73` | timeout | stdout, raise | loud | stderr |
| `assemblyzero/core/retry.py:95` | exhausted | raise | loud | log |
| `assemblyzero/core/utf8_console.py:76` | tier 1 | tier 2 | compliant | none |
| `assemblyzero/core/utf8_console.py:83` | both tiers | False | loud, logged | ERROR |
| `assemblyzero/core/state_persistence.py:42` | serialize | str() | loud, logged, stops | raise |
| `assemblyzero/core/state_persistence.py:77` | snapshot | None | all | raise |
| `assemblyzero/core/operator_wait.py:41` | isatty | False | logged | ERROR |
| `assemblyzero/core/operator_wait.py:42` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/retry_mode.py:40` | malformed | REGENERATED | compliant | none |
| `assemblyzero/core/gate_registry.py:1240` | scan_halt_sites parse failure | files_unparseable, continue | loud, logged, stops, alerts | raise |
| `assemblyzero/core/gate_registry.py:1241` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/gate_registry.py:1453` | malformed site key | continue | all | raise |
| `assemblyzero/core/gate_registry.py:1454` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/seats.py:128` | /proc/version | None | all | platform check, raise |
| `assemblyzero/core/seats.py:149` | is_dir | True | loud, logged, alerts | log ERROR |
| `assemblyzero/core/seats.py:173` | lock read | True | loud, logged, alerts | log ERROR |
| `assemblyzero/core/seats.py:191` | until parse | None | loud, logged, alerts | log ERROR |
| `assemblyzero/core/seats.py:564` | mock override | dropped | compliant | none |
| `assemblyzero/core/seats.py:776` | active_profile | DEFAULT_PROFILE | all | raise |
| `assemblyzero/core/seats.py:777` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/fail_open_audit.py:595` | unparse | label | all | raise |
| `assemblyzero/core/fail_open_audit.py:596` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/fail_open_audit.py:699` | read/parse | files_unparseable, [] | all | raise |
| `assemblyzero/core/fail_open_audit.py:700` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/fail_open_audit.py:739` | missing subdir | continue | all | raise |
| `assemblyzero/core/validation/test_plan_validator.py:136` | section 3 missing | WARNING, [] | loud, logged | ERROR |
| `assemblyzero/core/validation/test_plan_validator.py:225` | section 10 missing | WARNING, [] | loud, logged | ERROR + violation |
| `assemblyzero/core/validation/test_plan_validator.py:237` | no table | zero scenarios | loud, logged | ERROR |
| `assemblyzero/core/validation/test_plan_validator.py:248` | malformed row | dropped | loud, logged, stops | violation |
| `assemblyzero/core/validation/test_plan_validator.py:262` | bad id | dropped | loud, logged, stops | violation |
| `assemblyzero/core/interface_surface.py:107` | parse target | first 50 lines | all | raise |
| `assemblyzero/core/interface_surface.py:267` | walk | WARNING, [] | loud, stops, alerts | raise |
| `assemblyzero/core/interface_surface.py:295` | out-of-repo token | skip | compliant | none |
| `assemblyzero/core/interface_surface.py:319` | import expansion | [] | all | raise |
| `assemblyzero/core/interface_surface.py:394` | read file | WARNING, drop | loud, stops, alerts | raise |
| `assemblyzero/core/interface_surface.py:402` | budget | drop | loud, logged | name dropped |
| `assemblyzero/core/interface_surface.py:408` | not under root | bare name | loud, logged | raise |
| `assemblyzero/core/interface_surface.py:445` | root not dir | {} | all | raise |
| `assemblyzero/core/interface_surface.py:449` | empty | {} | loud, logged | log count |
| `assemblyzero/core/interface_surface.py:472` | resolve | continue | all | raise |
| `assemblyzero/core/interface_surface.py:492` | extraction | WARNING, {} | all | raise |
| `assemblyzero/core/interface_surface.py:518` | root not dir | {} | all | raise |
| `assemblyzero/core/interface_surface.py:552` | revision extraction | WARNING, {} | all | raise |
| `assemblyzero/core/run_record.py:77` | tee write | pass | all | ERROR |
| `assemblyzero/core/run_record.py:78` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:87` | flush | pass | all | ERROR |
| `assemblyzero/core/run_record.py:88` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:103` | git | (False, reason) | loud, alerts | ERROR |
| `assemblyzero/core/run_record.py:104` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:107` | git nonzero | (False, stderr) | loud, alerts | ERROR |
| `assemblyzero/core/run_record.py:134` | worktree list | unknown | loud, alerts | ERROR |
| `assemblyzero/core/run_record.py:144` | branch list | unknown | loud, alerts | ERROR |
| `assemblyzero/core/run_record.py:155` | remote refs | unknown | loud, alerts | ERROR |
| `assemblyzero/core/run_record.py:165` | status | unavailable | loud, alerts | ERROR |
| `assemblyzero/core/run_record.py:271` | open run log | console-only | loud, stops, alerts | ERROR + alert |
| `assemblyzero/core/run_record.py:272` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:283` | head | unknown | loud, logged, alerts | ERROR |
| `assemblyzero/core/run_record.py:318` | profile header | warning | loud, stops, alerts | raise |
| `assemblyzero/core/run_record.py:319` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:378` | console print | pass | loud, logged, alerts | ERROR |
| `assemblyzero/core/run_record.py:379` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:410` | events append | warning | loud, alerts | ERROR + alert |
| `assemblyzero/core/run_record.py:411` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:420` | stderr warning | pass | all | alert |
| `assemblyzero/core/run_record.py:421` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/run_record.py:434` | close | pass | loud, logged, alerts | ERROR |
| `assemblyzero/core/run_record.py:435` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/halt_node.py:229` | halt | no alert | loud, alerts | FIXED in #3581 core batch 1 (#3724): alert_operator |
| `assemblyzero/core/halt_node.py:291` | audit_dir missing | skip | loud, logged | FIXED in #3581 core batch 1 (#3724): ERROR |
| `assemblyzero/core/halt_node.py:297` | resume contract | WARN stdout | loud, logged, alerts | FIXED in #3581 core batch 1 (#3724): ERROR |
| `assemblyzero/core/halt_node.py:298` | tag | records the fall-through as a decision | all | FIXED in #3581 core batch 1 (#3724): remove |
| `assemblyzero/core/halt_node.py:344` | evidence | WARN stdout | loud, logged, alerts | FIXED in #3581 core batch 1 (#3724): ERROR |
| `assemblyzero/core/halt_node.py:345` | tag | records the fall-through as a decision | all | FIXED in #3581 core batch 1 (#3724): remove |
| `assemblyzero/core/section_utils.py:146` | import stripper | unstripped | all | propagate |
| `assemblyzero/core/section_utils.py:147` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/section_utils.py:288` | unmapped feedback | "" | compliant | none |
| `assemblyzero/core/audit.py:126` | git missing | raise | compliant | none |
| `assemblyzero/core/audit.py:130` | timeout | raise | logged | from e |
| `assemblyzero/core/audit.py:238` | bad history line | skip | all | raise |
| `assemblyzero/core/audit.py:242` | history read | [] | all | raise |
| `assemblyzero/core/audit.py:267` | bad shard line | skip | all | raise |
| `assemblyzero/core/audit.py:270` | shard read | partial | all | raise |
| `assemblyzero/core/halt_evidence.py:43` | hash artifact | None | loud, logged, alerts | ERROR |
| `assemblyzero/core/halt_evidence.py:44` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/halt_evidence.py:85` | corrupt record | drop | loud, logged, alerts | ERROR |
| `assemblyzero/core/halt_evidence.py:86` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/halt_evidence.py:91` | read log | [] | loud, logged, alerts | ERROR |
| `assemblyzero/core/halt_evidence.py:92` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/halt_evidence.py:120` | audit_dir missing | empty | loud, logged | ERROR |
| `assemblyzero/core/scripted_provider.py:136` | no response | "" success | all | raise |
| `assemblyzero/core/scripted_provider.py:241` | unmatched | failed result | loud, alerts | ERROR |
| `assemblyzero/core/scripted_provider.py:260` | scripted fail | failure | compliant | none |
| `assemblyzero/core/retry_gate.py:209` | unknown class | full budget | loud, logged, stops | raise |
| `assemblyzero/core/loud_failure_check.py:173` | source | raises | compliant | none |
| `assemblyzero/core/resume_contract.py:53` | hash | None | loud, logged | ERROR |
| `assemblyzero/core/resume_contract.py:54` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/resume_contract.py:126` | contract read | None, resume unverified | all | raise |
| `assemblyzero/core/resume_contract.py:127` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/resume_contract.py:148` | unhashable | missing | logged | real cause |
| `assemblyzero/core/resume_contract.py:196` | world changed | print, False | loud, alerts | ERROR + alert |
| `assemblyzero/core/resume_contract.py:223` | delete contract | WARN stdout | loud, alerts | ERROR |
| `assemblyzero/core/resume_contract.py:224` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/tdd_path_tracking.py:124` | delete scaffold | WARNING | loud, stops, alerts | raise |
| `assemblyzero/core/merge_driver.py:69` | no file | reason | compliant | none |
| `assemblyzero/core/merge_driver.py:160` | start | raise | compliant | none |
| `assemblyzero/core/merge_driver.py:163` | missing PR/SHA | success | loud, logged, stops | raise |
| `assemblyzero/core/merge_driver.py:164` | nonzero | raise | compliant | none |
| `assemblyzero/core/github_writes.py:145` | replay | inert | compliant | none |
| `assemblyzero/core/model_record.py:70` | check_spec | "" | loud, logged, alerts | raise |
| `assemblyzero/core/model_record.py:71` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/model_record.py:118` | no record | False | compliant | none |
| `assemblyzero/core/model_record.py:123` | sink write | False | loud, logged, alerts | ERROR + alert |
| `assemblyzero/core/model_record.py:124` | tag | records the fall-through as a decision | all | remove |
| `assemblyzero/core/pr_poll.py:86` | error payload | wait | loud, logged, stops | raise |
| `assemblyzero/core/text_sanitizer.py:72` | non-str | unstripped | loud, logged, stops | raise |
| `assemblyzero/core/workspace_context.py:38` | missing path | raise | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:594` | the directory probe raises OSError | False, falls back to a directory target; coverage may measure the wrong scope | loud, logged, stops, alerts | ERROR and re-raise so N5 halts |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:767` | pytest-cov not installed | WARN, runs without --cov | loud, logged, stops, alerts | raise or route to HALT: the coverage gate cannot run |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:791` | pytest run times out | synthetic -1 result read as test errors, loops to N4 | loud, logged, stops, alerts | ERROR with command and timeout; halt |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:798` | poetry or pytest not on PATH | synthetic -1 result treated as failure | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:841` | restoring a best-iteration file fails | prints non-fatal, partly restored worktree | loud, logged, alerts | ERROR and alert naming the files |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1009` | red marker cannot be written | returns silently | loud, logged, stops, alerts | raise or ERROR and alert |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1022` | writing the red marker raises | WARNING, continues, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1036` | reading the red marker fails | None silently, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1241` | a test file cannot be read for the hollow check | skips it: could not check reads as not hollow | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1271` | N3 has no test files | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1276` | a listed test file is missing | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1293` | audit dir missing | skips red-phase.txt silently | loud, logged, stops, alerts | raise or route to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1423` | pytest interrupted in red phase | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1605` | tests pass before implementation | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1697` | unknown framework resolves to None | runs the pytest path silently | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1729` | no framework config ran in the red phase | success with no red phase run | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1798` | best-iteration snapshot fails | non-fatal print, no snapshot | loud, logged, alerts | ERROR and alert, or raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1821` | restoring a snapshot file fails | non-fatal print, revises from a mixed state | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1846` | git status cannot run | None silently, droppings cleanup skipped | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1849` | git status exits non-zero | None, stderr dropped | loud, logged, stops, alerts | ERROR with code and stderr, raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1885` | a dropping cannot be deleted | prints, continues; poisons later iterations | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1927` | git status cannot run preserving samples | ("", []), under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise or alert |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1932` | git status exits non-zero preserving samples | ("", []) silently, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise or alert |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:1956` | copying a sample fails | prints, partial output, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise after the loop |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2249` | spec suite cannot be read | [] silently, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2261` | a plan test file cannot be read | skipped, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2270` | an aligned file cannot be written | prints, measures the drifted file, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2387` | candidate path not under repo_root | builds a scope from an absolute path | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2393` | no coverage target derivable | hard-coded default module | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2431` | audit dir missing | skips green-phase.txt silently | loud, logged, stops, alerts | raise or route to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2526` | pytest interrupted in green phase | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2584` | coverage target absent | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2669` | zero tests collected twice | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2721` | iteration cap with failures | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2811` | deterministic failure | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2891` | circuit breaker trips | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2960` | cap below coverage target | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:2995` | circuit breaker trips | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3098` | full-suite run exits 2-5 or -1 with nothing parsed | exit code unchecked: reads as no regressions | loud, logged, stops, alerts | check the return code; error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3192` | skip-audit gate fails | WARNING, green passes anyway | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3310` | result carries no coverage figure | defaults to 100% | loud, logged, stops, alerts | missing coverage is a failure; HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3355` | no framework config ran in the green phase | success with no tests run | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3398` | non-pytest red phase has no tests | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3408` | runner cannot be built | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3416` | non-pytest runner crashes without running tests | reroutes to the scaffolder as no tests ran | loud, logged, stops, alerts | error_message to HALT on a crash code |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3584` | runner cannot be built in green | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3592` | non-pytest green run exits non-zero or collects nothing | unchecked; zero failures passes | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3599` | coverage_type invalid | defaults to LINE silently | loud, logged, stops, alerts | ERROR and HALT |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3647` | non-pytest cap with failures | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3672` | circuit breaker trips | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/verify_phases.py:3707` | non-pytest cap below coverage | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/graph.py:128` | git checkpoint after a node fails | prints, continues (best-effort) | loud, logged, stops, alerts | ERROR, alert, re-raise |
| `assemblyzero/workflows/testing/graph.py:217` | N1 error under auto_mode | ignored, continues to N2 | loud, logged, stops, alerts | route any error to HALT |
| `assemblyzero/workflows/testing/graph.py:227` | test-plan gate BLOCKED under auto | continues past a failed gate | loud, logged, stops, alerts | route BLOCKED to HALT or revision |
| `assemblyzero/workflows/testing/graph.py:232` | gate BLOCKED under strict policy | END, no alert | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:245` | still BLOCKED after the revision cap | END with a print | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:318` | regeneration exhausted at N2.5 | END, no HALT, no alert | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:355` | unrecognised next_node after N3 | END silently | loud, logged, stops, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:438` | iteration cap on the augment path | END silently | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:447` | augment attempts spent | END with a print | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:451` | cost budget exceeded on augment | END with a print | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:471` | iteration cap while N5 asks for a revision | END, error_message empty | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:478` | cost budget exceeded before N4 | END with a print | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:488` | unrecognised next_node after N5 | END silently | loud, logged, stops, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:513` | iteration cap after an E2E failure | END silently | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/graph.py:557` | adversarial node errors or skips | continues to N8 | loud, logged, stops, alerts | route an error or skip to HALT |
| `assemblyzero/workflows/testing/graph.py:732` | N4c can return an error | unconditional edge to N5 | stops, alerts | conditional edge to HALT |
| `assemblyzero/workflows/testing/nodes/implementation/edit_script_fix.py:273` | a planned file cannot be read | empty sets, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/implementation/edit_script_fix.py:303` | a test file cannot be read | empty set, under a tag | loud, logged, stops, alerts | remove the tag, ERROR, raise |
| `assemblyzero/workflows/testing/nodes/implementation/edit_script_fix.py:497` | model returns no edit blocks | None outcome, falls back to regeneration with a print | loud, logged, alerts | ERROR on the fallback |
| `assemblyzero/workflows/testing/nodes/implementation/edit_script_fix.py:503` | edit blocks do not apply | None outcome, fallback with a print | loud, logged, alerts | ERROR naming the blocks |
| `assemblyzero/workflows/testing/nodes/implementation/edit_script_fix.py:507` | edits empty the file | None outcome, fallback with a print | loud, logged, alerts | ERROR naming the file |
| `assemblyzero/workflows/testing/completeness/report_generator.py:89` | LLD cannot be read | WARNING, [] | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/report_generator.py:100` | Section 3 not found | WARNING, [] | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/report_generator.py:169` | no requirements extracted | empty requirements list | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/report_generator.py:187` | an implementation file cannot be read | WARNING, partial materials | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/report_generator.py:407` | report cannot be written | ERROR, returns a nonexistent path | stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/report_generator.py:444` | project root not found | falls back silently | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/implementation/import_validator.py:85` | metadata enumeration fails | silent fallback to a map | loud, logged, stops, alerts | ERROR and re-raise |
| `assemblyzero/workflows/testing/nodes/implementation/import_validator.py:119` | pyproject.toml unreadable | empty set; every import flagged | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/implementation/import_validator.py:229` | code does not parse | (True, []): a gate that could not run passes | loud, logged, stops, alerts | return False with the error, or raise |
| `assemblyzero/workflows/testing/nodes/revise_test_plan.py:226` | no requirements to revise against | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/revise_test_plan.py:246` | revisor spec invalid | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/revise_test_plan.py:266` | revisor call fails | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/revise_test_plan.py:307` | revision budget spent | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/templates/cp_docs.py:137` | no CLI commands extracted | invented placeholder row written | loud, logged, stops, alerts | raise or ERROR and skip |
| `assemblyzero/workflows/testing/templates/cp_docs.py:159` | no commands for the usage block | invented placeholder command | loud, logged, stops, alerts | raise or ERROR and skip |
| `assemblyzero/workflows/testing/templates/runbook.py:172` | no prerequisites extracted | placeholder prerequisites | loud, logged, stops, alerts | raise or ERROR and skip |
| `assemblyzero/workflows/testing/templates/runbook.py:200` | no procedure steps | placeholder procedure | loud, logged, stops, alerts | raise or ERROR and skip |
| `assemblyzero/workflows/testing/templates/runbook.py:210` | no verification steps | placeholder verification row | loud, logged, stops, alerts | raise or ERROR and skip |
| `assemblyzero/workflows/testing/knowledge/patterns.py:24` | types.yaml missing | silent inline fallback | loud, logged, stops, alerts | raise FileNotFoundError |
| `assemblyzero/workflows/testing/knowledge/patterns.py:30` | types.yaml unreadable | silent inline fallback | loud, logged, stops, alerts | ERROR and re-raise |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:45` | analysis holds no test cases | INFO, {} | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:82` | writing a test file fails | ERROR and re-raise, but no alert (N7.5 has no HALT route) | alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:90` | deleting the staging dir fails | ignored, leaves a staging dir | loud, logged, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:134` | a test case has empty code | skipped silently, partial file | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/runner_registry.py:117` | framework string unrecognised | None; one caller treats None as pytest | loud, logged, stops, alerts | raise ValueError |
| `assemblyzero/workflows/testing/runners/pytest_runner.py:45` | pytest exits interrupted, internal, usage or collection error | exit code never read; counts default to 0 | loud, logged, stops, alerts | raise or ERROR on codes other than 0 or 1 |
| `assemblyzero/workflows/testing/runners/pytest_runner.py:57` | no TOTAL coverage line | defaults to 0.0 | loud, logged, stops, alerts | None or raise when unmeasured |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:101` | count_stub_tests cannot parse | (0, 0, []); the syntax error is recorded at line 418 in the same pass | compliant | none |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:418` | generated tests do not parse | appended to errors; exhaustion halts through HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:499` | imported_helper_sources cannot parse | {} as documented; the error is reported at line 418 | compliant | none |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:500` | withdrawn fail-open tag | comment present | loud, logged, stops, alerts | delete the tag |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:522` | a neighbouring helper cannot be read or parsed | continues, drops the helper; a valid test can be refused misleadingly | loud, logged, stops, alerts | ERROR with path and cause; record it as a validation error |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:523` | withdrawn fail-open tag | comment present | loud, logged, stops, alerts | delete the tag |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:557` | validate_scenario_coverage cannot parse | []; the error is already listed from line 418 | compliant | none |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:676` | every test fails unconditionally and the spec has no bodies | stdout print, proceeds | loud, alerts | ERROR on stderr with issue and stub names |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:811` | the non-pytest runner cannot be built | stdout print, is_valid True: a gate that cannot run passes | loud, logged, stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:963` | scaffold budget spent on a valid suite | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:975` | scaffold invalid and regeneration exhausted | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py:1043` | legacy fallback with regeneration exhausted | escalate with no error_message, routed to end, not HALT | loud, logged, stops, alerts | set error_message so the run halts |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:101` | worktree absent | INFO, False as documented; the caller treats it as done | compliant | none |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:144` | git worktree list fails | WARNING, None, read as no branch | loud, logged, stops, alerts | raise CalledProcessError |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:193` | git branch -d fails | any "error: branch" read as not found | loud, logged, stops, alerts | match the exact not-found message, re-raise the rest |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:221` | no active lineage dir | INFO, None as documented; the caller checks first | compliant | none |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:277` | a lineage artifact cannot be read | continue, drops the iteration | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:288` | coverage figure does not parse | records 0.0% | loud, logged, stops, alerts | raise with file and text |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:45` | passed count unparseable | 0 as documented; advisory only | compliant | none |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:182` | E2E run times out | -1; halts, but the message omits the timeout | logged | carry stderr, timeout and command into error_message |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:188` | poetry or pytest missing | -1; halts, cause lost | logged | put the cause into error_message |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:210` | cleanup_sandbox is a stub | always reports success | loud, logged, stops, alerts | raise NotImplementedError or implement |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:231` | verify_safety_limits is a stub | always reports safe | loud, logged, stops, alerts | implement or raise |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:291` | audit dir missing | skips saving results | loud, logged, stops, alerts | error_message naming the dir |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:300` | sandbox cleanup fails | WARN on stdout, continues | loud, logged, stops, alerts | error_message routed to HALT |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:313` | no E2E tests collected | routes to finalize as if passed | loud, logged, stops, alerts | halt unless E2E explicitly skipped |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:331` | pytest internal error | routed to HALT, without cause or identity | logged | include issue and output tail |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:334` | pytest exit 2 or unknown code | treated as test failures, loops to N4 | stops, alerts | only exit 1 is test failure; halt otherwise |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:337` | no E2E tests ran on non-zero exit | proceeds to finalize as if passed | loud, logged, stops, alerts | halt as at line 313 |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:394` | circuit breaker trips | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/e2e_validation.py:417` | retry loop runs out | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/adversarial_gemini.py:214` | response model neither Pro nor Flash | WARNING, verification passes | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/adversarial_gemini.py:291` | unexpected provider exception | re-raised as a timeout, which the node treats as a skip | loud, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/adversarial_gemini.py:361` | success with no text | empty string accepted | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/implementation/claude_client.py:61` | timeout override not an integer | stdout, default used | loud, logged, stops, alerts | raise naming the variable |
| `assemblyzero/workflows/testing/nodes/implementation/claude_client.py:64` | timeout override not positive | stdout, default used | loud, logged, stops, alerts | raise naming the variable |
| `assemblyzero/workflows/testing/nodes/implementation/claude_client.py:250` | model is not a provider spec | [NON-RETRYABLE] string; the caller raises ImplementationError | compliant | none |
| `assemblyzero/workflows/testing/nodes/implementation/claude_client.py:270` | seat, provider or invoke raises | string with no type or ERROR log | loud, logged | ERROR with type, seat and file |
| `assemblyzero/workflows/testing/checkpoints.py:89` | worktree path missing | False silently | loud, logged, stops, alerts | raise naming the path |
| `assemblyzero/workflows/testing/checkpoints.py:96` | git add fails | return code ignored | loud, logged, stops, alerts | check it, fail with stderr |
| `assemblyzero/workflows/testing/checkpoints.py:103` | git diff --cached fails | any non-zero read as staged | logged | only exit 1 means staged |
| `assemblyzero/workflows/testing/checkpoints.py:115` | checkpoint commit fails | stdout non-fatal, False | loud, alerts, stops | ERROR and raise |
| `assemblyzero/workflows/testing/checkpoints.py:125` | git times out or cannot run | stdout non-fatal, False | loud, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/checkpoints.py:193` | measurement note not written | stdout non-fatal, False | loud, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/checkpoints.py:194` | withdrawn fail-open tag | comment present | loud, logged, stops, alerts | delete the tag |
| `assemblyzero/workflows/testing/checkpoints.py:200` | git notes add fails | stdout non-fatal, False | loud, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/checkpoints.py:222` | git notes show cannot run | None, read as no measurement | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/checkpoints.py:223` | withdrawn fail-open tag | comment present | loud, logged, stops, alerts | delete the tag |
| `assemblyzero/workflows/testing/checkpoints.py:229` | git notes show fails | None, same as no note | loud, logged, stops, alerts | raise unless git says no note |
| `assemblyzero/workflows/testing/checkpoints.py:232` | a note is corrupt | None silently | loud, logged, stops, alerts | raise naming commit and text |
| `assemblyzero/workflows/testing/checkpoints.py:238` | measurement numbers do not convert | None silently | loud, logged, stops, alerts | raise naming the commit |
| `assemblyzero/workflows/testing/checkpoints.py:239` | withdrawn fail-open tag | comment present | loud, logged, stops, alerts | delete the tag |
| `assemblyzero/workflows/testing/runners/playwright_runner.py:91` | no JSON report | WARNING, fabricated result | loud, logged, stops, alerts | raise with exit code and output head |
| `assemblyzero/workflows/testing/runners/playwright_runner.py:104` | JSON report does not parse | WARNING, fabricated result | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/implementation/context.py:40` | a completed file cannot be parsed | first 50 lines, generation continues | loud, logged | ERROR naming the file and error |
| `assemblyzero/workflows/testing/nodes/cleanup.py:47` | issue_number missing after N8 | INFO, run ends without cleanup | loud, logged, alerts | route to HALT |
| `assemblyzero/workflows/testing/nodes/cleanup.py:72` | keys not declared in the state | always 0.0, 0.0, UNKNOWN; the summary always reports failure | loud, logged, stops, alerts | read the declared keys, fail when absent |
| `assemblyzero/workflows/testing/nodes/cleanup.py:81` | repo_root missing | uses the current directory | loud, logged, stops, alerts | error_message when absent |
| `assemblyzero/workflows/testing/nodes/cleanup.py:96` | worktree removal or branch delete fails | WARNING, continues; N9 goes straight to END | loud, stops, alerts | error_message, conditional edge to HALT |
| `assemblyzero/workflows/testing/nodes/cleanup.py:103` | PR merge check fails | WARNING, records skip reason | loud, stops, alerts | error_message routed to HALT |
| `assemblyzero/workflows/testing/nodes/cleanup.py:123` | learning summary fails | WARNING, continues | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/nodes/cleanup.py:138` | archival produced no done dir | WARNING, continues | loud, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/cleanup.py:139` | lineage archival raises | WARNING, continues | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/exit_code_router.py:47` | red phase passes every test | END, no error; function unused | loud, logged, stops, alerts | route to HALT or delete the unused function |
| `assemblyzero/workflows/testing/exit_code_router.py:60` | pytest interrupted or internal error | end, not HALT; unused | loud, logged, stops, alerts | route to HALT or delete |
| `assemblyzero/workflows/testing/exit_code_router.py:68` | pytest timed out | end, not HALT; unused | loud, logged, stops, alerts | route to HALT or delete |
| `assemblyzero/workflows/testing/exit_code_router.py:71` | unknown exit code | end, not HALT; unused | loud, logged, stops, alerts | route to HALT or delete |
| `assemblyzero/workflows/testing/nodes/load_lld.py:202` | Section 10 cannot be parsed | empty suite, same as no functions; quiet fallback | loud, logged, stops, alerts | re-raise or return a parse-failure marker |
| `assemblyzero/workflows/testing/nodes/load_lld.py:324` | LLD rebuild from refs raised | WARN, None, continues on spec content | loud, logged, stops, alerts | alert with issue and cause, raise |
| `assemblyzero/workflows/testing/nodes/load_lld.py:325` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/load_lld.py:835` | no coverage target in the LLD | documented ADR 0207 default | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:896` | no files table | [], no red-phase import, no message | loud, logged, stops, alerts | raise WorkflowParsingError or error_message |
| `assemblyzero/workflows/testing/nodes/load_lld.py:969` | gh issue view timed out or missing | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:972` | gh issue view non-zero | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:977` | gh JSON does not parse | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:983` | issue has no body | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1001` | issue-only mode has no Section 10 | empty plan, success, no message | loud, logged, stops, alerts | error_message naming Section 10 |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1099` | spec missing | MISSING REQUIRED INPUT routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1136` | spec cannot be read | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1142` | spec too short | GUARD error routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1146` | spec not approved | GUARD WARNING, continues | loud, logged, stops, alerts | error_message so it halts |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1164` | original LLD unreadable | WARN, continues on the spec | loud, logged, stops, alerts | error_message naming path and cause |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1180` | original LLD fails Section 10 validation | swallowed, next source tried | loud, logged, stops, alerts | record each source's error |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1182` | no Section 10 anywhere | GUARD WARNING, zero scenarios | loud, logged, stops, alerts | error_message to halt at N0 |
| `assemblyzero/workflows/testing/nodes/load_lld.py:1224` | zero requirements extracted | prints, continues until N4b | loud, logged, stops, alerts | error_message at N0 |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:105` | no Section 10 | empty ParsedLLDTests silently | loud, logged, stops, alerts | raise naming the patterns |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:325` | no assertion derivable | emits assert True | loud, logged, stops, alerts | raise or emit a failing assertion |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:342` | no assertion pattern matches | emits assert True | loud, logged, stops, alerts | raise or emit a failing assertion |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:435` | unsupported framework | raises | compliant | none |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:457` | Playwright scaffold has no logic | always-passing placeholder | loud, logged, stops, alerts | failing placeholder and ERROR |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:489` | Jest scaffold has no logic | always-passing assertion | loud, logged, stops, alerts | failing assertion and ERROR |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:787` | emitted test file does not parse | empty repair set, continues | loud, logged, stops, alerts | raise or error_message |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:788` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:833` | find_spec raised | False, classified as a symbol | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:834` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:1069` | audit dir missing (non-Python) | audit file skipped silently | loud, logged, stops, alerts | raise or error_message |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:1153` | no scenarios | GUARD error routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/scaffold_tests.py:1199` | audit dir missing (pytest) | audit record skipped silently | loud, logged, stops, alerts | raise or error_message |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:101` | malformed range in Missing column | skipped silently | loud, logged, stops, alerts | raise a parse error |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:106` | malformed line number | skipped silently | loud, logged, stops, alerts | raise a parse error |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:134` | uncovered source unreadable | "", caller falls back to bare ranges | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:142` | uncovered source does not parse | documented fallback to _read_lines | compliant | none |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:209` | source unreadable in _read_lines | "" silently | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:218` | malformed range in _read_lines | skipped silently | loud, logged, stops, alerts | raise a parse error |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:223` | malformed line in _read_lines | skipped silently | loud, logged, stops, alerts | raise a parse error |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:317` | addition does not parse in vetting | keeps nothing, read as none pass | loud, logged, stops, alerts | raise: invariant breach |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:318` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:347` | vetting run executed nothing | drops all additions, returns to N5 with no error | loud, logged, stops, alerts | ERROR and error_message to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:389` | repair source does not parse | passed through unchanged | loud, logged, stops, alerts | raise or reject loudly |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:390` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:537` | N4c has no test file | returns to N5 with no error | loud, logged, stops, alerts | error_message, conditional edge to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:551` | coverage not measured | error_message on an unconditional edge to N5 | stops, alerts | conditional edge to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:554` | under target with no uncovered lines named | returns to N5, attempts not counted; can loop | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:581` | target test file unreadable | returns to N5 with no error | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:593` | audit dir missing | audit writes skipped silently | loud, logged, stops, alerts | raise or error_message |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:613` | augment seat cannot resolve | prints, returns to N5 with no error | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:645` | LLM call failed or empty | prints, returns to N5, no attempt counted | loud, logged, stops, alerts | error_message with the provider error |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:650` | no code block | prints, returns to N5 | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:671` | retry loop ran out | returns to N5 with no error (a skip) | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:701` | added tests failed | prints, partial output | loud, logged, stops, alerts | ERROR, count drops as a failure |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:721` | repair call returned an error | error ignored | loud, logged, stops, alerts | check and log the error |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:734` | repaired candidate does not parse | printed, continues | loud, logged, stops, alerts | ERROR, surface in error_message |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:735` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:755` | repair fails import validation | printed, continues | loud, logged, stops, alerts | ERROR, surface in error_message |
| `assemblyzero/workflows/testing/nodes/augment_tests.py:761` | none of the added tests pass | restores, returns to N5 with no error | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:132` | no implementation files | INFO, skipped; router always goes to N8 | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:148` | client cannot be built | WARNING, skipped | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:164` | quota exhausted | WARNING, skipped | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:167` | model not permitted | WARNING, skipped | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:174` | downgraded to Flash | WARNING, skipped | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:177` | call failed or timed out | WARNING, skipped | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:184` | malformed response | ERROR, verdict error, proceeds to N8 | stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:235` | generated file has violations | WARNING, deleted, partial set | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:239` | removing a rejected file failed | pass; the file stays | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:250` | zero valid tests | verdict fail at INFO, proceeds | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:372` | a file cannot be read for context | WARNING, "", partial context | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:119` | zero requirements | BLOCK routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:142` | no files to analyse | WARN, verdict PASS | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:158` | AST analysis raised | WARNING, verdict WARN, proceeds | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:215` | Layer 2 materials raised | WARNING, Layer 2 skipped | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:243` | report generation raised | WARNING, continues | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:249` | no LLD path | WARN, report skipped | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:364` | still BLOCK at the cap | END, bypasses HALT | loud, logged, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/completeness_gate.py:380` | issues stagnant | END, bypasses HALT | loud, logged, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/document.py:182` | README required but missing | False, reported as no update needed | loud, logged, stops, alerts | raise naming the README |
| `assemblyzero/workflows/testing/nodes/document.py:215` | README has no Features section | False silently | loud, logged, stops, alerts | raise naming the section |
| `assemblyzero/workflows/testing/nodes/document.py:289` | sidebar update failed | False return ignored | loud, logged, stops, alerts | check it and raise |
| `assemblyzero/workflows/testing/nodes/document.py:292` | wiki page generation raised | SKIPPED, continues | loud, logged, stops, alerts | alert and raise, or HALT |
| `assemblyzero/workflows/testing/nodes/document.py:308` | runbook generation raised | SKIPPED, continues | loud, logged, stops, alerts | alert and raise, or HALT |
| `assemblyzero/workflows/testing/nodes/document.py:338` | c/p doc generation raised | SKIPPED, partial cp_paths | loud, logged, stops, alerts | alert and raise, or HALT |
| `assemblyzero/workflows/testing/nodes/document.py:350` | README update raised | SKIPPED, continues | loud, logged, stops, alerts | alert and raise, or HALT |
| `assemblyzero/workflows/testing/audit.py:121` | audit dir missing | 1, as if empty | loud, logged, stops, alerts | raise FileNotFoundError |
| `assemblyzero/workflows/testing/audit.py:280` | audit log write failed | WARNING, continues | loud, logged, stops, alerts | alert and raise |
| `assemblyzero/workflows/testing/audit.py:320` | no TOTAL coverage row | 0.0 default, same as 0% | loud, logged, stops, alerts | None when absent |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:98` | before or after source does not parse | returns after untouched | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:99` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:134` | a passing test's class was deleted | dropped silently | loud, logged, stops, alerts | report the lost test or raise |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:172` | spec suite does not parse | contract unchanged silently | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:173` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:214` | plan or spec does not parse | plan unaligned silently | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/implementation/keep_passing_tests.py:215` | withdrawn fail-open tag | justifies the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/templates/wiki_page.py:120` | no overview extracted | placeholder in the wiki page | loud, logged, stops, alerts | raise naming the section |
| `assemblyzero/workflows/testing/templates/wiki_page.py:169` | _Sidebar.md missing | False; the caller ignores it | loud, logged, stops, alerts | raise or check the result |
| `assemblyzero/workflows/testing/coverage_report.py:137` | no TOTAL row | documented ABSENT, treated as failure | compliant | none |
| `assemblyzero/workflows/testing/coverage_report.py:143` | target absent from report | documented ABSENT with message | compliant | none |
| `assemblyzero/workflows/testing/path_validator.py:65` | stat failed | documented (False, reason) | compliant | none |
| `assemblyzero/workflows/testing/path_validator.py:164` | a context file fails validation | appended; run continues with partial context | loud, logged, stops, alerts | exit non-zero and alert on any rejection |
| `assemblyzero/workflows/testing/path_validator.py:177` | reading a validated file raised | appended, partial context | loud, logged, stops, alerts | raise or exit non-zero |
| `assemblyzero/workflows/testing/nodes/mechanical_hooks.py:70` | no .unleashed.json | documented no hook | compliant | none |
| `assemblyzero/workflows/testing/nodes/mechanical_hooks.py:74` | config unreadable | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/mechanical_hooks.py:91` | hook could not start | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/mechanical_hooks.py:98` | hook exited non-zero | error_message routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/mechanical_hooks.py:108` | git add failed | return code ignored | loud, logged, stops, alerts | check it and halt |
| `assemblyzero/workflows/testing/nodes/implementation/routing.py:62` | file_path not a str | raises TypeError | compliant | none |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:117` | edit-script call raises | failure outcome printed to stdout; falls back to regeneration | loud, alerts | ERROR with file, issue and cause; alert |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:125` | edit-script API error | stdout only, then regeneration | loud, alerts | ERROR with identity; alert |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:135` | whole file instead of edit blocks | stdout only, falls through | loud, alerts | ERROR with file and issue |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:239` | non-retryable API error | raises; the runner prints and exits 1, no alert | loud, alerts | ERROR and alert at the raise or the runner |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:270` | transport error refused or exhausted | stdout halt line, raises, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:301` | summary instead of code on every retry | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:316` | no code block after every retry | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:344` | mechanical validation fails every retry | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:357` | retry loop falls through | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:439` | git ls-files fails for another reason | any non-zero read as untracked | loud, logged, stops, alerts | only 1 is untracked; raise otherwise |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:559` | no files_to_modify | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:572` | paths fail pre-flight | routed to HALT | compliant | none |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:589` | reading a test file for the prompt fails | bare pass, prompt loses the tests | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:693` | batch API call fails | stdout, per-file fallback | loud, alerts | ERROR with identity; alert |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:704` | batch response unparseable for a file | stdout, fallback | loud, alerts | ERROR; alert |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:717` | batch code fails validation | stdout, fallback | loud, alerts | ERROR; alert |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:819` | reading an existing Modify target fails | bare pass; disables the shrink gate | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:912` | reading for the edit script fails | stdout, falls through to full-file | loud, alerts | ERROR, alert, stop |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:913` | withdrawn fail-open tag | documents the fall-through | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:933` | Modify target missing | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:946` | context over 180K tokens | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1016` | reading an unattributed file fails | "" silently; empty context later | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1017` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1065` | reading a test file after a failed patch | "" silently, recorded as completed | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1066` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1120` | reading the spec suite fails | "" silently, contract on incomplete input | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1121` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/orchestrator.py:1146` | writing the generated file fails | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:233` | dead-flag check cannot parse | [], could not run reads as passed | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:390` | empty-branch check cannot parse | [], reads as passed | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:482` | docstring-only check cannot parse | [], reads as passed | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:549` | trivial-assertion check cannot parse | [], reads as passed | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:665` | unused-import check cannot parse | [], reads as passed | loud, logged, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:780` | stat on a file fails | WARNING, skipped; verdict can be PASS | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:784` | file too large | WARNING, skipped; PASS on unchecked code | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:796` | reading a file fails | WARNING, skipped | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/completeness/ast_analyzer.py:807` | a file has a syntax error | WARNING, analysis skipped | loud, stops, alerts | FIXED in #3581 testing batch 1 (#3811) |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:156` | review prompt template missing | silent default prompt | loud, logged, stops, alerts | ERROR, alert, HALT or raise |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:428` | mechanical gates fail | HALT only without auto_mode | stops, alerts | route any error to HALT whatever auto_mode |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:489` | reviewer cannot resolve | HALT only without auto_mode | stops, alerts | route any error to HALT |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:553` | reviewer call fails | HALT only without auto_mode | stops, alerts | route any error to HALT |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:579` | unexpected review error | HALT only without auto_mode | stops, alerts | route any error to HALT |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:609` | no schema-valid verdict | with auto_mode falls through to N2 | stops, alerts | route any error to HALT |
| `assemblyzero/workflows/testing/nodes/review_test_plan.py:710` | no Required Changes extracted | placeholder feedback | loud, logged, stops, alerts | ERROR and raise or error_message |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py:142` | conftest does not parse | set(), check passes | loud, logged, stops, alerts | raise or explicit failure |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py:143` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py:197` | ancestor conftest unreadable | treated as no options, passes | loud, logged, stops, alerts | (False, error) or raise |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py:198` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py:212` | a directory cannot resolve | walk ends early, partial comparison | loud, logged, stops, alerts | (False, error) or raise |
| `assemblyzero/workflows/testing/nodes/implementation/parsers.py:213` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/nodes/implementation/prompts.py:153` | reading a Modify file for the prompt fails | bare pass, prompt lacks contents | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/framework_detector.py:215` | package.json unreadable | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/framework_detector.py:252` | unknown framework in test_dirs | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/framework_detector.py:273` | project root missing | {} silently; defaults to pytest | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/finalize.py:46` | file to archive missing | WARNING, None, reports COMPLETE | loud, logged, stops, alerts | ERROR and HALT or raise |
| `assemblyzero/workflows/testing/nodes/finalize.py:74` | move to done/ fails | ERROR without identity, continues to COMPLETE | logged, stops, alerts | identity, alert, HALT or raise |
| `assemblyzero/workflows/testing/nodes/finalize.py:152` | green output empty or unparseable | counts default to 0, workflow complete | loud, logged, stops, alerts | HALT when no parseable counts |
| `assemblyzero/workflows/testing/nodes/finalize.py:216` | some artifacts failed to archive | skipped list ignored | loud, logged, stops, alerts | non-empty skipped list is an error |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:63` | a test has no assertions | warning only, valid can be True | loud, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:79` | parse fails after compile succeeded | bare pass, duplicate check skipped | loud, logged, stops, alerts | FIXED in #3725: fails loud, error_message routed to HALT, which alerts; test in test_adversarial_review_halts.py |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:114` | mock scan cannot parse | [] for files whose errors are already recorded | compliant | none |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:227` | test does not compile | documented error entry; valid False | compliant | none |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:251` | assertion scan cannot parse | [] only for compiled files | compliant | none |
| `assemblyzero/workflows/testing/nodes/implementation/deprecated.py:58` | reading a test file for the batch prompt fails | bare pass | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/deprecated.py:87` | reading a Modify file fails | bare pass | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/nodes/implementation/deprecated.py:190` | no path in a code block | invents a path | loud, logged, stops, alerts | raise |
| `assemblyzero/workflows/testing/nodes/implementation/deprecated.py:218` | entry has no path or content | skipped silently, partial write | loud, logged, stops, alerts | ERROR and raise before writing |
| `assemblyzero/workflows/testing/runners/jest_runner.py:33` | npx not on PATH | raises, no ERROR, no alert | loud, alerts | ERROR and alert before raising |
| `assemblyzero/workflows/testing/runners/jest_runner.py:57` | package.json unreadable | bare pass, typecheck may be skipped | loud, logged, stops, alerts | ERROR, alert, raise |
| `assemblyzero/workflows/testing/runners/jest_runner.py:58` | withdrawn fail-open tag | documents the swallow | loud, logged, stops, alerts | remove the tag |
| `assemblyzero/workflows/testing/runners/jest_runner.py:72` | typecheck exits non-zero | red result, a legitimate failing run | compliant | none |
| `assemblyzero/workflows/testing/runners/jest_runner.py:110` | no JSON report | WARNING, fallback reads as not failing | loud, stops, alerts | ERROR and raise or error result |
| `assemblyzero/workflows/testing/runners/jest_runner.py:124` | JSON report unparseable | WARNING, fallback with zero failures | loud, stops, alerts | ERROR and raise or error result |
| `assemblyzero/workflows/testing/runners/jest_runner.py:169` | fallback after a parse failure | failed and errors 0 at exit 0 | loud, logged, stops, alerts | always mark the fallback as an error |
| `assemblyzero/workflows/testing/symbol_validator.py:71` | target module unreadable | None, treated as no finding | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/symbol_validator.py:137` | test source does not parse | [], same as all imports resolve | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/symbol_validator.py:152` | exported names undeterminable | skipped: could not check counts as passed | loud, logged, stops, alerts | report it as unverifiable |
| `assemblyzero/workflows/testing/runners/base_runner.py:96` | zero scenarios | WARNING, 0.0 as if measured | loud, stops, alerts | ERROR and raise ValueError |
| `assemblyzero/workflows/testing/runners/base_runner.py:129` | test command times out | ERROR without identity, -1 sentinel read as a failed run | logged, stops, alerts | identity, alert, raise |
| `assemblyzero/workflows/testing/runners/base_runner.py:132` | test binary not found | ERROR, -1 sentinel | logged, stops, alerts | identity, alert, raise |
| `assemblyzero/workflows/testing/runners/base_runner.py:135` | OS error launching | ERROR, -1 sentinel | logged, stops, alerts | identity, alert, raise |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:548` | int() of the title's issue number | returns None, so the title check degrades to a WARNING and is skipped | loud, logged, stops, alerts | Remove the dead handler (group 1 is \d+) or raise with the title text. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:571` | the title issue-number gate cannot run (no H1) | records WARNING severity; the draft passes N1.5 | loud, logged, stops, alerts | Make it ERROR severity so the draft is BLOCKED. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:584` | the title issue-number gate cannot run (no number parsed) | records WARNING severity; "could not check" is treated as passed | loud, logged, stops, alerts | Make it ERROR severity so the draft is BLOCKED. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1056` | glob while searching for similar-file suggestions | continues silently; suggestions are lost | loud, logged, alerts | Log at ERROR with the path and raise. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1080` | git cat-file could not be run | returns False, read as "path not on base" | loud, logged, stops, alerts | Raise GitOperationError naming the repo, ref and path. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1082` | git error (bad ref, not a repo) is indistinguishable from an absent path | non-zero rc becomes False and stderr is dropped | loud, logged, stops, alerts | Raise on any rc other than the "missing object" case and carry stderr. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1513` | the AST import sentinel crashed on a Modify file | logger.debug and continue; the file counts as checked | loud, logged, stops, alerts | Log at ERROR and raise (or alert_operator then raise). |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1583` | the lineage write of validation errors (empty-draft path) | WARNING and continue; the audit record is missing | loud, stops, alerts | logger.error with identity, then raise. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1617` | the lineage write (missing-sections path) | WARNING and continue | loud, stops, alerts | logger.error with identity, then raise. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1653` | the lineage write (parse-error path) | WARNING and continue | loud, stops, alerts | logger.error with identity, then raise. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1694` | the lineage write (bad repo_root path) | WARNING and continue | loud, stops, alerts | logger.error with identity, then raise. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1766` | the lineage write (aggregate-errors path) | WARNING and continue | loud, stops, alerts | logger.error with identity, then raise. |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1775` | mechanical validation blocks the draft | lld_status BLOCKED; route_after_validate_mechanical (graph.py:218-230) loops to N1 and sends it to HALT at the iteration cap, and HALT alerts | compliant | none |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py:1825` | recording validation-failure telemetry | print to stdout, continue | loud, logged, stops, alerts | alert_operator with identity, then raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:376` | the contract the repo declares is missing on disk | returns None; build_brief reports "declares no binding contract" and preflight (1100) skips it as not applicable | loud, logged, stops, alerts | Raise when config.contract is declared but the file is absent. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:864` | the declared contract cannot be read | sets brief.error; the roll continues | loud, stops, alerts | alert_operator and refuse the preflight. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:865` | the withdrawn fail-open convention | the tag justifies continuing past an unreadable contract | loud, stops, alerts | Delete the tag and raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1018` | the brief is not ready (no table, no sections, or an error) | NOT CHECKED reason returned; the roll proceeds | loud, stops, alerts | Treat not-ready as a refusal for repos that declare a contract. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1030` | provider or seat resolution failed | review.reason set, NOT REACHED, roll proceeds | loud, stops, alerts | alert_operator and raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1031` | the withdrawn fail-open convention | the tag justifies continuing | loud, stops, alerts | Delete the tag and raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1052` | the model call failed or returned nothing | reason recorded and returned; the roll proceeds | loud, stops, alerts | Log at ERROR, alert_operator, and refuse. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1060` | the reviewer's answer is not JSON | reason recorded; the roll proceeds | loud, stops, alerts | alert_operator and raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1061` | the withdrawn fail-open convention | the tag justifies continuing | loud, stops, alerts | Delete the tag and raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1069` | the reviewer's answer carries no findings list | reason recorded; the roll proceeds | loud, stops, alerts | Raise with the response excerpt. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1094` | fetching the issue title and body | a line is appended and the loop continues | loud, stops, alerts | alert_operator and refuse. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1095` | the withdrawn fail-open convention | the tag justifies continuing | loud, stops, alerts | Delete the tag and raise. |
| `assemblyzero/workflows/requirements/contract_fidelity.py:1115` | any NOT REACHED or NOT CHECKED audit | never refuses, so a gate that did not run lets the launch go ahead | stops, alerts | Return refuse=True when any audit was not reached. |
| `assemblyzero/workflows/requirements/form_check.py:388` | the EARS check cannot run (no Requirements section) | no violation is added, so report.ok stays True | loud, logged, stops, alerts | Add a violation when the required section is absent. |
| `assemblyzero/workflows/requirements/form_check.py:821` | EARS, tables or ownership were not examined (vacuous) | renders RESULT: PASS | stops, alerts | Render a vacuous run as NOT CHECKED, a failing verdict. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:112` | no title can be parsed from the issue draft | error_message, but route_after_finalize (graph.py:499-505) sends it to END, never to HALT | loud, logged, alerts | Route a non-empty error_message after N5 to HALT and name the draft and repo. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:126` | gh issue create non-zero | error_message routed to END, not HALT | loud, alerts | Route to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:136` | parsing the filed issue number from the URL | pass; filed_issue_number stays 0 on a success | loud, logged, stops, alerts | Raise with the URL. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:140` | gh issue create timed out | error_message routed to END, not HALT | loud, logged, alerts | Route to HALT and include the repo and title. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:142` | the gh binary is missing | error_message routed to END, not HALT | loud, alerts | Route to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:145` | audit_dir is missing or does not exist | the final audit save is silently skipped | loud, logged, stops, alerts | Raise when audit_dir is unset or absent. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:247` | the durable LLD copy is missing after the landing | final_lld_path keeps naming the removed worktree copy | loud, logged, stops, alerts | Set error_message when the durable copy is absent. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:261` | the LLD commit or landing failed | prints to stdout, sets commit_error, no error_message, so the graph ends at END without HALT | loud, alerts | Set error_message, log at ERROR, and route to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:297` | the created file is outside target_repo | passed through as documented; commit_and_pr's git add then fails non-zero and raises GitOperationError (git_operations.py:243-247) | compliant | none |
| `assemblyzero/workflows/requirements/nodes/finalize.py:450` | max_iterations is malformed | defaults the cap to 3 | loud, logged, stops, alerts | Raise naming the bad value. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:487` | the finalize repair budget is exhausted | error_message, finalize_repair_pending False, routed to END, not HALT | loud, alerts | Route to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:532` | no issue number | error_message routed to END, not HALT | loud, logged, alerts | Route to HALT with the repo. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:535` | no draft at finalize | returns with no error; finalize logs "complete" and carries on | loud, logged, stops, alerts | Set error_message and route to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:573` | the withdrawn fail-open convention; the error it guards is routed to END, not HALT | the worktree failure ends the graph without an alert | loud, alerts | Delete the tag and route the error to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:590` | the LLD file is not on disk after the write | error_message routed to END, not HALT | loud, alerts | Route to HALT. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:642` | writing the durable LLD copy | prints WARNING to stdout and continues | loud, stops, alerts | FIXED in #3767: fails loud, error routed to HALT, which alerts |
| `assemblyzero/workflows/requirements/nodes/finalize.py:643` | the withdrawn fail-open convention | the tag justifies continuing | loud, stops, alerts | FIXED in #3767: fails loud, error routed to HALT, which alerts |
| `assemblyzero/workflows/requirements/nodes/finalize.py:653` | audit_dir is missing | the final.md audit save is skipped silently | loud, logged, stops, alerts | Raise when audit_dir is unset or absent. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:673` | the declared source idea file is missing | returns silently; the idea is never moved to done | loud, logged, alerts | Log at ERROR and raise. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:787` | audit_dir is missing | the lineage move to done/ is silently skipped | loud, logged, stops, alerts | Raise when audit_dir is unset or absent. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:798` | the review loop ran out (graph.py:410-414 sends a non-APPROVED draft to N5) | LLD saved, commit skipped, "complete" logged, no error_message, END | loud, logged, stops, alerts | Set error_message for a non-APPROVED LLD and route to HALT. |
| `assemblyzero/workflows/requirements/ownership_check.py:459` | a criterion asserts a key whose owner row has no group tag | skipped; check_table_form never reports a missing group tag, so the assertion goes unchecked | loud, logged, stops, alerts | Add a violation for an untagged owner row in a joinable table. |
| `assemblyzero/workflows/requirements/ownership_check.py:611` | no variable table, so the ownership checks cannot run | no violation; form_check renders PASS | loud, stops, alerts | Make the vacuous state a violation or a NOT CHECKED verdict. |
| `assemblyzero/workflows/requirements/ownership_check.py:627` | owners are named in prose, so the per-criterion clauses cannot run | no violation; form_check renders PASS | loud, stops, alerts | Make the vacuous state a violation or a NOT CHECKED verdict. |
| `assemblyzero/workflows/requirements/scope_coverage.py:467` | no elements or no criteria table, so nothing is judged | report.ok is True; only the disclosure says NOT CHECKED | loud, stops, alerts | Make ok False when vacuous and refuse. |
| `assemblyzero/workflows/requirements/scope_coverage.py:476` | an alias's target rows are never checked to exist | the element counts as disposed | loud, logged, stops, alerts | Verify every aliased row ID exists and add a violation if not. |
| `assemblyzero/workflows/requirements/git_operations.py:116` | git fetch of the base branch, whose return code is ignored | continues and may cut from a stale ref | loud, logged, stops, alerts | Check the return code and raise GitOperationError with stderr. |
| `assemblyzero/workflows/requirements/git_operations.py:180` | worktree add with -b from the arc failed | the first error is discarded and a retry cuts from the existing branch, ignoring start_point | loud, logged, stops, alerts | Raise on the first failure, or verify the reused branch's base. |
| `assemblyzero/workflows/requirements/git_operations.py:265` | the commit SHA cannot be parsed | commit_sha stays "" silently | loud, logged, alerts | Resolve it with git rev-parse HEAD and raise on failure. |
| `assemblyzero/workflows/requirements/git_operations.py:330` | origin URL lookup failed | returns "" as documented best-effort; the caller falls back to landing.pr_url (306-309) | compliant | none |
| `assemblyzero/workflows/requirements/git_operations.py:395` | the commit SHA cannot be parsed | commit_sha stays "" silently | loud, logged, alerts | Resolve it with git rev-parse HEAD and raise on failure. |
| `assemblyzero/workflows/requirements/nodes/load_input.py:85` | no brief file | error_message; route_after_load_input (graph.py:154-155) sends it to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/load_input.py:92` | the brief file is missing | routed to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/load_input.py:98` | the brief file cannot be read | routed to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/load_input.py:147` | no issue number | routed to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/load_input.py:204` | gh issue view failed, or retries ran out | routed to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/load_input.py:207` | the issue body is empty or missing | proceeds to drafting with an empty body | loud, logged, stops, alerts | Return error_message when the body is empty. |
| `assemblyzero/workflows/requirements/nodes/load_input.py:334` | git remote get-url non-zero | falls through to "unknown/unknown" provenance | loud, logged, stops, alerts | Raise with stderr. |
| `assemblyzero/workflows/requirements/nodes/load_input.py:340` | the remote lookup raised | pass; writes "unknown/unknown" into the provenance frontmatter | loud, logged, stops, alerts | Log at ERROR and raise. |
| `assemblyzero/workflows/requirements/discrimination_check.py:278` | no Acceptance Criteria section, so nothing is judged | report.ok is True; only the disclosure says NOT CHECKED | loud, stops, alerts | Make ok False when the section is absent. |
| `assemblyzero/workflows/requirements/parsers/verdict_parser.py:76` | the verdict is empty | UNKNOWN status, with the warning only in a field | loud, logged, stops, alerts | Raise ValueError naming the issue. |
| `assemblyzero/workflows/requirements/parsers/verdict_parser.py:135` | the verdict status cannot be parsed | UNKNOWN; the caller (review.py:550) then applies no resolutions and keeps the draft unchanged | loud, logged, stops, alerts | Raise on an unparseable status. |
| `assemblyzero/workflows/requirements/config.py:122` | config validation (bad drafter or reviewer spec, max_iterations < 1) | returns an error list that no production code calls (is_valid at 158 is also uncalled) | loud, logged, stops, alerts | Call validate at workflow start and raise on any error. |
| `assemblyzero/workflows/requirements/nodes/human_gate.py:168` | verdict status cannot be decided reliably | the substring "APPROVED" anywhere (e.g. "NOT APPROVED") finalizes | loud, logged, stops, alerts | Decide on lld_status alone and halt on anything unrecognised. |
| `assemblyzero/workflows/requirements/nodes/human_gate.py:179` | the revise loop through N4 has no cap | returns to N1 unbounded until GraphRecursionError | loud, logged, stops, alerts | Check verdict_count against max_iterations and set error_message for HALT. |
| `assemblyzero/workflows/requirements/nodes/human_gate.py:186` | verdict status cannot be decided reliably (auto mode) | the substring "APPROVED" anywhere finalizes | loud, logged, stops, alerts | Decide on lld_status alone and halt on anything unrecognised. |
| `assemblyzero/workflows/requirements/verdict_summarizer.py:64` | a JSON verdict lacks blocking_issues or is malformed | returns an empty issue list | loud, logged, stops, alerts | Raise naming the missing key. |
| `assemblyzero/workflows/requirements/verdict_summarizer.py:66` | JSON parse of the verdict failed | WARNING, then falls back to text extraction | loud, stops, alerts | logger.error and raise. |
| `assemblyzero/workflows/requirements/verdict_summarizer.py:105` | JSON parse of the verdict status failed | pass, then falls back to substring matching | loud, logged, stops, alerts | Raise on a malformed JSON verdict. |
| `assemblyzero/workflows/requirements/verdict_summarizer.py:109` | text status cannot be decided reliably | any "APPROVED" substring (including "NOT APPROVED") is APPROVED | loud, logged, stops, alerts | Match the explicit verdict line and raise otherwise. |
| `assemblyzero/workflows/requirements/best_of_n.py:130` | a mechanical or test-plan gate crashed on a candidate | recorded as one failure; the candidate can still win, so the gate that could not run does not stop anything | loud, stops, alerts | Log at ERROR, alert_operator, and raise. |
| `assemblyzero/workflows/requirements/best_of_n.py:131` | the withdrawn fail-open convention | the tag justifies continuing | loud, stops, alerts | Delete the tag and raise. |
| `assemblyzero/workflows/requirements/best_of_n.py:156` | every candidate is unusable | None; generate_draft.py:218-223 turns it into error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/requirements/best_of_n.py:179` | the candidate count is malformed | silently returns SERIAL | loud, logged, stops, alerts | Raise naming the bad value. |
| `assemblyzero/workflows/requirements/best_of_n.py:180` | the withdrawn fail-open convention | the tag justifies the default | loud, logged, stops, alerts | Delete the tag and raise. |
| `assemblyzero/workflows/requirements/step_budget.py:83` | max_iterations is malformed | defaults to 3 | loud, logged, stops, alerts | Raise naming the bad value. |
| `assemblyzero/workflows/requirements/step_budget.py:159` | the graph step budget is exhausted | prints to stdout and returns error_message to the caller; the HALT node never runs | loud, alerts | Log at ERROR and call alert_operator before returning or raising. |
| `assemblyzero/workflows/requirements/nodes/ponder.py:35` | no draft to fix | skips; route_after_ponder always goes to N1.5, which blocks an empty draft (validate_mechanical.py:1575-1593) | compliant | none |
| `assemblyzero/workflows/requirements/nodes/ponder.py:73` | writing the fixed draft to disk | prints [WARN] and continues; the disk draft and state diverge | loud, logged, stops, alerts | Return error_message (route_after_ponder must then read it) or raise. |
| `assemblyzero/workflows/requirements/nodes/ponder.py:108` | writing the ponder-fixes lineage file | swallowed silently | loud, logged, stops, alerts | Log at ERROR and raise. |
| `assemblyzero/workflows/requirements/audit.py:133` | get_repo_structure: target repo path does not exist | returns a placeholder string that callers splice into the drafter prompt as the "repository structure" | loud, logged, stops, alerts | raise FileNotFoundError naming the repo and the caller, so the node returns error_message routed to HALT |
| `assemblyzero/workflows/requirements/audit.py:150` | add_tree cannot list a subdirectory | silently returns, so the subtree is missing from the structure given to the drafter | loud, logged, stops, alerts | log ERROR with the path and re-raise |
| `assemblyzero/workflows/requirements/audit.py:179` | the repo root cannot be listed | returns "(Permission denied reading repository)" as if it were structure content | loud, logged, stops, alerts | log ERROR and re-raise so the node halts |
| `assemblyzero/workflows/requirements/audit.py:333` | move_lineage_to_done: the lineage dir to archive is missing | logs INFO "skipping" and returns None | loud, logged, stops, alerts | treat a missing lineage dir as an error: log ERROR, call alert_operator, raise |
| `assemblyzero/workflows/requirements/audit.py:359` | shutil.move of lineage active->done fails | logger.error without repo/issue identity, returns None, and the caller continues | logged, stops, alerts | include the repo/issue and call alert_operator, then re-raise |
| `assemblyzero/workflows/requirements/audit.py:539` | a context file the operator named is outside the repo or missing (validate_context_path returns None) | silently drops it, so the draft is built without the requested context | loud, logged, stops, alerts | raise ValueError naming the rejected path and why |
| `assemblyzero/workflows/requirements/audit.py:558` | a context file cannot be read | silently continues, giving partial context | loud, logged, stops, alerts | log ERROR with the path and cause, then re-raise |
| `assemblyzero/workflows/requirements/audit.py:613` | resolving the repo key for the approval cache fails | falls back to an unresolved path key, which can file or look up the approval under a different key | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/requirements/audit.py:646` | git rev-parse --git-common-dir fails (non-zero rc) | ignores rc and stderr and returns the calling path, so worktree callers silently use a per-worktree cache | loud, logged, stops, alerts | separate "not a git repo" from a git failure, and raise on a failure with rc and stderr |
| `assemblyzero/workflows/requirements/audit.py:680` | lld-status.json is corrupt or unreadable | returns an empty cache; the next save overwrites the file, destroying every repo's approvals | loud, logged, stops, alerts | log ERROR with the path and cause, call alert_operator, raise |
| `assemblyzero/workflows/requirements/audit.py:683` | the cache file holds a non-object | returns an empty cache, which the next save overwrites | loud, logged, stops, alerts | raise a ValueError naming the file |
| `assemblyzero/workflows/requirements/audit.py:697` | the cache's repos field is malformed | silently replaces it with {}, discarding every slice on the next save | loud, logged, stops, alerts | raise a ValueError naming the file |
| `assemblyzero/workflows/requirements/audit.py:816` | an absolute lld_path is not under target_repo | keeps the absolute path as stored; the documented behavior ("Keep as-is"), and every reader just stores or displays it | compliant | none |
| `assemblyzero/workflows/requirements/audit.py:1183` | a Review Summary heading exists but its table does not match the pattern | the review evidence row is silently not embedded in the finalized LLD | loud, logged, stops, alerts | add an else branch that raises, saying the evidence row could not be embedded |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:185` | a best-of-N drafter candidate call fails | records it as an unusable score and continues with no ERROR line; only all-fail halts | loud, alerts | log ERROR with the candidate index, spec and cause for every failed candidate |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:201` | the audit dir is missing when a candidate is saved | the candidate is silently not preserved to lineage | loud, logged, stops, alerts | raise when audit_dir does not exist |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:218` | every best-of-N candidate was unusable | returns error_message, which route_after_generate_draft sends to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:233` | the audit dir is missing when the winning draft is saved | draft_path is None and current_draft_path is "", with no message | loud, logged, stops, alerts | return error_message, which routes to HALT |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:345` | a withdrawn `# fail-open:` tag (the held error does reach the HALT route at line 398) | the tag text is present in source | loud, logged, stops, alerts | delete the `# fail-open:` tag and reword the comment |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:358` | the drafting template is missing | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:366` | the prompt exceeds the cap | logs WARNING and truncates, so the drafter runs on a partial prompt | loud, stops, alerts | return error_message naming the size and the cap, so the run halts |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:389` | the Gemini preflight fails | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:398` | the drafter seat or provider is invalid | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:480` | the previous draft at previous_draft_path cannot be read | puts the placeholder "(unable to read previous draft ...)" into the system prompt and continues | loud, logged, stops, alerts | return error_message with the path and cause |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:589` | the drafter call fails | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:596` | the cost budget is exceeded | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:612` | the edit-script revision has no edit blocks | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:620` | edit blocks fail to apply | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:674` | the audit dir is missing when the serial draft is saved | draft_path is set to None and the draft is not recorded to lineage | loud, logged, stops, alerts | return error_message, which routes to HALT |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:807` | the Tiphys interface refresh raises | logs WARNING and falls back to the stale map | loud, stops, alerts | log ERROR and return error_message, or re-raise |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:1155` | prompt sections are dropped to fit the cap | WARNING, and the drafter runs without those sections | loud, stops, alerts | raise instead of dropping content |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:1160` | the prompt is still over the cap after dropping sections | hard-truncates mid-content with a WARNING | loud, stops, alerts | raise instead of hard-truncating |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py:1186` | validate_draft_structure gets an empty draft | returns None ("passes") | loud, logged, stops, alerts | return a blocking error for empty content, or delete the unused function |
| `assemblyzero/workflows/requirements/nodes/review.py:101` | the reviewer provider call fails (result.success False) | not checked; the failure becomes "" and is re-asked, so the provider's error_message is lost from the eventual halt | logged | check result.success and raise with result.error_message before parsing |
| `assemblyzero/workflows/requirements/nodes/review.py:122` | the re-ask provider call fails | not checked; the cause is reported as an unreadable response | logged | check retry.success and raise with its error_message |
| `assemblyzero/workflows/requirements/nodes/review.py:187` | the review prompt is missing | returns error_message, which route_after_review sends to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/review.py:201` | the reviewer seat or provider is invalid | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/review.py:247` | the reviewer response cannot be read twice | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/review.py:257` | the cost budget is exceeded | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/review.py:306` | a REVISE verdict has a malformed rationale (no Tier sections) | silently set to BLOCKED and looped back with no message | loud, logged, stops, alerts | return error_message saying the reviewer output broke the contract |
| `assemblyzero/workflows/requirements/nodes/review.py:328` | the audit dir is missing | the verdict is silently not saved to lineage | loud, logged, stops, alerts | return error_message when audit_dir does not exist |
| `assemblyzero/workflows/requirements/nodes/review.py:438` | the target repo's structure cannot be listed | passes, and the reviewer prompt says "structure could not be enumerated" | loud, logged, stops, alerts | log ERROR and raise |
| `assemblyzero/workflows/requirements/nodes/review.py:553` | update_draft could not apply resolutions or suggestions | prints "Warning:" to stdout, and an APPROVED draft goes forward without the resolutions | loud, logged, stops, alerts | treat any update_draft warning as an error and return error_message |
| `assemblyzero/workflows/requirements/nodes/review.py:557` | the parsers module fails to import | silently returns the unmodified draft | loud, logged, stops, alerts | remove the handler and let the ImportError raise |
| `assemblyzero/workflows/requirements/nodes/review.py:560` | updating the draft with the verdict raises | prints a warning and returns the unmodified draft | loud, stops, alerts | log ERROR and re-raise, or return error_message |
| `assemblyzero/workflows/requirements/nodes/review.py:592` | _parse_verdict_status cannot determine the verdict | defaults to BLOCKED silently | loud, logged, stops, alerts | raise on an unrecognized verdict, or delete the unused helper |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:325` | the analysis JSON does not parse | returns None, the documented "no verdict"; every caller treats None as no verdict and retries, then halts (line 684), or halts on the first answer (line 763) | compliant | none |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:333` | a finding in the model response is not an object | silently dropped, which can turn a findings list into "consistent" | loud, logged, stops, alerts | treat a non-dict finding as unparseable (return None) |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:371` | the storm probe raises | returns False ("no storm") silently | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:399` | run_context() raises | run_id is set to "" silently | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:407` | recording the unverified state fails | prints WARNING, so the unverified outcome is never recorded | loud, stops, alerts | call alert_operator and re-raise |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:561` | the issue body is empty, so the gate cannot run | returns {} (proceed) with a withdrawn `# fail-open:` tag | loud, logged, stops, alerts | return requirements_unverified and error_message (HALT) and delete the tag |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:583` | the analysis provider is invalid | _halt_unverified returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:643` | the escalation provider is invalid | prints WARNING and retries on the original model | loud, stops, alerts | return _halt_unverified naming the bad escalation spec |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:683` | no verdict after the retries run out | _halt_unverified returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:727` | every reported conflict is unarticulated, so the gate reached no usable verdict | prints WARNING, records, returns {} and proceeds to drafting | loud, stops, alerts | return _halt_unverified and delete the tag |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:763` | the confirming second ask fails | halts on the first answer, but the second call's cause is never logged | logged | include _no_verdict_reason of the second call in the message |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:779` | a withdrawn `# fail-open:` tag on the not-reproduced path | the tag text is present in source | loud, logged, stops, alerts | FIXED in #3767: tag removed; shown not a failure path, or already routed to HALT |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:814` | recording the conflict telemetry fails | prints "skipped" and continues | loud, alerts | log ERROR and call alert_operator |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:825` | must-resolve issue filing fails | prints WARNING and continues to the halt | loud, alerts | log ERROR and call alert_operator naming the repo/issue |
| `assemblyzero/workflows/requirements/graph.py:182` | the N1 drafter returns an error | routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/graph.py:230` | mechanical validation is still failing at the iteration cap | routes to HALT; the HALT node derives a reason and calls alert_operator | compliant | none |
| `assemblyzero/workflows/requirements/graph.py:235` | route_after_validate_mechanical never reads error_message | a mechanical-node error goes on to N1b instead of HALT | stops | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/graph.py:308` | route_after_ponder is unconditional | a Ponder node error goes on to mechanical validation | stops | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/graph.py:334` | the draft human gate sets an unrecognized next_node | ends the workflow silently | loud, logged, stops, alerts | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/graph.py:380` | the open-questions revision loop runs out (verdict_count >= max) | goes to the verdict gate instead of failing | loud, logged, stops, alerts | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/graph.py:414` | the BLOCKED revise loop runs out | goes on to finalize a BLOCKED draft instead of failing | loud, logged, stops, alerts | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/graph.py:505` | route_after_finalize ignores error_message | a finalize error goes to END, never HALT, so the operator is never alerted | loud, alerts | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/graph.py:578` | N0b returns error_message (arc worktree cannot be cut) | the unconditional edge runs N0c's model calls before the halt | stops | FIXED in #3581 requirements graph batch (#3864) |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:107` | no target repo path | logs WARNING and returns an empty context; drafting proceeds ungrounded | loud, stops, alerts | return error_message, once the N0b edge routes it to HALT |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:112` | the target repo path does not exist | logs WARNING and returns an empty context | loud, stops, alerts | return error_message naming the path |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:153` | the LLD arc worktree cannot be cut | logger.error plus error_message, but the unconditional N0b->N0c edge runs N0c first | stops | make the N0b edge conditional to HALT (see graph.py:578) |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:191` | a key file read returns no content (read failure or budget) | silently omitted from the context | loud, logged, stops, alerts | log ERROR for any key file that was selected and not read, and halt |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:268` | a related file read returns no content | silently omitted | loud, logged, stops, alerts | log ERROR and halt for an unreadable selected file |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:285` | Tiphys interface extraction raises | logs WARNING; interface_map stays {} and drafting proceeds | loud, stops, alerts | log ERROR and return error_message |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:361` | globbing docs/standards or docs/adrs fails | passes silently | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:375` | listing the repo root for __init__ files fails | passes silently | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:460` | a candidate path resolves outside the repo | skips it, as the boundary filter intends | compliant | none |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py:502` | rglob under a search dir fails | continues silently | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/requirements/state.py:356` | an empty assemblyzero_root/target_repo at state creation | raises | compliant | none |
| `assemblyzero/workflows/requirements/state.py:455` | state validation errors | returns an error list; the documented contract is "List of error messages. Empty if valid" | compliant | none |
| `assemblyzero/workflows/requirements/precheck.py:181` | the precheck --repo is not a directory | raises; tools/check_requirements.py catches it and exits EXIT_ERROR, never calling alert_operator | alerts | call alert_operator in tools/check_requirements.py's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:192` | the gh CLI is missing | raises PrecheckError; the tool exits 2 without an alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:196` | gh issue view times out | raises PrecheckError; exit 2, no alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:201` | gh issue view returns non-zero | raises PrecheckError with the stderr; exit 2, no alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:207` | gh output is not JSON | raises PrecheckError; exit 2, no alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:215` | gh returned no issue body | raises PrecheckError; exit 2, no alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:260` | the issue body is empty | raises PrecheckError; exit 2, no alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:283` | the N0c gate raises | re-raises as PrecheckError; exit 2, no alert | alerts | call alert_operator in the tool's PrecheckError handler |
| `assemblyzero/workflows/requirements/precheck.py:298` | the gate reached no verdict | returns status "error", which the tool turns into exit 2 with no ERROR line and no alert | loud, alerts | on a non-clean status the tool logs ERROR and calls alert_operator |
| `assemblyzero/workflows/requirements/precheck.py:310` | no conflict and no clean marker: no verdict | returns status "error"; exit 2, no alert | loud, alerts | on an "error" status the tool logs ERROR and calls alert_operator |
| `assemblyzero/workflows/requirements/parsers/draft_updater.py:35` | update_draft gets an empty draft | returns it with a warning string; the caller only prints warnings | loud, logged, stops, alerts | raise ValueError on an empty draft |
| `assemblyzero/workflows/requirements/parsers/draft_updater.py:84` | a resolution cannot be applied because the draft has no Open Questions section | appends a warning and continues | loud, logged, stops, alerts | raise, naming the unapplied resolution |
| `assemblyzero/workflows/requirements/parsers/draft_updater.py:105` | the resolved question cannot be matched in the draft | appends a warning, and the resolution is lost from the approved draft | loud, logged, stops, alerts | raise, naming the unmatched question |
| `assemblyzero/workflows/requirements/parsers/draft_updater.py:271` | the first heading regex matches but the section regex does not (existing_match is None) | AttributeError, which review.py line 560 swallows | loud, logged, stops, alerts | check existing_match is not None and raise a named error |
| `assemblyzero/workflows/requirements/form_gate.py:149` | the issue fetch for the form check fails | stores result.error; render does not refuse, so the launch proceeds with the gate not run | loud, stops, alerts | make an error result refuse the launch, and log ERROR and call alert_operator |
| `assemblyzero/workflows/requirements/form_gate.py:153` | the issue body is empty, so the gate cannot run | sets error, does not refuse, and the launch proceeds | loud, stops, alerts | refuse the launch on an empty body |
| `assemblyzero/workflows/requirements/form_gate.py:162` | the discrimination check raises | silently sets None, and nothing is printed for it | loud, logged, stops, alerts | log ERROR with the cause and re-raise |
| `assemblyzero/workflows/requirements/form_gate.py:169` | the scope-coverage check raises | silently sets None | loud, logged, stops, alerts | log ERROR with the cause and re-raise |
| `assemblyzero/workflows/requirements/form_gate.py:170` | a withdrawn `# fail-open:` tag on the scope-check handler | the tag text is present in source | loud, logged, stops, alerts | delete the tag and fix the handler |
| `assemblyzero/workflows/requirements/form_gate.py:193` | rendering a check that could not run | reports "could not be checked" and continues without setting refuse | stops, alerts | set refuse = True for an errored item |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py:64` | validation attempts run out | returns error_message; route_after_validate_test_plan sends it to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py:73` | no draft content | returns error_message, which routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py:139` | recording the test-plan failure telemetry fails | prints "skipped" and continues | loud, stops, alerts | log ERROR and call alert_operator, then re-raise |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py:154` | audit_dir is empty, so the failing draft cannot be preserved | silently skips preserving it | loud, logged, stops, alerts | return error_message when audit_dir is unset |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py:163` | writing the failed draft fails | prints and continues ("best-effort") | loud, stops, alerts | log ERROR, call alert_operator and re-raise |
| `assemblyzero/workflows/requirements/table_injection.py:120` | a table's line_no and rows extend past the body | silently clamps and slices a partial table, then injects it as "verbatim" | loud, logged, stops, alerts | raise if start + 2 + len(rows) exceeds len(lines) |
| `assemblyzero/workflows/requirements/table_injection.py:184` | no Section 3 heading to insert after | appends at the end; the docstring documents this as correct, because the manifest compiler finds the table anywhere | compliant | none |
| `assemblyzero/workflows/requirements/feedback_window.py:90` | the latest verdict alone exceeds the token budget | keeps it in full and drops the summaries; the docstring documents this priority rule, and render consumes it normally | compliant | none |
| `assemblyzero/workflows/requirements/feedback_window.py:131` | the oldest summaries are dropped to fit the budget | the documented behavior of a bounded window (step 5), and every caller renders it as is | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:132` | N3 receives an empty or under-100-character draft | returns validation_passed False with error_message "", and builds no cap message, so a halt at the cap carries no reason (the banner reads "unknown") | loud, logged | Build the same cap message the main path builds, or return an error_message naming the issue and draft length. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:280` | hallucination telemetry raises | prints a WARNING to stdout and continues | loud, logged, stops, alerts | Log at ERROR to stderr and call alert_operator, then re-raise. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:571` | the completeness retry loop runs out at the iteration cap | sets a detailed error_message, and route_after_validation sends the exhausted loop to HALT, which alerts | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1342` | pattern_references_valid cannot run because repo_root is missing | returns passed=True ("skipping file existence checks") | loud, logged, stops, alerts | Treat a missing repo_root as a node error routed to HALT. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1393` | a referenced pattern file cannot be read | records it as an invalid reference, so the check fails and the draft goes to revision, or to HALT at the cap | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1455` | import_targets_exist cannot run because repo_root is missing | returns passed=True ("skipping") | loud, logged, stops, alerts | Fail the node with an error routed to HALT. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1530` | the target environment probe cannot answer, so third-party imports go unvalidated | passes the check with only a note in the details | loud, logged, stops, alerts | Raise or return a node error naming the repo and the probe cause. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1614` | git ls-tree on the base ref fails | check=False; the return code and stderr are ignored, and the empty stdout is read as "no matches" | loud, logged, stops, alerts | Check returncode and raise with stderr when it is non-zero. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1702` | call_signatures_match cannot run because repo_root is missing | returns passed=True as "not applicable" | loud, logged, stops, alerts | Fail the node with an error routed to HALT. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1725` | a spec fence does not parse | withdrawn fail-open tag; the fence is silently skipped | loud, logged | FIXED in #3767: tag removed; shown not a failure path, or already routed to HALT |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1746` | a first-party callee module does not parse | withdrawn fail-open tag; the module's calls go unchecked and the check passes | loud, logged, stops, alerts | FIXED in #3767: fails loud, error routed to HALT, which alerts |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1879` | the LLD content needed for criteria coverage is missing | returns passed=True as "not applicable" | loud, logged, stops, alerts | Return a node error routed to HALT; a missing LLD at N3 is a pipeline fault. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1892` | criteria_coverage could not run (ran=False: no table, or untagged rows) | report.ok is True because missing is empty, so the gate passes | loud, logged, stops, alerts | Fail when report.ran is False (or demand REQ tags), instead of passing. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1988` | the target pyproject is not valid TOML | withdrawn fail-open tag; returns None, which the caller turns into an empty set | loud, logged, stops, alerts | Remove the tag and raise or alert with the TOMLDecodeError and the repo path. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2036` | reading pyproject from the base ref fails | prints to stdout and falls back to the checkout copy | loud, logged, stops, alerts | Log at ERROR, alert, and raise rather than substituting the checkout. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2037` | the base-ref pyproject is unreadable | withdrawn fail-open tag on the fallback path | loud, logged, stops, alerts | Remove the tag along with the fallback. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2050` | the checkout pyproject cannot be read | returns ("", "no pyproject could be read") and the check continues | loud, logged, stops, alerts | Raise with the path and the OSError, or distinguish a missing file from an unreadable one. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2051` | the pyproject is unreadable | withdrawn fail-open tag | loud, logged, stops, alerts | Remove the tag and make the read failure loud. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2083` | an extracted test function's source cannot be located in the draft | continues without a span, so the later complaint carries no line address | loud, logged | Raise, because the extractor and the draft disagree, which is an internal fault. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2194` | there is no Section 10 heading, so the check cannot run | returns passed=True ("check did not run") | loud, logged, stops, alerts | Fail the check when Section 10 is absent. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2222` | extract_test_plan_section raises | swallows the exception and sets section = "" | loud, logged, stops, alerts | Log at ERROR, alert, and re-raise. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2223` | the section extractor raises | withdrawn fail-open tag | loud, logged, stops, alerts | Remove the tag and the swallow. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2419` | the Section 10 test block does not parse | returns passed=True as "not applicable" | loud, logged, stops, alerts | Fail the check, naming the SyntaxError and the line span. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2420` | the Section 10 block does not parse | withdrawn fail-open tag | loud, logged, stops, alerts | Remove the tag and fail instead of abstaining. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:2641` | a fence in manifest traceability does not parse | withdrawn fail-open tag; the fence is skipped and counted in the details | loud, logged | Remove the tag; fail the check when a declared-Python fence goes unjudged. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:3439` | a stdlib base class cannot be imported or resolved | withdrawn fail-open tag; returns None, and the class's methods abstain | loud, logged | Remove the tag; record the unresolved base in the check details at ERROR. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:3535` | an untagged or diff fence does not parse | counts it and states the count in the api_symbols_exist details; documented contract (_ScanResult: "never a failure: nothing claimed they were Python"), and the only caller reports it | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:3873` | the target environment import probe fails (None) | returns an empty set silently, so unbound roots stay judged with no notice | loud, logged, stops, alerts | Raise or alert when the probe returns None. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:3890` | the first-party package scan cannot read the repo | returns an empty frozenset (fail-open), treating every imported root as foreign | loud, logged, stops, alerts | Log at ERROR, alert, and re-raise. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:3932` | N1 gathered no symbols, so the API symbol check cannot run | returns passed=True ("check skipped") | loud, logged, stops, alerts | Fail the check, or route to HALT, when the symbol table is empty for a Python target. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4167` | pyproject.toml exists but cannot be read or parsed for source roots | returns () silently ("best-effort") | loud, logged, stops, alerts | Raise with the path and cause. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4288` | pyproject.toml exists but cannot be read or parsed for the declared package | returns an empty set silently | loud, logged, stops, alerts | Raise with the path and cause. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4355` | a repo or src directory cannot be listed | continues silently, so first-party packages may be missed | loud, logged, stops, alerts | Log at ERROR, alert, and re-raise. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4360` | reading the declared package from pyproject fails | pass, a silent swallow | loud, logged, stops, alerts | Remove the swallow and let the OSError propagate with context. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4380` | poetry env info cannot run or times out | returns None silently | loud, logged, stops, alerts | Log at ERROR with the cause and raise or alert. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4382` | poetry env info exits non-zero | returns None and discards stderr | loud, logged, stops, alerts | Raise with the return code and stderr. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4417` | the find_spec probe in the target venv fails or prints nothing | returns None and discards stderr | loud, logged, stops, alerts | Raise with the return code and stderr. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4423` | the probe subprocess errors, times out, or prints bad JSON | returns None silently | loud, logged, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:4485` | a declared proxy-heuristic check fails | demotes it to passed with an ADVISORY prefix; this is operator-ruled policy (#2540, #2620; check_classification.py), not an operational failure, and the N5 reviewer judges the same dimension | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:130` | N6 receives an empty spec draft | prints to stdout and returns error_message, but N6 -> END is an unconditional edge (graph.py:513), so HALT and the alert never run | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:137` | the spec draft is too short to finalize | returns error_message on the unconditional N6 -> END edge; stdout print only | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:153` | finalize is reached with a verdict other than APPROVED | returns error_message on the unconditional N6 -> END edge; stdout print only | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:166` | the issue number is invalid | returns error_message on the unconditional N6 -> END edge | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:179` | repo_root is missing from state | defaults to the current directory and writes the spec there | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:219` | writing or renaming the temp file fails | removes the temp file and re-raises into the OSError handler | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:224` | the spec file write fails | prints "ERROR" to stdout and returns error_message on the unconditional N6 -> END edge | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:234` | the spec file is absent after the write | prints to stdout and returns error_message on the unconditional N6 -> END edge | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:257` | the durable handoff copy cannot be written (resume contract broken) | prints a WARNING to stdout, continues, and reports the stage completed | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:271` | audit_dir is missing or absent on disk | silently skips the audit-trail save, and the lineage move at line 279 | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:105` | the Section 2.1 Files Changed table cannot be found | returns an empty list with no error | loud, logged, stops, alerts | Return an error from load_lld when the table is absent. |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:165` | the change type is unrecognised | silently defaults to "Add" | loud, logged, stops, alerts | Raise ValueError naming the row and the raw change type. |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:196` | no explicit approval marker is found | the approval gate falls back to the substring "APPROVED" anywhere, so a gate that cannot verify passes | stops | Drop the substring fallback and require an explicit status marker. |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:226` | no issue number is provided | returns error_message, and route_after_load sends it to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:234` | repo_root is missing from state | defaults to the current working directory | loud, logged, stops, alerts | Return an error routed to HALT when repo_root is empty. |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:244` | the LLD file is not found | returns an error_message naming the issue and expected path, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:260` | reading the LLD fails | returns an error_message routed to HALT, but it names neither the issue nor the path | logged | Include the issue number, the path, and type(e).__name__ in the message. |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:266` | the LLD content is trivial | returns "GUARD: LLD content too short", routed to HALT, with no issue, path, or length | logged | Name the issue, the path, and the character count in the error_message. |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:274` | the LLD is not approved | returns an error_message naming the issue, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py:290` | no files are parsed from Section 2.1 | prints a WARNING to stdout and continues with an empty list | loud, logged, stops, alerts | Return an error_message routed to HALT. |
| `assemblyzero/workflows/implementation_spec/criteria_coverage.py:171` | a criteria row's cell count does not match the header | silently skips the row, so the criterion is dropped from coverage | loud, logged, stops | Raise or report malformed rows instead of skipping them. |
| `assemblyzero/workflows/implementation_spec/criteria_coverage.py:180` | a criteria row has neither a REQ tag nor an ID | silently skips the row | loud, logged, stops | Report the keyless row as a failure. |
| `assemblyzero/workflows/implementation_spec/criteria_coverage.py:222` | no pass-criteria table is found, so coverage cannot be checked | returns ran=False, whose ok is True, and the caller (validate_completeness.py:1892) passes the gate | loud, logged, stops, alerts | Give a not-run report ok=False, or have the caller fail on ran=False. |
| `assemblyzero/workflows/implementation_spec/criteria_coverage.py:237` | criteria lack REQ tags, so coverage cannot be established | returns ran=False and the caller passes the gate | loud, logged, stops, alerts | Fail the check, demanding tags, instead of reporting not applicable as a pass. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:54` | repo_root is missing, so no contract can be loaded | returns "" silently, and the contract cross-check is lost | loud, logged, stops, alerts | Return an N1b error routed to HALT when repo_root is empty. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:63` | the gate config declares a contract file that does not exist | returns "" silently and compiles without the contract | loud, logged, stops, alerts | Return an error naming the declared path, routed to HALT. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:66` | loading the gate config or reading the contract raises | prints to stdout and returns "" | loud, logged, stops, alerts | Log at ERROR, alert, and re-raise, or return an N1b error. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:67` | the contract cannot be loaded | withdrawn fail-open tag | loud, logged, stops, alerts | Remove the tag and the swallow. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:89` | the manifest compiler abstains or does not apply | withdrawn fail-open tag; prints to stdout and proceeds with the #2533 protection off | loud, logged, stops, alerts | Remove the tag; at least make the abstain (tables present, none in criteria shape) an ERROR with an alert. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:121` | criteria cannot compile | returns an error_message listing the failures, routed by route_after_compile_manifest to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:155` | audit_dir is unset or missing | silently skips persisting the manifest lineage artifact | loud, logged, stops, alerts | Fail loudly when audit_dir is unset or missing. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:186` | the must-resolve filing is not performed in mock mode | prints "skipped" and returns | loud, logged | Treat as documented test-mode behaviour without a fail-open tag, or log at ERROR. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:188` | the must-resolve filing is skipped | withdrawn fail-open tag | loud, logged | Remove the tag. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:198` | repo_root is missing when filing a must-resolve | defaults to "." | loud, logged, stops, alerts | Raise when repo_root is empty. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:199` | issue_number is missing when filing a must-resolve | defaults to 0 and files against issue 0 | loud, logged, stops, alerts | Raise when issue_number is missing. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:210` | must-resolve filing fails | prints a WARNING to stdout and continues; the halt still occurs, but the filing failure itself is never alerted | loud, logged, alerts | Log at ERROR and call alert_operator with the filing failure. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:211` | must-resolve filing fails | withdrawn fail-open tag | loud, logged, alerts | Remove the tag. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:230` | N1c has no manifest to gate | prints to stdout and passes through with error_message "" | loud, logged, stops, alerts | Fail when N1b abstained (shape mismatch); pass only on a true not-applicable. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:231` | the manifest gate passes through | withdrawn fail-open tag | loud, logged, stops, alerts | Remove the tag. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:256` | the criteria list is missing from state | falls back to criteria re-derived from the rows, which by its own comment can only agree with them, so the coverage gate becomes vacuous | stops | Return an N1c error when assertion_manifest_criteria is missing. |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py:275` | the manifest gate finds invariant violations | returns error_message, routed by route_after_manifest_gate to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py:87` | invalid retry context (count, empty LLD, target, or error) | raises ValueError | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py:101` | the Tier 2 snippet is missing | raises ValueError | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py:174` | Tier 2 spec-section extraction fails | logs at WARNING and silently falls back to the Tier 1 full prompt | loud, logged, stops, alerts | Log at ERROR and raise, naming the target file. |
| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py:232` | tiktoken encoding fails | logs at WARNING with no cause and returns a -1 sentinel | loud, logged, stops, alerts | Log at ERROR with the exception and re-raise. |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:328` | spec template file not found | prints to stdout, returns bare str(e) as error_message; the N2 router sends it to HALT | logged | prefix the message with [N2], the issue number and the template path |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:397` | seat resolution ValueError | the handler holds the error and re-raises it at line 421, so the node halts through line 425, but the line carries the withdrawn `# fail-open:` tag | fail-open tag (always a violation) | reword the comment so it does not use the fail-open tag |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:410` | Gemini transport preflight fails | returns error_message, routed to HALT by route_after_generate_spec | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:425` | drafter seat or provider cannot be built | returns error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:582` | edit-script retry loop runs out of attempts | returns the named halt message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:602` | drafter LLM call fails | returns error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:610` | cost budget exceeded | returns error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:616` | drafter reports success but returns an empty response | an empty string is accepted as the draft, saved, and sent to N3 with error_message "" | loud, logged, stops | return an error_message routed to HALT when the drafter response is empty |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:662` | audit_dir is set but missing on disk | the draft is not saved to lineage, spec_draft_path becomes "", and the run continues silently | loud, logged, stops, alerts | create the directory, or return error_message when the save cannot happen |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:747` | the pinning gate cannot pull named content out of the verdict | pinning is skipped and the revision passes unenforced, with only a stdout note | loud, stops, alerts | halt when the pinning gate cannot run instead of treating it as passed |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:1416` | prompt is over the character budget | drops whole sections, unknown-priority ones first (the binding ASSERTION MANIFEST header matches no priority keyword), and prints only [WARN] to stdout | loud, logged, stops, alerts | halt when a required section (LLD, manifest, draft) would be dropped |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py:1436` | prompt is still over budget after dropping sections | cuts the prompt off mid-content and sends the partial prompt to the drafter | loud, logged, stops, alerts | raise with the overage instead of hard-truncating |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:110` | repo_root missing | returns error_message, routed to HALT by route_after_analyze | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:118` | the LLD yields no files to modify | prints a WARNING to stdout, returns error_message "" and the run proceeds | loud, logged, stops, alerts | return error_message so the router halts |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:183` | a Modify/Delete target file does not exist | prints a WARNING, sets current_content None and continues | loud, stops, alerts | return error_message naming the missing file and issue |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:196` | a Modify/Delete target path is not a file | prints a WARNING, sets current_content None and continues | loud, stops, alerts | return error_message naming the path |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:216` | reading a target file fails | prints [WARN], sets current_content None and continues | loud, stops, alerts | return error_message with the file and exception |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:261` | unknown change_type in the LLD file list | passed through unchecked with no message | loud, logged, stops, alerts | return error_message naming the invalid change_type |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:310` | target-repo .py files do not parse | excluded from the symbol universe, reported only on stdout, run continues | loud, stops, alerts | halt with error_message listing the unparseable files |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:567` | reading a node pattern file fails | silent continue | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:627` | reading a state.py pattern file fails | silent continue | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:676` | reading a graph.py pattern file fails | silent continue | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:734` | reading a test pattern file fails | silent continue | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:782` | reading a tool pattern file fails | silent continue | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:831` | reading CLAUDE.md fails | `pass`, so the project rules are silently missing from context | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:843` | reading README.md fails | `pass`, silently omitted | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:871` | reading pyproject.toml fails | `pass`, silently omitted | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:914` | reading or parsing a file_to_modify for imports fails | silent continue; the file vanishes from the import map | loud, logged, stops, alerts | raise, or return error_message naming the file |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:947` | git ls-tree on the base ref fails | returns [] with return code and stderr ignored; the API surface silently becomes empty | loud, logged, stops, alerts | raise with the return code and stderr |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:959` | base has more than 200 .py files | sweep is cut short with a stdout note that calls may be misflagged; continues | loud, stops, alerts | halt, or remove the cap, rather than feeding a partial surface |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:988` | read_from_base returns "" (git error conflated with empty) | file silently skipped from the API surface | loud, logged, stops, alerts | raise when git show fails for a path ls-tree listed |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1024` | git ls-tree on the base ref fails | returns set(), so the symbol universe silently lacks the base and spec calls get misflagged | loud, logged, stops, alerts | raise with the return code and stderr |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1037` | base has more than 200 .py files | symbol sweep cut short with a stdout note; continues | loud, stops, alerts | halt, or remove the cap |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1044` | read_from_base returns "" on a git error | file silently skipped from the symbol universe | loud, logged, stops, alerts | raise when git show fails |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1054` | a base file does not parse | falls back to regex-scraped symbols (the fallback #2393 removed elsewhere) with no message | loud, logged, stops, alerts | record the file as unreadable and halt instead of regex-scraping |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py:1127` | a gathered target file does not parse | appended to unreadable and excluded; the caller only prints | loud, stops, alerts | raise, or have the caller return error_message |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:170` | reviewer LLM call fails | returns (None, error), the documented contract; its one caller (line 392) turns it into error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:173` | reviewer returns an empty response | (None, error) per the contract; caller halts at line 392 | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:179` | JSON contract violated | reads the output template per 0028 §3, re-asks once, and returns (None, error) on a second failure, so the caller halts | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:203` | second contract violation | the handler returns (None, error), which halts, but the line carries the withdrawn `# fail-open:` tag | fail-open tag (always a violation) | reword the comment so it does not use the fail-open tag |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:318` | iteration is past the hard ceiling | returns error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:329` | spec draft is empty | returns error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:334` | draft is under the minimum size | WARNING on stdout; still pays for a review | loud, stops, alerts | return error_message for a draft under MIN_SPEC_SIZE |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:338` | spec exceeds the review size limit | reviewer judges a truncated spec, and an APPROVED verdict then applies to the whole | loud, logged, stops, alerts | halt with error_message instead of reviewing partial input |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:366` | reviewer seat or provider cannot be built | error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:388` | cost budget exceeded | error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:395` | review LLM call or parse fails | error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:403` | verdict UNKNOWN | error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:432` | writing the verdict to the audit trail fails | WARNING on stdout; run continues without the lineage record | loud, stops, alerts | return error_message (or raise) naming the path and exception |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:516` | BLOCKED verdict or review loop exit | non-empty error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:558` | must-resolve filing for a requirements conflict fails | broad handler prints a WARNING to stdout and swallows it; the halt alert does not name the filing failure | loud, logged, alerts | call alert_operator with the filing failure (what, issue, cause) inside the handler |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:641` | LLD exceeds 50,000 chars | reviewer judges traceability against a truncated LLD, silently | loud, logged, stops, alerts | halt rather than review against a partial LLD |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py:771` | empty reviewer response | a BLOCKED verdict the reviewer never issued is made up, with no error | loud, logged, stops, alerts | raise StructuredContractError for an empty response |
| `assemblyzero/workflows/implementation_spec/revision_pinning.py:571` | pinning merge produces duplicate test definitions (merge malfunction) | emits the revision unenforced; the event is only printed to stdout by the caller | loud, stops, alerts | treat the merge malfunction as a halt instead of passing the revision unenforced |
| `assemblyzero/workflows/implementation_spec/revision_pinning.py:583` | pinning merge loses tests present in both inputs (differ misalignment) | emits the revision unenforced, so the pinning gate is bypassed | loud, stops, alerts | halt when the gate cannot produce a sound merge |
| `assemblyzero/workflows/implementation_spec/graph.py:265` | N4 next_node is empty or unrecognised | routes to END as a normal exit, with no error and no alert | loud, logged, stops, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/graph.py:513` | finalize_spec returns a non-empty error_message (finalize_spec.py lines 134-238: empty draft, invalid issue, write failure, file not created) | unconditional edge to END; the error never reaches HALT | loud, alerts | FIXED in #3581 spec finalize batch (#3887) |
| `assemblyzero/workflows/implementation_spec/assertion_manifest.py:259` | the LLD has tables but none in the criteria shape (abstained) | reported as not applicable; the compile node (compile_manifest.py:117-118) returns error_message "" and drafting proceeds without a manifest | loud, stops, alerts | have the caller halt when result.abstained is true |
| `assemblyzero/workflows/implementation_spec/assertion_manifest.py:284` | decision-table row has no ID (also lines 291, 307, 338, 355) | recorded as a CompileFailure, the documented contract; the compile node turns any failure into error_message (compile_manifest.py:121-139), routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/assertion_manifest.py:325` | one assertion fragment has no literal while others in the row compile | the fragment is silently dropped from the manifest (partial output) | loud, logged, stops, alerts | record a CompileFailure for every literal-less fragment |
| `assemblyzero/workflows/implementation_spec/nodes/edit_script.py:170` | malformed edit-block response | returns [], the documented contract; generate_spec re-prompts and halts via error_message when retries run out | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/edit_script.py:203` | an edit block cannot be applied (marker inside, not found, ambiguous; also lines 210, 215) | returns the failures list per the contract; the caller discards the partial text and halts when retries run out | compliant | none |
| `assemblyzero/workflows/implementation_spec/table_injection.py:139` | the LLD's machine-owned block is present but parses to no criteria table (damaged fence) | falls back silently to every criteria table in the LLD | loud, logged, stops, alerts | halt naming the damaged injected block |
| `assemblyzero/workflows/implementation_spec/lineage_seed.py:102` | reading a prior run's draft or verdict fails | returns "", so the run is skipped as non-resumable and paid work is silently replaced by an older seed or a fresh draw | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/workflows/implementation_spec/lineage_seed.py:140` | a prior verdict reads as empty or unreadable | silently dropped from review_feedback_history, which blinds the stagnation check | loud, logged, stops | raise when a verdict file in lineage cannot be read |
| `assemblyzero/workflows/implementation_spec/error_path_coverage.py:102` | the check did not run (ran=False, no implementation fence) | ok is True, so validate_completeness.py:1892/1913 records the check as passed | loud, logged, stops, alerts | make ok False when ran is False |
| `assemblyzero/workflows/implementation_spec/review_progress.py:73` | max_iterations is not an integer | silently substitutes the default base cap of 3 | loud, logged, stops, alerts | raise with the bad value |
| `assemblyzero/workflows/implementation_spec/review_progress.py:157` | REVISE verdict with empty feedback | Decision(False), which review_spec turns into error_message, routed to HALT | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/human_gate.py:146` | node invoked while the gate is disabled (misconfiguration) | prints to stdout and proceeds to N5 | loud, logged, stops, alerts | return error_message naming the misrouting |
| `assemblyzero/workflows/implementation_spec/nodes/human_gate.py:159` | no spec draft at the gate | error_message, sent to HALT by route_after_human_gate | compliant | none |
| `assemblyzero/workflows/implementation_spec/base_tree.py:41` | git fetch fails | return code and stderr ignored; a stale origin ref is read silently | loud, logged, stops, alerts | check the return code and raise with stderr |
| `assemblyzero/workflows/implementation_spec/base_tree.py:45` | origin/<base> cannot be resolved | silently falls back to the local branch, which #2021 says nothing fast-forwards | loud, logged, stops, alerts | raise naming the unresolvable remote ref |
| `assemblyzero/workflows/implementation_spec/base_tree.py:54` | git cat-file errors (bad ref, repo error) | treated the same as the file being absent, so the Add stays unreclassified | loud, logged | tell "missing" apart from a git error and raise on the error |
| `assemblyzero/workflows/implementation_spec/base_tree.py:63` | git show errors | returns "", the same as absent; callers skip silently | loud, logged, stops, alerts | raise on a git error other than path-not-found |
| `assemblyzero/workflows/checkpoint.py:31` | git rev-parse returns non-zero (not a repo, or git error) | returns None, which the docstring defines as "not in a git repo"; its caller treats it that way and exits 1 | compliant | none |
| `assemblyzero/workflows/checkpoint.py:32` | git binary is missing | returns None, so a missing git reads the same as "not in a repo" and the cause is lost | logged | Log the missing binary at ERROR with its cause, or raise it, instead of turning it into the not-a-repo value. |
| `assemblyzero/workflows/checkpoint.py:77` | no checkpoint DB path can be resolved | prints ERROR to stderr and exits 1, but never calls alert_operator | alerts | Call alert_operator before the exit. |
| `assemblyzero/workflows/narration.py:55` | gate-state lookup on a state that does not support `in` | returns False (gate described as the atlas describes it), which the docstring defines as the "unknown" answer | compliant | none |
| `assemblyzero/workflows/narration.py:64` | graph node has no atlas entry | prints a plain stdout line once and continues | loud, alerts | Log the missing atlas entry at ERROR on stderr and alert, or fail the graph build. |
| `assemblyzero/workflows/narration.py:114` | narration line build or print raises | silently `pass`, no log | loud, logged, stops, alerts | Log at ERROR with node_id and cause, alert, and re-raise. |
| `assemblyzero/workflows/narration.py:160` | writing the convergence record (record_node_enter) fails | `# fail-open:` tag; returns silently, so the record is missing | loud, logged, stops, alerts | Remove the fail-open tag, log at ERROR, alert, and raise. |
| `assemblyzero/workflows/narration.py:181` | setting the call-recording context (set_context) fails | `# fail-open:` tag; returns silently, so later model calls are recorded against the wrong node | loud, logged, stops, alerts | Remove the fail-open tag, log at ERROR, alert, and raise. |
| `assemblyzero/workflows/orchestrator/artifacts.py:160` | artifact missing, empty, or lacking its required heading | returns False, which the docstring defines as "not valid"; its only caller (should_skip_stage) redraws the stage, a legitimate state | compliant | none |
| `assemblyzero/workflows/orchestrator/config.py:128` | an override key not in the schema (for example a typo) | the key is dropped without a word and the default applies | loud, logged, stops, alerts | Raise ValueError naming the unknown override keys. |
| `assemblyzero/workflows/orchestrator/graph.py:100` | record_stage_enter fails | `# fail-open:` tag; returns silently | loud, logged, stops, alerts | Remove the fail-open tag, log at ERROR, alert, and raise. |
| `assemblyzero/workflows/orchestrator/graph.py:111` | current_stage is not a known stage runner (and not "done") | returns an empty update; the router sends it back to run_stage, so the graph loops until LangGraph's recursion limit fires with no stage named | loud, logged, stops, alerts | Return an error_message naming the unknown stage and route it to terminal. |
| `assemblyzero/workflows/orchestrator/graph.py:296` | a stage result is failed or blocked (retry gate refused, retries exhausted, non-transient, human gate) | routes to the terminal create_halt_node, which reads error_message and calls alert_operator | compliant | none |
| `assemblyzero/workflows/orchestrator/graph.py:465` | a failed run with an empty error_message | records the finalize gate key as the cause of a failure | logged | Record an explicit unknown-cause key, never the success key, for a failed run. |
| `assemblyzero/workflows/orchestrator/graph.py:503` | record_terminal fails | `# fail-open:` tag; returns silently, so the terminal record is missing | loud, logged, stops, alerts | Remove the fail-open tag, log at ERROR, alert, and raise. |
| `assemblyzero/workflows/orchestrator/graph.py:523` | writing the per-run record file fails | `pass` with no log | loud, logged, stops, alerts | Log at ERROR with the path and cause, alert, and raise. |
| `assemblyzero/workflows/orchestrator/graph.py:575` | base-branch resolution or validation fails | returns OrchestrationResult(success=False) with the reason only in error_summary; nothing logged, nothing alerted | loud, alerts | Log at ERROR and call alert_operator before returning, or raise. |
| `assemblyzero/workflows/orchestrator/graph.py:590` | configuration validation fails | returns OrchestrationResult(success=False) with the errors only in error_summary; nothing logged, nothing alerted | loud, alerts | Log at ERROR and call alert_operator before returning, or raise. |
| `assemblyzero/workflows/orchestrator/graph.py:717` | a run that did not reach done but has an empty error_message | reports failure with an empty error summary | logged | Give a non-success run a non-empty summary naming final_stage and stage_results. |
| `assemblyzero/workflows/orchestrator/resume.py:59` | state file is unreadable or corrupt | prints a Warning to stdout and returns None; the caller then raises "No persisted state found", which hides the real cause | loud, logged, alerts | Raise naming the corrupt file and cause, logged at ERROR and alerted. |
| `assemblyzero/workflows/orchestrator/resume.py:66` | state file is missing required keys, or its issue_number does not match (also line 73) | prints a Warning to stdout and returns None | loud, logged, alerts | Raise a ValueError naming the file and the defect. |
| `assemblyzero/workflows/orchestrator/resume.py:134` | lock file is corrupt or unreadable | deletes the lock with no log and takes the lock | loud, logged, alerts | Log at ERROR and alert before removing a corrupt lock, or refuse. |
| `assemblyzero/workflows/orchestrator/resume.py:174` | lock file is unreadable when a destructive tool asks whether a run is live | `# fail-open:` tag; returns None ("no live run") | loud, logged, stops, alerts | Remove the fail-open tag and raise, so the destructive caller refuses on an unreadable lock. |
| `assemblyzero/workflows/orchestrator/stages.py:86` | fetching the issue body for settlement fails | `# fail-open:` tag; returns None, the input reads as unsettled, and the stage redraws | loud, logged, alerts | Remove the fail-open tag, log at ERROR, and alert; raise if settlement must not proceed blind. |
| `assemblyzero/workflows/orchestrator/stages.py:230` | writing the settlement record fails | `# fail-open:` tag; prints to stdout and the stage stays passed | loud, logged, stops, alerts | Remove the fail-open tag, log at ERROR, alert, and fail the stage or raise. |
| `assemblyzero/workflows/orchestrator/stages.py:336` | the green-phase measurement keys are absent or unreadable | returns 0 ("no failures"), so a run that never measured counts as clean | loud, logged, stops | Return an unknown result distinct from 0, and fail the stage when no measurement exists. |
| `assemblyzero/workflows/orchestrator/stages.py:423` | the recovery plan JSON cannot be read | returns False (non-transient) with no log | loud, logged | Log the unreadable plan path and cause at ERROR. |
| `assemblyzero/workflows/orchestrator/stages.py:459` | the brief-summary provider call fails | WARNING log; returns "" and falls back to a raw passthrough | loud, stops, alerts | Log at ERROR, alert, and fail the triage stage. |
| `assemblyzero/workflows/orchestrator/stages.py:466` | the summary provider returns failure or an empty response | WARNING log; returns "" and the brief is built without a summary | loud, stops, alerts | Log at ERROR, alert, and fail the triage stage. |
| `assemblyzero/workflows/orchestrator/stages.py:590` | gh issue view fails, returns empty output, or returns unparseable JSON (lines 511-522) | turns the reason into a failed stage result; the router sends it to the alerting HALT node | compliant | none |
| `assemblyzero/workflows/orchestrator/stages.py:623` | persisting the brief to its canonical path fails | WARNING log; the stage passes with a temp-file artifact | loud, stops, alerts | Fail the stage with the path and cause. |
| `assemblyzero/workflows/orchestrator/stages.py:766` | the reviewer returns REVISE (not APPROVED) | with the gate off the LLD stage passes anyway | loud, logged, stops, alerts | Fail the stage on any non-APPROVED verdict. |
| `assemblyzero/workflows/orchestrator/stages.py:800` | the LLD sub-workflow raises | failed stage result, which the router sends to the alerting HALT node | compliant | none |
| `assemblyzero/workflows/orchestrator/stages.py:836` | no LLD worktree, so the spec cannot ride the LLD PR | prints to stdout and returns False; the spec never lands | loud, stops, alerts | Fail the spec stage when the spec cannot be landed. |
| `assemblyzero/workflows/orchestrator/stages.py:846` | the spec path is not under the target repo | returns False with no log | loud, logged, stops, alerts | Fail the stage, naming both paths. |
| `assemblyzero/workflows/orchestrator/stages.py:859` | git check-ignore errors (exit 128) | the error is treated as "not ignored" and processing goes on | loud, logged | Treat any return code other than 0 or 1 as a failure and report its stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:876` | git add of the spec fails | prints to stdout and returns False | loud, stops, alerts | Fail the spec stage with the git stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:889` | git commit of the spec fails | prints to stdout and returns False | loud, stops, alerts | Fail the spec stage with the git output. |
| `assemblyzero/workflows/orchestrator/stages.py:899` | git push of the spec commit fails | prints to stdout and returns True (success) | loud, logged, stops, alerts | Return failure and fail the spec stage with the push stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:903` | copying the spec into the LLD worktree fails | prints to stdout and returns False | loud, stops, alerts | Fail the spec stage with the cause. |
| `assemblyzero/workflows/orchestrator/stages.py:960` | recording spec convergence telemetry fails | WARNING log and skip | loud, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/workflows/orchestrator/stages.py:989` | the visual-gate declaration cannot be read (the failed result does route to HALT) | the behaviour is a failed, non-transient stage, but a withdrawn `# fail-open:` tag sits on it | loud, logged, stops, alerts | Delete the fail-open tag; the behaviour itself routes to HALT. |
| `assemblyzero/workflows/orchestrator/stages.py:1121` | the spec lineage directory cannot be created | WARNING log; the stage runs with no audit_dir, so drafts are not persisted and a resume cannot seed | loud, stops, alerts | Fail the stage with the path and cause. |
| `assemblyzero/workflows/orchestrator/stages.py:1111` | all 100 candidate lineage directory names already exist | the loop ends with audit_dir_str empty and no message | loud, logged, stops, alerts | Raise once the loop runs out without claiming a directory. |
| `assemblyzero/workflows/orchestrator/stages.py:1172` | a spec resume finds no prior draft-and-verdict pair | prints to stdout and draws fresh, discarding the resume | loud, stops, alerts | Fail the resumed stage, naming the lineage searched. |
| `assemblyzero/workflows/orchestrator/stages.py:1240` | the spec did not land on the LLD PR | the boolean return is ignored and the spec stage passes | loud, logged, stops, alerts | Check the return and fail the stage when it is False. |
| `assemblyzero/workflows/orchestrator/stages.py:1274` | the spec sub-workflow raises | failed stage result, which the router sends to the alerting HALT node | compliant | none |
| `assemblyzero/workflows/orchestrator/stages.py:1374` | git show-ref errors (any non-zero, not only "missing") | the error is treated as "branch absent" | loud, logged | Tell exit 1 (missing) from other codes and raise on errors. |
| `assemblyzero/workflows/orchestrator/stages.py:1387` | git rev-list --count fails, or its output does not parse (line 1391) | returns "not reusable, not divergent" with no log | loud, logged, stops, alerts | Raise with the git stderr instead of returning the neutral value. |
| `assemblyzero/workflows/orchestrator/stages.py:1453` | git branch --list of graveyard branches fails (also line 1546 in _best_measured_attempt) | returns None ("no preserved attempt"), and the resume rebuilds from zero | loud, logged, stops, alerts | Raise with the git stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:1472` | git merge-base or rev-list fails on a candidate grave (also lines 1469, 1561) | the candidate is skipped with no log | loud, logged | Tell "not an ancestor" (exit 1) from git errors and raise on errors. |
| `assemblyzero/workflows/orchestrator/stages.py:1475` | the rev-list count does not parse | `# fail-open:` tag; candidate skipped | loud, logged, stops, alerts | Remove the fail-open tag and raise with the output. |
| `assemblyzero/workflows/orchestrator/stages.py:1678` | the base branch cannot be resolved | prints [WARN] to stdout and goes on | loud, stops, alerts | Fail the impl stage. |
| `assemblyzero/workflows/orchestrator/stages.py:1684` | no base branch, so the worktree is carved from the ambient HEAD | prints [WARN] to stdout and carves from HEAD | loud, stops, alerts | Fail the stage rather than build from an unknown base. |
| `assemblyzero/workflows/orchestrator/stages.py:1740` | an impl resume finds no resumable preserved attempt | prints to stdout and starts from the base | loud, stops, alerts | Fail the resume, naming the graves examined. |
| `assemblyzero/workflows/orchestrator/stages.py:1781` | a preserved attempt cannot be used because a leftover branch is in the way | prints [WARN] to stdout and implements from zero | loud, stops, alerts | Fail the stage, naming the blocking branch. |
| `assemblyzero/workflows/orchestrator/stages.py:2027` | git worktree add or fetch fails (also the generic except at line 2043) | failed stage result, which the router sends to the alerting HALT node | compliant | none |
| `assemblyzero/workflows/orchestrator/stages.py:2093` | fetching the remote branch fails (unreachable remote, or no branch) | returns "" ("nothing to reconcile") with no log | loud, logged | Tell a missing branch from a fetch error and log the error at ERROR. |
| `assemblyzero/workflows/orchestrator/stages.py:2100` | git rev-parse fails | returns "" with no log | loud, logged, stops, alerts | Raise with the git stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:2111` | preserving the diverged remote branch fails | returns "", and the push goes ahead to fail later | loud, logged, stops, alerts | Raise with the push stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:2114` | deleting the old remote branch name fails | returns a note printed to stdout and goes on | loud, stops, alerts | Raise with the push stderr. |
| `assemblyzero/workflows/orchestrator/stages.py:2233` | the merge driver refuses (the failed result does route to HALT) | the behaviour is a failed, non-transient stage, but a withdrawn `# fail-open:` tag sits on it | loud, logged, stops, alerts | FIXED in #3767: tag removed; shown not a failure path, or already routed to HALT |
| `assemblyzero/workflows/orchestrator/stages.py:2259` | the PR stage raises (also the CalledProcessError handler at line 2244) | failed stage result, which the router sends to the alerting HALT node | compliant | none |
| `assemblyzero/workflows/orchestrator/stages.py:2335` | deleting a landed working-tree copy fails | appends a note, printed to stdout; cleanup passes | loud, stops, alerts | Fail the cleanup stage with the path and cause. |
| `assemblyzero/workflows/orchestrator/stages.py:2383` | reading the LLD worktree's branch fails | branch=None with no log, so branch deletion is skipped without a word | loud, logged, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/workflows/orchestrator/stages.py:2391` | deleting the LLD branch fails | appends a note, printed to stdout; cleanup passes | loud, stops, alerts | Fail the cleanup stage with the cause. |
| `assemblyzero/workflows/orchestrator/stages.py:2393` | removing the LLD worktree fails after its retries | appends a residue note, printed to stdout; cleanup passes | loud, stops, alerts | Fail the cleanup stage with the cause. |
| `assemblyzero/workflows/orchestrator/stages.py:2401` | removing the impl worktree fails after its retries | appends a residue note, printed to stdout; cleanup passes | loud, stops, alerts | Fail the cleanup stage with the cause. |
| `assemblyzero/workflows/orchestrator/stages.py:2429` | the LLD PR landing cannot be confirmed (no lld_pr_url) | a stdout note; cleanup passes | loud, stops, alerts | Fail cleanup unless the LLD's landing is verified on the base. |
| `assemblyzero/workflows/orchestrator/stages.py:2479` | the implementation squash is not verified on the base (fetch fails or it is not an ancestor) | failed cleanup result, which the router sends to the alerting HALT node | compliant | none |
| `assemblyzero/workflows/parallel/coordinator.py:106` | a shutdown signal arrives while items are still being submitted | stops submitting, and the unsubmitted items are neither checkpointed nor reported | loud, logged, stops, alerts | Checkpoint the unsubmitted items and report the run as interrupted. |
| `assemblyzero/workflows/parallel/coordinator.py:119` | a shutdown signal arrives while results are being collected | returns partial stats and results as a normal return | loud, logged, stops, alerts | Raise an interruption error naming the checkpointed items. |
| `assemblyzero/workflows/parallel/coordinator.py:169` | a worker function raises or a credential cannot be acquired | converts it to WorkflowResult(success=False, error=str(e)) with no log and no alert | loud, logged, alerts | Log at ERROR with item_id and cause, and alert, before returning the failed result. |
| `assemblyzero/workflows/parallel/credential_coordinator.py:79` | no credential is free before the timeout (also line 96) | returns None, which the docstring defines as timeout; the only caller (coordinator.py line 156) raises RuntimeError on it | compliant | none |
| `assemblyzero/workflows/parallel/credential_coordinator.py:117` | release is called for a credential that is not in use | ignored silently | loud, logged | Raise ValueError naming the unknown credential release. |
| `assemblyzero/workflows/death/age_meter.py:52` | an issue has no weighted label | uses DEFAULT_WEIGHT and logs a WARNING; this fallback is in the docstring ("Falls back to DEFAULT_WEIGHT") and compute_age_meter accepts it as a normal weight | compliant | none |
| `assemblyzero/workflows/death/age_meter.py:108` | the GitHub API fetch of closed issues | re-raises as RuntimeError, chaining the cause; the swallowing happens at the caller, hourglass.py:302 | compliant | none |
| `assemblyzero/workflows/death/age_meter.py:166` | the age meter state file is corrupt or unreadable | logs ERROR, then returns None, which every caller reads as "no state yet", so the meter resets to 0 and the save overwrites the file | stops, alerts | raise, and call alert_operator; keep None only for a file that does not exist |
| `assemblyzero/workflows/death/age_meter.py:183` | the atomic write of the age meter state | removes the temp file and re-raises | compliant | none |
| `assemblyzero/workflows/death/drift_scorer.py:67` | the README it was asked to scan is missing | logs a WARNING and returns [], which reads as zero drift | loud, stops, alerts | raise FileNotFoundError |
| `assemblyzero/workflows/death/drift_scorer.py:123` | the inventory it was asked to scan is missing | logs a WARNING and returns [], which reads as zero drift | loud, stops, alerts | raise FileNotFoundError |
| `assemblyzero/workflows/death/drift_scorer.py:165` | the docs directory it was asked to scan is missing | logs a WARNING and returns [], which reads as zero drift | loud, stops, alerts | raise FileNotFoundError |
| `assemblyzero/workflows/death/drift_scorer.py:249` | the extra docs_to_scan entries | silently drops missing docs, and adds existing ones to scanned_docs without scanning them, so the report claims coverage it never had | loud, logged, stops, alerts | scan each requested doc and raise on a missing one |
| `assemblyzero/workflows/death/hourglass.py:77` | the drift scan in the walk_field node | logs ERROR, appends to errors, and puts in an empty drift report with score 0, which the next node consumes | stops, alerts | return error_message and route it through a conditional edge to a HALT node that calls alert_operator |
| `assemblyzero/workflows/death/hourglass.py:101` | harvest has no drift report | appends a string to errors and continues to archive | loud, stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/death/hourglass.py:119` | harvest and building the reconciliation report | logs ERROR, sets report to None, and continues through archive, chronicle and rest | stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/death/hourglass.py:147` | archiving old artifacts | logs ERROR, appends to errors, and continues to chronicle and rest | stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/death/hourglass.py:165` | chronicle, the README and wiki update | logs ERROR, appends to errors, and continues to rest, which resets the meter | stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/death/hourglass.py:186` | saving the reset age meter | logs ERROR, then announces "THE NEW AGE BEGINS" and completes | stops, alerts | raise, or return error_message routed to HALT |
| `assemblyzero/workflows/death/hourglass.py:212` | reading or writing history.json | logs ERROR and completes without the history entry | stops, alerts | raise, or return error_message routed to HALT |
| `assemblyzero/workflows/death/hourglass.py:239` | the graph's routing after nodes that can fail | every edge is unconditional and the graph has no HALT node, so no node failure stops the run or alerts | stops, alerts | add a HALT node that calls alert_operator, with conditional edges that read error_message |
| `assemblyzero/workflows/death/hourglass.py:266` | the critical-drift trigger check | logs a WARNING and goes on as though drift were not critical | loud, stops, alerts | log ERROR, alert, and raise |
| `assemblyzero/workflows/death/hourglass.py:302` | the meter trigger check (GitHub fetch, compute, save) | logs a WARNING and returns (False, "", ...), which reads as "DEATH should not arrive" | loud, stops, alerts | log ERROR, alert, and raise |
| `assemblyzero/workflows/death/hourglass.py:340` | node failures the graph collected in result["errors"] | never reads result["errors"], so every collected failure is dropped | loud, logged, stops, alerts | raise with alert_operator when result["errors"] is non-empty |
| `assemblyzero/workflows/death/hourglass.py:343` | the workflow produced no reconciliation report | builds a report with zero findings and zero actions and returns it as a result | loud, logged, stops, alerts | raise and alert instead of building a placeholder report |
| `assemblyzero/workflows/death/reconciler.py:41` | the drift category is unknown | quietly maps it to update_description | loud, logged, stops, alerts | raise KeyError on an unknown category |
| `assemblyzero/workflows/death/reconciler.py:78` | writing an ADR file | logs ERROR, continues, and returns the action as if it were done | stops, alerts | raise after logging, or alert |
| `assemblyzero/workflows/death/reconciler.py:101` | the archive source file is missing | skips it silently and still returns the action | loud, logged, stops, alerts | raise FileNotFoundError |
| `assemblyzero/workflows/death/reconciler.py:104` | moving a file into docs/legacy | logs ERROR, continues, and returns the action as if it were done | stops, alerts | raise after logging, or alert |
| `assemblyzero/workflows/death/reconciler.py:128` | old_content does not appear in the target file, or the target is missing (line 123) | does nothing and says nothing, while the report says the action was "applied" | loud, logged, stops, alerts | raise when the replacement does not happen or the target is missing |
| `assemblyzero/workflows/death/reconciler.py:132` | reading or writing the README or wiki file | logs ERROR, continues, and returns the action as if it were done | stops, alerts | raise after logging, or alert |
| `assemblyzero/workflows/death/skill.py:34` | the /death mode argument is invalid | raises | compliant | none |
| `assemblyzero/workflows/death/skill.py:64` | reaper mode was asked for without --force | raises | compliant | none |
| `assemblyzero/workflows/janitor/fixers.py:49` | reading a file to fix its links | continues silently, and that file's links are never fixed | loud, logged, stops, alerts | log ERROR with the path and raise |
| `assemblyzero/workflows/janitor/fixers.py:100` | git worktree remove | ignores the return code and records "Pruned" with applied=True | loud, logged, stops, alerts | pass check=True, or raise and alert on a non-zero return |
| `assemblyzero/workflows/janitor/fixers.py:136` | git add | raises CalledProcessError with no log and no alert; n1_fixer does not catch it | logged, alerts | catch, call alert_operator with the repo and files, and re-raise |
| `assemblyzero/workflows/janitor/fixers.py:144` | git commit | tolerates "nothing to commit" as a legitimate state; any other failure raises, but with no log and no alert | logged, alerts | log ERROR and call alert_operator before raising |
| `assemblyzero/workflows/janitor/fixers.py:202` | gh pr create returned non-zero | returns None, which n1_fixer ignores | loud, logged, stops, alerts | raise RuntimeError with the stderr and alert |
| `assemblyzero/workflows/janitor/fixers.py:203` | branch creation, push, or PR creation | swallows the error and returns None | loud, logged, stops, alerts | log ERROR, alert, and re-raise |
| `assemblyzero/workflows/janitor/graph.py:44` | a probe crashed (status="error") | gathers the result with the others; n0_sweeper never returns error_message, so the run goes on | stops, alerts | return error_message when any probe errored, and route it to a HALT node |
| `assemblyzero/workflows/janitor/graph.py:99` | creating the fix PR | when it returns None the code does nothing (`if pr_url: pass`) | loud, logged, stops, alerts | raise or return error_message when pr_url is None |
| `assemblyzero/workflows/janitor/graph.py:151` | probes errored and produced no findings | routes to END as a clean run, and no report is filed | loud, stops, alerts | route to HALT when any probe_result has status "error" |
| `assemblyzero/workflows/janitor/graph.py:204` | the graph has no HALT node at all | node exceptions crash the run with no alert_operator, and errors kept in state are never routed | alerts | add a HALT node that calls alert_operator, with conditional routing on error_message |
| `assemblyzero/workflows/janitor/probes/__init__.py:57` | a probe raised | converts it to ProbeResult(status="error") with no log; the caller does not treat that as a stop | loud, stops, alerts | log ERROR, and have the sweeper halt on any error result |
| `assemblyzero/workflows/janitor/probes/adr_collision.py:34` | the ADR directory is missing, so the check cannot run | returns passed=True with "skipping" | loud, stops, alerts | return a failed result or raise |
| `assemblyzero/workflows/janitor/probes/dead_references.py:34` | the docs directory it was asked to scan is missing | skips it silently, and the probe can pass having scanned nothing | loud, stops, alerts | raise when a requested doc_dir is missing |
| `assemblyzero/workflows/janitor/probes/dead_references.py:44` | the markdown file does not decode | silently drops the undecodable bytes, and any references in them | loud, logged, stops, alerts | decode strictly and raise on error |
| `assemblyzero/workflows/janitor/probes/dead_references.py:49` | verification returned ERROR or UNVERIFIABLE | drops those results, so a check that could not run counts as passed | loud, stops, alerts | count any non-MATCH status as a failure |
| `assemblyzero/workflows/janitor/probes/drift.py:50` | the drift analysis raised | logs ERROR and returns status="error", which the janitor graph never halts on | stops, alerts | re-raise, or have the sweeper route errored probes to HALT |
| `assemblyzero/workflows/janitor/probes/harvest.py:23` | the harvest script is missing, so the check cannot run | files it as an info-severity finding | loud, stops, alerts | return status="error" or raise |
| `assemblyzero/workflows/janitor/probes/harvest.py:39` | the harvest script exited non-zero | ignores returncode and parses stdout; no DRIFT lines means status="ok" | loud, logged, stops, alerts | check returncode, raise with the stderr |
| `assemblyzero/workflows/janitor/probes/harvest.py:52` | the harvest script timed out | returns status="error" with no log; the graph does not halt | loud, stops, alerts | log ERROR and raise, or route to HALT |
| `assemblyzero/workflows/janitor/probes/harvest.py:58` | the harvest run raised | returns status="error" with no log; the graph does not halt | loud, stops, alerts | log ERROR and raise, or route to HALT |
| `assemblyzero/workflows/janitor/probes/inventory_drift.py:30` | the inventory file is missing, so the check cannot run | returns passed=True with "skipping" | loud, stops, alerts | return a failed result or raise |
| `assemblyzero/workflows/janitor/probes/links.py:65` | git ls-files for *.md failed | returns [], and the probe reports status="ok" | loud, logged, stops, alerts | raise with the return code and stderr |
| `assemblyzero/workflows/janitor/probes/links.py:95` | reading a markdown file | pass; its links are never checked | loud, logged, stops, alerts | log ERROR and raise |
| `assemblyzero/workflows/janitor/probes/links.py:118` | the link resolves outside the repo | returns False, which the probe reports as a broken-link finding; that is the documented security contract | compliant | none |
| `assemblyzero/workflows/janitor/probes/links.py:143` | git ls-files failed while looking for a replacement link | returns None, which reads the same as "no likely target", so the link is marked unfixable | loud, logged, stops, alerts | raise on a non-zero return |
| `assemblyzero/workflows/janitor/probes/persona_status.py:40` | the persona file is missing, so the check cannot run | returns passed=True with "skipping" | loud, stops, alerts | return a failed result or raise |
| `assemblyzero/workflows/janitor/probes/readme_claims.py:30` | the README is missing, so the check cannot run | returns passed=True with "skipping" | loud, stops, alerts | return a failed result or raise |
| `assemblyzero/workflows/janitor/probes/readme_claims.py:49` | verification returned ERROR or UNVERIFIABLE | drops those results, so a check that could not run counts as passed | loud, stops, alerts | count any non-MATCH status as a failure |
| `assemblyzero/workflows/janitor/probes/stale_timestamps.py:40` | the docs directory it was asked to scan is missing | skips it silently, and the probe can pass having scanned nothing | loud, stops, alerts | raise when a requested doc_dir is missing |
| `assemblyzero/workflows/janitor/probes/stale_timestamps.py:50` | the markdown file does not decode | silently drops the undecodable bytes | loud, logged, stops, alerts | decode strictly and raise on error |
| `assemblyzero/workflows/janitor/probes/stale_timestamps.py:101` | verification returned ERROR or UNVERIFIABLE | passed is False, but the summary says "No stale timestamps found" | logged | count and report ERROR and UNVERIFIABLE results in the summary |
| `assemblyzero/workflows/janitor/probes/todo.py:75` | git ls-files failed | returns [], and the probe reports status="ok" | loud, logged, stops, alerts | raise with the return code and stderr |
| `assemblyzero/workflows/janitor/probes/todo.py:92` | reading a source file | pass; its TODOs are never checked | loud, logged, stops, alerts | log ERROR and raise |
| `assemblyzero/workflows/janitor/probes/todo.py:117` | git blame failed | returns None, and the TODO is skipped at line 40 | loud, logged, stops, alerts | raise with the stderr |
| `assemblyzero/workflows/janitor/probes/todo.py:125` | the blame author-time does not parse | returns None, and the TODO is skipped | loud, logged, stops, alerts | raise ValueError with the line |
| `assemblyzero/workflows/janitor/probes/worktrees.py:107` | git worktree list failed | returns [], and the probe reports status="ok" | loud, logged, stops, alerts | raise with the return code and stderr |
| `assemblyzero/workflows/janitor/probes/worktrees.py:156` | git log for the branch failed | returns None, the same as "branch missing", and the worktree is skipped | loud, logged, stops, alerts | raise on a non-zero return |
| `assemblyzero/workflows/janitor/probes/worktrees.py:165` | the commit date does not parse | returns None, and the worktree is skipped | loud, logged, stops, alerts | raise ValueError with the date string |
| `assemblyzero/workflows/janitor/probes/worktrees.py:184` | git branch --merged failed | returns False, so the branch reads as "not merged" | loud, logged, stops, alerts | raise on a non-zero return |
| `assemblyzero/workflows/janitor/reporter.py:67` | gh auth status timed out | raises RuntimeError with no log and no alert | alerts | call alert_operator before raising |
| `assemblyzero/workflows/janitor/reporter.py:69` | gh auth status failed | continues when GITHUB_TOKEN is set, which gh honours as its documented fallback, and raises otherwise | compliant | none |
| `assemblyzero/workflows/janitor/reporter.py:99` | gh issue list timed out | returns None, which reads as "no existing report", so a duplicate report is created | loud, logged, stops, alerts | raise RuntimeError |
| `assemblyzero/workflows/janitor/reporter.py:101` | gh issue list failed | returns None, and a duplicate report is created | loud, logged, stops, alerts | raise with the stderr |
| `assemblyzero/workflows/janitor/reporter.py:108` | the gh issue list output does not parse | pass, then returns None, and a duplicate report is created | loud, logged, stops, alerts | raise ValueError with the output |
| `assemblyzero/workflows/janitor/reporter.py:134` | gh issue create timed out | raises RuntimeError with no log and no alert | alerts | call alert_operator before raising |
| `assemblyzero/workflows/janitor/reporter.py:136` | gh issue create failed | raises RuntimeError with the stderr, with no alert | alerts | call alert_operator before raising |
| `assemblyzero/workflows/janitor/reporter.py:164` | gh issue edit timed out | raises RuntimeError with no log and no alert | alerts | call alert_operator before raising |
| `assemblyzero/workflows/janitor/reporter.py:166` | gh issue edit failed | raises RuntimeError with the stderr, with no alert | alerts | call alert_operator before raising |
| `assemblyzero/workflows/janitor/reporter.py:276` | probes that crashed | lists them only as a section of the report body, and only when the run reaches the reporter | loud, stops, alerts | halt the workflow and alert on any probe error |
| `assemblyzero/workflows/lld/nodes/assembly_node.py:17` | the required issue context is absent | defaults to "", and the LLD is generated with no issue context | loud, logged, stops, alerts | return error_message when issue_context is empty |
| `assemblyzero/workflows/lld/nodes/assembly_node.py:72` | the LLM section generation | print()s to stdout, not an ERROR to stderr, retries, and after 3 attempts raises AssemblyError with no alert | loud, alerts | log ERROR to stderr, and alert or return error_message routed to HALT on exhaustion |
| `assemblyzero/workflows/scout/budget.py:25` | tiktoken encoding failed | silently falls back to len(text)//4, and the budget gate runs on a guessed count | loud, logged, stops, alerts | log ERROR and re-raise |
| `assemblyzero/workflows/scout/graph.py:34` | the scout workflow's error channel | failures go into a list; this module has no error_message field, no graph, no router and no HALT node | stops, alerts | add error_message and a graph whose conditional edges route it to a HALT node that calls alert_operator |
| `assemblyzero/workflows/scout/instrumentation.py:48` | enabling LangSmith tracing | logs a WARNING and continues without tracing | loud, alerts | log ERROR and raise |
| `assemblyzero/workflows/scout/instrumentation.py:122` | an external API call reported success=False | logs the "FAILED" status at INFO | loud, alerts | log failures at ERROR and alert |
| `assemblyzero/workflows/scout/nodes.py:33` | gh auth token returned non-zero | falls through silently to an anonymous Github() client | loud, logged, stops, alerts | raise with the stderr |
| `assemblyzero/workflows/scout/nodes.py:36` | gh auth token timed out, or gh is missing | pass, then an anonymous Github() client | loud, logged, stops, alerts | log ERROR and raise |
| `assemblyzero/workflows/scout/nodes.py:80` | the required topic is absent | defaults to "", and the search runs with an empty topic | loud, logged, stops, alerts | return error_message when topic is empty |
| `assemblyzero/workflows/scout/nodes.py:126` | the GitHub repository search | sets repos to [], and the brief is produced with no repos | loud, logged, stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/scout/nodes.py:157` | the token budget was exhausted before a repo was fetched | stops extracting silently and returns a partial repo list | loud, logged, stops, alerts | log ERROR and return error_message, or record the truncation explicitly |
| `assemblyzero/workflows/scout/nodes.py:174` | fetching the README | sets readme to "" silently | loud, logged, stops, alerts | log ERROR and return error_message |
| `assemblyzero/workflows/scout/nodes.py:179` | fetching the repo or license | sets readme to "" and uses the previous license_type silently | loud, logged, stops, alerts | log ERROR and return error_message |
| `assemblyzero/workflows/scout/nodes.py:197` | the token budget was exceeded after a fetch | drops this repo and the rest silently, a partial result | loud, logged, stops, alerts | log ERROR and return error_message, or record the truncation explicitly |
| `assemblyzero/workflows/scout/nodes.py:216` | internal_code_content is never loaded from internal_file_path | defaults to "", so the gap comparison is skipped silently | loud, logged, stops, alerts | load the file, or return error_message when the path is set but the content is empty |
| `assemblyzero/workflows/scout/nodes.py:274` | the LLM returned an empty response | puts in a placeholder string as the analysis | loud, logged, stops, alerts | raise on an empty response |
| `assemblyzero/workflows/scout/nodes.py:277` | the gap analysis LLM call | writes the error into gap_analysis text and continues ("don't fail the workflow") | loud, stops, alerts | log ERROR and return error_message routed to HALT |
| `assemblyzero/workflows/scout/nodes.py:310` | gap_analysis is missing | writes the brief with a placeholder | loud, logged, stops, alerts | return error_message when gap_analysis is empty |
| `assemblyzero/workflows/scout/nodes.py:327` | the data-privacy confirmation is missing | returns an "errors" list, not error_message, and no router halts on it | loud, stops, alerts | return error_message routed to HALT |
| `assemblyzero/workflows/scout/security.py:43` | the read path is outside base_dir | re-raises as ValueError | compliant | none |
| `assemblyzero/workflows/scout/security.py:85` | the write path is outside the directory | re-raises as ValueError | compliant | none |
| `assemblyzero/workflows/scout/templates.py:60` | gap_analysis is missing | renders the brief with a placeholder | loud, logged, stops, alerts | raise ValueError when gap_analysis is empty |
| `assemblyzero/workflows/telemetry/hallucination_log.py:105` | the audit_dir it was given does not exist | skips the audit sink silently | loud, logged, stops, alerts | raise FileNotFoundError when audit_dir is given but missing |
| `assemblyzero/workflows/telemetry/hallucination_log.py:114` | writing the audit sink file | print()s a WARNING to stdout and continues | loud, stops, alerts | log ERROR, call alert_operator, and raise |
| `assemblyzero/workflows/telemetry/hallucination_log.py:123` | appending to the JSONL sink | print()s a WARNING to stdout and continues | loud, stops, alerts | log ERROR, call alert_operator, and raise |
| `assemblyzero/speedrun/answer_key.py:223` | path gate cannot run because the LLD's paths were not extracted | returns refused=False ("the gate is inert"), so the verdict reads as a pass | loud, logged, stops, alerts | Record the gate as not run (a distinct outcome) and fail the audit, not a pass. |
| `assemblyzero/speedrun/answer_key.py:298` | required LLD answer-key artifact is missing | appends to coverage.files_missing and the audit continues, producing a partial report | loud, logged, stops, alerts | Log at ERROR, alert_operator, and make the audit exit non-zero when any listed artifact is missing. |
| `assemblyzero/speedrun/answer_key.py:303` | shipped source or test file in the arc is missing | appends to files_missing and `continue`s; no gate runs over it and the report is partial | loud, logged, stops, alerts | Same as above: ERROR, alert, and a non-zero audit result. |
| `assemblyzero/speedrun/answer_key.py:306` | an undecodable shipped file | silently replaces bad bytes and judges the altered content | loud, logged, stops, alerts | Read strictly and raise on a decode error, or record it as a failure. |
| `assemblyzero/speedrun/archive.py:164` | `git for-each-ref` fails while listing branches | returns an empty list, so graveyard discovery finds zero branches and the archive can still be marked complete | loud, logged, stops, alerts | Raise with the return code and stderr, or record an incomplete component. |
| `assemblyzero/speedrun/archive.py:262` | run log directory missing | records an incomplete component; archiving continues and writes a partial archive; the caller in speedrun_roll only appends a report line | loud, alerts | Call alert_operator with an ERROR line when archive_run finishes incomplete. |
| `assemblyzero/speedrun/archive.py:267` | an events log cannot be read | records an incomplete component and `continue`s; that roll is left out of the archive | loud, alerts | Log at ERROR and alert (once per incomplete archive). |
| `assemblyzero/speedrun/archive.py:295` | `git worktree list` fails | returns an empty set, so every candidate directory is treated as an orphan and tarred; the failure is not recorded | loud, logged, stops, alerts | Raise on a non-zero return code, with the stderr. |
| `assemblyzero/speedrun/archive.py:388` | stat/chmod fails while clearing ReadOnly | returns False with the exception discarded | loud, logged, stops, alerts | Log the cause at ERROR and re-raise. |
| `assemblyzero/speedrun/archive.py:396` | rmtree onexc hook when ReadOnly cannot be cleared | returns without raising, so shutil.rmtree swallows the removal error; stale files survive and get hashed into the new manifest | loud, logged, stops, alerts | Re-raise the original exception when clearing fails or the retry fails. |
| `assemblyzero/speedrun/archive.py:411` | first copytree attempt fails | discards it and retries once; the retry raises on its own failure | compliant | none |
| `assemblyzero/speedrun/archive.py:440` | making the archived copy writable fails | `pass`; the archive stays ReadOnly and the next re-archive fails the way #2404 describes | loud, logged, stops, alerts | Raise, or record an incomplete component, with the path and cause. |
| `assemblyzero/speedrun/archive.py:529` | integration branch not found, or rev-parse failed | adds an incomplete component and continues building a partial archive | loud, alerts | Alert the operator at ERROR when the archive ends incomplete. |
| `assemblyzero/speedrun/archive.py:536` | nothing to bundle | adds an incomplete component and continues | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:546` | `git bundle create` fails | adds an incomplete component with the stderr and continues | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:552` | `git bundle verify` fails | adds an incomplete component and continues | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:569` | copying a log file fails | adds an incomplete component and continues | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:588` | copying a lineage directory fails | adds an incomplete component and continues | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:599` | copying reset-artifacts fails | adds an incomplete component and continues | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:611` | tarring an orphan worktree fails | adds an incomplete component and `continue`s | loud, alerts | Same as above. |
| `assemblyzero/speedrun/archive.py:638` | rev-parse of a graveyard branch fails | writes sha null into index.json; the branch is not marked as an incomplete component | loud, logged, stops, alerts | Treat a None sha as an incomplete component, or raise. |
| `assemblyzero/speedrun/archive.py:689` | restore meets a graveyard entry with no recorded sha | skips the branch silently; the restore reports success without it | loud, logged, stops, alerts | Raise RuntimeError that names the branch the restore cannot reproduce. |
| `assemblyzero/speedrun/archive.py:807` | index.json is unreadable | returns VerifyResult(error=...); the tool reports it and exits non-zero (the documented contract), but nothing at ERROR and no alert | loud, alerts | Log at ERROR and call alert_operator before returning. |
| `assemblyzero/speedrun/box_health.py:122` | the box-health baseline file is unreadable or corrupt | returns [], as if there were no baseline; record_sample then overwrites the corrupt file | loud, logged, stops, alerts | Keep "file absent" as an empty baseline, but raise or alert on OSError/ValueError for a file that exists. |
| `assemblyzero/speedrun/box_health.py:176` | canary subprocess cannot start | returns (None, problem), the documented contract; check_box_health refuses the launch, and the caller prints to stdout and exits 91 | loud, alerts | Have the refusal path log at ERROR and call alert_operator. |
| `assemblyzero/speedrun/box_health.py:180` | canary pytest fails | returns (None, generic message), dropping the return code, stdout and stderr | loud, logged, alerts | Put the return code and the tail of the output in the problem, and alert on refusal. |
| `assemblyzero/speedrun/box_health.py:209` | psutil cannot be imported | marks every metric unreadable, so the launch is refused; ImportError detail dropped | loud, logged, alerts | Carry the exception text in the detail; ERROR and alert on refusal. |
| `assemblyzero/speedrun/box_health.py:213` | reading memory fails | marks the metric unreadable (launch refused); exception discarded | loud, logged, alerts | Record type(e).__name__ and the message in the metric detail; alert on refusal. |
| `assemblyzero/speedrun/box_health.py:218` | process enumeration fails | marks two metrics unreadable and returns; exception discarded | loud, logged, alerts | Same as above. |
| `assemblyzero/speedrun/box_health.py:293` | box is degraded, or a resource could not be read | returns BoxHealth(False); speedrun_roll prints the message to stdout and returns 91 with no alert | loud, alerts | Write the message to stderr at ERROR and call alert_operator. |
| `assemblyzero/speedrun/box_health.py:300` | canary could not be timed | returns BoxHealth(False); caller prints to stdout, exits 91, no alert | loud, alerts | Same as above. |
| `assemblyzero/speedrun/convergence.py:90` | appending a run record fails | returns False and the run continues; the factory report quietly falls back to the banner | loud, logged, stops, alerts | Log at ERROR, call alert_operator, and raise. |
| `assemblyzero/speedrun/convergence.py:91` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag and fix the handler as above. |
| `assemblyzero/speedrun/convergence.py:185` | a record line is corrupt | counts it as unreadable and continues; the only consumer (factory_report.apply_records) discards the count | loud, logged, stops, alerts | Raise or alert on corrupt lines, and make the callers use the count. |
| `assemblyzero/speedrun/convergence.py:186` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag and fix the handler. |
| `assemblyzero/speedrun/convergence.py:195` | a record is not a dict or has an unknown event | counted and dropped | loud, logged, stops, alerts | Same as line 185. |
| `assemblyzero/speedrun/emergency_stop.py:89` | stat of a kill file fails | `continue`s silently, so an operator stop can be missed | loud, logged, stops, alerts | Log at ERROR and alert, naming the path and the cause. |
| `assemblyzero/speedrun/emergency_stop.py:109` | unlinking a kill file fails | `continue`s silently; the stale file stops the next launch, which the docstring calls load-bearing | loud, logged, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/speedrun/emergency_stop.py:223` | kill and kill-failure messages with no handler | defaults to a no-op, so a failed tree-kill message is discarded | loud, logged, alerts | Default to an ERROR log on stderr plus alert_operator for the failure case. |
| `assemblyzero/speedrun/emergency_stop.py:286` | tree-kill of the running child fails | reports only through on_kill (no ERROR, no alert) and falls back to proc.kill(); grandchildren may survive | loud, alerts | Log at ERROR and call alert_operator naming the pid and the cause. |
| `assemblyzero/speedrun/emergency_stop.py:292` | the fallback proc.kill() fails | `pass`; the ordered stop may not land | loud, logged, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/speedrun/factory_report.py:496` | withdrawn fail-open convention (the handler itself raises after the loop) | the tag is present | loud, logged, stops, alerts | Remove the tag; the behaviour is already compliant. |
| `assemblyzero/speedrun/factory_report.py:511` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag. |
| `assemblyzero/speedrun/factory_report.py:529` | a record's timestamp cannot be parsed | keeps the record in every window ("could not check" treated as in-window), and nothing counts it | loud, logged, stops, alerts | Count undatable records and report them as a failure, or raise. |
| `assemblyzero/speedrun/factory_report.py:630` | a run log cannot be stat'd | mtime becomes "", the run is kept in every window and filed under "(undated)" | loud, logged, stops, alerts | Raise or alert with the path and the cause. |
| `assemblyzero/speedrun/factory_report.py:631` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag and fix the handler. |
| `assemblyzero/speedrun/factory_report.py:646` | a run log cannot be read | sets unreadable=True and returns facts with the default outcome "killed"; render_report never prints unreadable, so the log counts as a killed run | loud, logged, stops, alerts | Raise, or report unreadable logs separately at ERROR and alert. |
| `assemblyzero/speedrun/factory_report.py:647` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag and fix the handler. |
| `assemblyzero/speedrun/factory_report.py:764` | withdrawn fail-open convention | the tag is present (the absence is printed as NO in the stores table) | loud, logged, stops, alerts | Remove the tag. |
| `assemblyzero/speedrun/factory_report.py:802` | corrupt lines in the convergence store | throws away the unreadable count read_records returns so callers can report it | loud, logged, stops, alerts | Carry the count into the report and fail or alert when it is non-zero. |
| `assemblyzero/speedrun/factory_report.py:851` | a path cannot be resolved or compared | returns False, which drops the halt bundle silently | loud, logged, stops, alerts | Raise or alert with the path and the cause. |
| `assemblyzero/speedrun/factory_report.py:852` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag and fix the handler. |
| `assemblyzero/speedrun/factory_report.py:928` | withdrawn fail-open convention (the caller does count it as unplaced and print it) | the tag is present | loud, logged, stops, alerts | Remove the tag. |
| `assemblyzero/speedrun/factory_report.py:971` | a halt-evidence bundle is unreadable or corrupt | `continue`s; the comment says a denominator is reported, but nothing counts it | loud, logged, stops, alerts | Count and report it at ERROR and alert, or raise. |
| `assemblyzero/speedrun/factory_report.py:972` | withdrawn fail-open convention | the tag is present | loud, logged, stops, alerts | Remove the tag and fix the handler. |
| `assemblyzero/speedrun/factory_report.py:976` | a halt bundle is valid JSON but not an object | dropped silently, uncounted | loud, logged, stops, alerts | Count it as unreadable and report it. |
| `assemblyzero/speedrun/golden_disasters.py:273` | a corpus fixture is missing | returns CaseResult(errored=True), the documented contract; tools/golden_disasters.py exits 1, but nothing at ERROR and no alert | loud, alerts | Log at ERROR and call alert_operator from the tool when any case errors. |
| `assemblyzero/speedrun/golden_disasters.py:282` | no runner registered for a case | returns CaseResult(errored=True); the tool exits 1 with no ERROR line and no alert | loud, alerts | Same as above. |
| `assemblyzero/speedrun/healing.py:151` | writing a heal record fails | returns False with the exception discarded; the heal goes unrecorded | loud, logged, stops, alerts | Log at ERROR with the cause, call alert_operator, and raise. |
| `assemblyzero/speedrun/healing.py:168` | a heal ledger line is corrupt | `continue`s and the loss is not counted (the docstring asks callers to infer it from a length they never see) | loud, logged, stops, alerts | Count corrupt lines and fail or alert when any exist. |
| `assemblyzero/speedrun/leavings.py:180` | `git status` fails in untracked_files | returns [], so the caller sees no untracked files | loud, logged, stops, alerts | Raise with the return code and stderr. |
| `assemblyzero/speedrun/leavings.py:213` | `git status` fails in classify_dirt | returns the failure as a line of operator dirt, so it blocks as dirt but is never logged as a failure | loud, alerts | Raise or log at ERROR and alert, instead of passing it off as dirt. |
| `assemblyzero/speedrun/leavings.py:247` | preserve and remove failures when no log is passed | every failure message goes to a no-op | loud, logged, alerts | Default to an ERROR log on stderr. |
| `assemblyzero/speedrun/leavings.py:263` | read-tree/add/write-tree/commit-tree/branch/push fails during preservation | logs through the caller's log at no level, marks entries not ok, and returns; no alert | loud, alerts | Log at ERROR and call alert_operator. |
| `assemblyzero/speedrun/leavings.py:312` | preserved-branch ledger write fails | the False return is ignored, so the archiver can miss the branch | loud, logged, stops, alerts | Check the return value (or have record_preserved raise) and fail loudly. |
| `assemblyzero/speedrun/leavings.py:321` | unlinking a preserved leaving fails | records a not-ok entry and `continue`s; no ERROR, no alert | loud, alerts | Log at ERROR and alert. |
| `assemblyzero/speedrun/leavings.py:349` | rmdir of a non-empty directory | returns; this is the documented stop condition for pruning | compliant | none |
| `assemblyzero/speedrun/must_resolve.py:176` | `gh` or `git` cannot be executed | returns a CompletedProcess with rc 127, the documented contract; every caller checks returncode | compliant | none |
| `assemblyzero/speedrun/must_resolve.py:355` | the gh issue list dedupe query fails | returns None ("no existing issue"), so a duplicate issue is filed | loud, logged, stops, alerts | Raise or return a failure the filer reports, never "none found". |
| `assemblyzero/speedrun/must_resolve.py:359` | the gh issue list output is unparseable | returns None, treated as no existing issue | loud, logged, stops, alerts | Same as above. |
| `assemblyzero/speedrun/must_resolve.py:372` | `gh label create` fails | the return code is ignored | loud, logged, stops, alerts | Check the return code and report its stderr. |
| `assemblyzero/speedrun/must_resolve.py:411` | a conflict cannot be ruled on and is not filed | prints to stdout via log=print and returns "rejected"; no ERROR, no alert | loud, alerts | Log at ERROR and call alert_operator. |
| `assemblyzero/speedrun/must_resolve.py:443` | a ledger write fails for a suppressed filing | the False return is ignored | loud, logged, stops, alerts | Check the return value and fail loudly. |
| `assemblyzero/speedrun/must_resolve.py:451` | the must-resolve issue cannot be filed (no remote) | prints to stdout and returns FilingResult(failed) | loud, alerts | Log at ERROR and call alert_operator. |
| `assemblyzero/speedrun/must_resolve.py:465` | the recurrence comment fails | prints to stdout and returns failed | loud, alerts | Log at ERROR and alert. |
| `assemblyzero/speedrun/must_resolve.py:473` | the ledger write for a recurrence fails | the return value is ignored, so the launch gate may miss the open question | loud, logged, stops, alerts | Check the return value and fail loudly. |
| `assemblyzero/speedrun/must_resolve.py:498` | issue creation fails after the label retry | prints to stdout and returns failed | loud, alerts | Log at ERROR and alert. |
| `assemblyzero/speedrun/must_resolve.py:503` | the created issue's URL cannot be parsed | number None, the log prints "#?", record_filed returns False without writing, and the result is still "filed" | loud, logged, stops, alerts | Treat a missing number as a failure: ERROR plus alert. |
| `assemblyzero/speedrun/must_resolve.py:509` | the ledger write for a new filing fails | the return value is ignored | loud, logged, stops, alerts | Check the return value and fail loudly. |
| `assemblyzero/speedrun/must_resolve.py:527` | the open-question gate cannot find a remote | returns ([], error); speedrun_roll prints a WARNING and proceeds ("could not check" treated as passed) | loud, stops, alerts | Refuse the launch on error, with ERROR and alert. |
| `assemblyzero/speedrun/must_resolve.py:535` | gh issue list fails for the open-question gate | returns ([], stderr); the caller warns and proceeds | loud, stops, alerts | Same as above. |
| `assemblyzero/speedrun/must_resolve.py:539` | the gh response is unparseable | returns ([], message); the caller warns and proceeds | loud, stops, alerts | Same as above. |
| `assemblyzero/speedrun/must_resolve.py:613` | the filed-questions ledger write fails | returns False with the exception discarded | loud, logged, stops, alerts | Log at ERROR with the cause and alert. |
| `assemblyzero/speedrun/must_resolve.py:630` | the filed-questions ledger cannot be read (absent or unreadable) | returns [], so the launch gate sees no recorded questions | loud, logged, stops, alerts | Return [] only when the file is absent; raise on other OSErrors. |
| `assemblyzero/speedrun/must_resolve.py:639` | a ledger line is corrupt | `continue`s silently, uncounted, and can hide an open question | loud, logged, stops, alerts | Count it and fail or alert. |
| `assemblyzero/speedrun/must_resolve.py:721` | file_must_resolve raises | prints "continuing" to stdout and appends a failed result | loud, alerts | Log at ERROR and call alert_operator in the handler. |
| `assemblyzero/speedrun/preserved.py:97` | the preserved-branch ledger write fails | returns False; both callers (leavings, worktrees) ignore it | loud, logged, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/speedrun/preserved.py:115` | the ledger exists but cannot be read | returns [], so the archiver loses attribution silently | loud, logged, stops, alerts | Raise with the cause. |
| `assemblyzero/speedrun/preserved.py:124` | a ledger line is corrupt | `continue`s silently, uncounted | loud, logged, stops, alerts | Count it and fail or alert. |
| `assemblyzero/speedrun/preserved.py:127` | a ledger record has no branch | skipped silently | loud, logged, stops, alerts | Count it as a corrupt record and report it. |
| `assemblyzero/speedrun/prompt_ranking.py:62` | the telemetry file cannot be read (absent or unreadable) | returns [], which renders as "No validation failures recorded" | loud, logged, stops, alerts | Return [] only when the file is absent; raise otherwise. |
| `assemblyzero/speedrun/prompt_ranking.py:70` | a telemetry line is corrupt | `continue`s silently, uncounted | loud, logged, stops, alerts | Count it and fail or alert. |
| `assemblyzero/speedrun/prompt_ranking.py:80` | runs.csv cannot be read | returns {}, so every fingerprint is flagged duration-unknown without saying why | loud, logged, stops, alerts | Raise for an unreadable file; state an absent file explicitly in the output. |
| `assemblyzero/speedrun/prompt_ranking.py:89` | a runs.csv row is malformed | `continue`s silently, uncounted | loud, logged, stops, alerts | Count bad rows and fail or alert. |
| `assemblyzero/speedrun/prompt_telemetry.py:130` | a validation failure arrives with an empty detail | returns None and records nothing | loud, logged, stops, alerts | Record it under an explicit empty-detail fingerprint, or raise. |
| `assemblyzero/speedrun/prompt_telemetry.py:152` | the telemetry append fails | prints via log=print (no ERROR) and returns None | loud, stops, alerts | Log at ERROR, alert_operator, and raise. |
| `assemblyzero/speedrun/prompt_telemetry.py:180` | the telemetry file cannot be read | returns [], which the factory report counts as zero failures | loud, logged, stops, alerts | Return [] only when the file is absent; raise otherwise. |
| `assemblyzero/speedrun/prompt_telemetry.py:188` | a telemetry line is corrupt | `continue`s silently, uncounted | loud, logged, stops, alerts | Count it and fail or alert. |
| `assemblyzero/speedrun/replay.py:262` | the lineage directory for a run is ambiguous | appends a note and `continue`s; that stage kind is not replayed | loud, logged, stops, alerts | Raise, or return a failure the runner reports at ERROR. |
| `assemblyzero/speedrun/replay.py:330` | a recorded verdict file has no Verdict line | substitutes an empty verdict, which replays as a reviewer failure the recording never had | loud, logged, stops, alerts | Raise with the file path when no verdict line is found. |
| `assemblyzero/speedrun/replay.py:520` | no unique anchor for an edit script | degrades to a whole-document answer, counted and noted in Reconstruction (the documented contract) and printed by the report | compliant | none |
| `assemblyzero/speedrun/replay.py:680` | the call recording has unreadable lines | proceeds with a partial recording; only a note | loud, logged, stops, alerts | Refuse to replay from a partial recording, with ERROR and alert. |
| `assemblyzero/speedrun/replay.py:683` | the call recording is wholly unreadable | silently falls back to reconstruction, with a note | loud, logged, stops, alerts | Raise, or fail the replay with ERROR and alert. |
| `assemblyzero/speedrun/requirements_status.py:65` | writing the requirements-unverified record fails | returns False, so the UNVERIFIED banner never prints and an unchecked roll looks clean | loud, logged, stops, alerts | Log at ERROR, alert_operator, and raise. |
| `assemblyzero/speedrun/requirements_status.py:88` | a ledger line is corrupt | `continue`s silently and can drop an unverified marker | loud, logged, stops, alerts | Count it and fail or alert. |
| `assemblyzero/speedrun/requirements_status.py:90` | a ledger line is not an object | skipped silently | loud, logged, stops, alerts | Count it as corrupt and report it. |
| `assemblyzero/speedrun/restore.py:46` | `git for-each-ref` fails for leavings refs | returns [], so restore searches fewer refs and reports "not restorable" | loud, logged, stops, alerts | Raise with the return code and stderr. |
| `assemblyzero/speedrun/restore.py:83` | `git for-each-ref` fails for graveyard lld refs | returns [] | loud, logged, stops, alerts | Raise with the return code and stderr. |
| `assemblyzero/speedrun/restore.py:140` | withdrawn fail-open convention | the tag is present; returns False for an artifact outside the repo | loud, logged, stops, alerts | Remove the tag; raise ValueError for a path outside the repo. |
| `assemblyzero/speedrun/restore.py:150` | `git show` fails for any reason, not only "not on this ref" | treated as absent; the error is dropped and the loop moves to the next ref | loud, logged, stops, alerts | Tell "path not in ref" apart from other git errors and raise on the latter. |
| `assemblyzero/speedrun/roll_blockers.py:75` | `gh` cannot be executed | returns rc 127, the documented contract; callers check returncode | compliant | none |
| `assemblyzero/speedrun/roll_blockers.py:145` | a board cannot be checked (no remote) | appends to errors; `refuses` ignores errors, so the launch proceeds ("could not check" treated as passed) | loud, stops, alerts | Refuse the launch when any board could not be consulted, with ERROR and alert. |
| `assemblyzero/speedrun/roll_blockers.py:154` | gh issue list fails for a board | appends to errors and `continue`s; the launch proceeds | loud, stops, alerts | Same as above. |
| `assemblyzero/speedrun/roll_blockers.py:197` | a blocker check failed | surfaced only as a WARNING report line | loud, stops, alerts | Emit at ERROR, alert, and refuse. |
| `assemblyzero/speedrun/successes.py:58` | the success ledger cannot be read (absent or unreadable) | returns [], so the redraw guard is silently absent | loud, logged, stops, alerts | Return [] only when the file is absent; raise otherwise. |
| `assemblyzero/speedrun/successes.py:62` | the success ledger is corrupt JSON | returns []; record_success then overwrites the file with one entry, destroying the ledger | loud, logged, stops, alerts | Raise on corrupt JSON, and never rewrite over a ledger that could not be parsed. |
| `assemblyzero/speedrun/successes.py:64` | the success ledger has the wrong shape | returns [], and the next record_success overwrites it | loud, logged, stops, alerts | Raise. |
| `assemblyzero/speedrun/successes.py:102` | the success ledger write fails | returns False with the exception discarded | loud, logged, stops, alerts | Log at ERROR, alert, and raise. |
| `assemblyzero/speedrun/timing.py:91` | the heartbeat log cannot be read | returns None; the killed run's duration becomes 0 with source "unknown" | loud, logged, stops, alerts | Return None only when the file is absent; raise otherwise. |
| `assemblyzero/speedrun/timing.py:110` | an events log cannot be read | returns None, the same as "no START line", so the run is dropped from the table | loud, logged, stops, alerts | Raise with the path and the cause. |
| `assemblyzero/speedrun/timing.py:141` | the duration of a killed run cannot be determined | substitutes 0 seconds, which is then summed into the day totals | loud, logged, stops, alerts | Exclude unknown durations from the sums and report their count, or fail. |
| `assemblyzero/speedrun/timing.py:185` | `git log` fails | returns 0 commits, so a fix gap is classified as idle | loud, logged, stops, alerts | Raise with the return code and stderr. |
| `assemblyzero/speedrun/worktrees.py:97` | `git worktree list` fails | returns an empty set, so the sweep relocates every registered pipeline worktree as an orphan | loud, logged, stops, alerts | Raise with the return code and stderr before the sweep moves anything. |
| `assemblyzero/speedrun/worktrees.py:136` | `git status` fails on a worktree | treated as dirty (the preserve path), and the failure itself is not reported | loud, logged, alerts | Log at ERROR with the stderr and alert. |
| `assemblyzero/speedrun/worktrees.py:223` | rglob fails while clearing ReadOnly | `pass`; partial clearing | loud, logged, stops, alerts | Log at ERROR and raise. |
| `assemblyzero/speedrun/worktrees.py:229` | stat of a path fails | `continue`s silently | loud, logged, stops, alerts | Re-raise OSError; allow AttributeError only as the non-Windows case. |
| `assemblyzero/speedrun/worktrees.py:236` | chmod fails | `continue`s silently | loud, logged, stops, alerts | Log at ERROR and raise. |
| `assemblyzero/speedrun/worktrees.py:274` | `git add -A` fails while preserving a dirty worktree | the return code is ignored; the commit can then preserve less than the tree held | loud, logged, stops, alerts | Check the return code and return a failed entry. |
| `assemblyzero/speedrun/worktrees.py:286` | push of the graveyard branch fails | logs (no level) and continues to remove the worktree | loud, stops, alerts | Log at ERROR, alert, and do not remove the worktree. |
| `assemblyzero/speedrun/worktrees.py:295` | the preserved-branch ledger write fails | the return value is ignored | loud, logged, stops, alerts | Check the return value and fail loudly. |
| `assemblyzero/speedrun/worktrees.py:300` | worktree removal fails after preservation | returns a not-ok entry; the sweep continues with no ERROR and no alert | loud, alerts | Log at ERROR and alert. |
| `assemblyzero/speedrun/worktrees.py:315` | an orphan directory cannot be relocated | returns a not-ok entry; the sweep continues | loud, alerts | Log at ERROR and alert. |
| `assemblyzero/speedrun/worktrees.py:330` | sweep failures when no log is passed | every failure message goes to a no-op | loud, logged, alerts | Default to an ERROR log on stderr. |
| `assemblyzero/speedrun/worktrees.py:344` | removal of a clean worktree fails | records a not-ok entry; the sweep continues | loud, alerts | Log at ERROR and alert. |
| `assemblyzero/speedrun/worktrees.py:351` | an unexpected OSError while handling a worktree | converted into a not-ok entry; the sweep continues | loud, alerts | Log at ERROR, alert, and re-raise. |
| `assemblyzero/hooks/cascade_action.py:64` | creating or writing the cascade telemetry event (import, create_cascade_event, log_cascade_event) | bare `pass`; the event is lost silently and the block proceeds | loud, logged, alerts | log at ERROR with session_id and cause and call alert_operator (the block itself may still return False) |
| `assemblyzero/hooks/cascade_detector.py:81` | a cascade pattern regex fails to compile | skipped silently ("Skip invalid patterns silently"); detection runs with fewer patterns and may return allow | loud, logged, stops, alerts | raise (or log ERROR and alert) naming the pattern id and regex error instead of skipping |
| `assemblyzero/hooks/cascade_patterns.py:214` | user pattern config absent | DEBUG log, returns [] | compliant | none |
| `assemblyzero/hooks/cascade_patterns.py:221` | user pattern config present but unreadable or malformed JSON | WARNING, returns []; operator overrides silently dropped | loud, stops, alerts | raise with path and cause (a declared config that cannot load must stop detection) |
| `assemblyzero/hooks/cascade_patterns.py:228` | config top level is not a JSON object | WARNING, returns [] | loud, stops, alerts | raise a config error naming the path |
| `assemblyzero/hooks/cascade_patterns.py:237` | patterns field is not a list | WARNING, returns [] | loud, stops, alerts | raise a config error naming the path |
| `assemblyzero/hooks/cascade_patterns.py:245` | a pattern entry is not a dict | skipped with no log at all | loud, logged, stops, alerts | raise naming the entry index and path |
| `assemblyzero/hooks/cascade_patterns.py:247` | a user pattern lacks required keys | WARNING, pattern skipped, rest loaded | loud, stops, alerts | raise naming the pattern id and missing keys |
| `assemblyzero/hooks/cascade_patterns.py:252` | a user pattern regex does not compile | WARNING, pattern skipped | loud, stops, alerts | raise naming the pattern id and regex error |
| `assemblyzero/metrics/cache.py:35` | cache file content is not a JSON object | WARNING, returns {}; the next save overwrites the file, erasing every other repo's entries | loud, stops, alerts | raise with the path, or log ERROR and alert before treating it as empty |
| `assemblyzero/metrics/cache.py:38` | cache file unreadable or corrupt | WARNING, returns {}; save then overwrites the whole cache | loud, stops, alerts | raise with path and cause (or ERROR plus alert_operator) |
| `assemblyzero/metrics/cache.py:50` | chmod 0o600 on the cache file fails (permission hardening) | WARNING, continues with the file world-readable | loud, stops, alerts | raise; a failed permission restriction must not pass silently |
| `assemblyzero/metrics/cache.py:73` | cache entry's expires_at is corrupt | WARNING, treated as a cache miss | loud, alerts | log ERROR naming repo and bad value and alert, or raise |
| `assemblyzero/metrics/collector.py:49` | no GitHub token available | WARNING, continues unauthenticated; private repos then fail or rate limits truncate results | loud, stops, alerts | raise when no token is configured |
| `assemblyzero/metrics/collector.py:167` | listing an LLD directory fails (404 or any API error) | `continue` with no log; workflow counts silently partial | loud, logged, stops, alerts | treat only 404 as absent; raise CollectionError on any other GithubException |
| `assemblyzero/metrics/collector.py:186` | listing an LLD directory fails (any API error, not just 404) | DEBUG "not found", count stays 0 | loud, logged, stops, alerts | narrow to 404; raise CollectionError on other GithubException |
| `assemblyzero/metrics/collector.py:196` | ContentFile has no content | returns empty string, verdict counted in total but as neither approve nor block | loud, logged, stops, alerts | raise naming the file path |
| `assemblyzero/metrics/collector.py:213` | fetching docs/reports fails (any API error) | DEBUG, returns (0, 0, 0) | loud, logged, stops, alerts | narrow to 404; raise CollectionError otherwise |
| `assemblyzero/metrics/collector.py:234` | reading or decoding a verdict file | WARNING, file already counted in total, approval rate skewed | loud, stops, alerts | raise CollectionError with repo, path and cause |
| `assemblyzero/metrics/collector.py:238` | listing a report subdirectory fails | `continue` with no log; that directory's verdicts dropped | loud, logged, stops, alerts | raise CollectionError naming repo and directory |
| `assemblyzero/nodes/anthropic_provider.py:91` | response object cannot be dumped to a dict | substitutes {}; record carries model "unknown" and null tokens, cost estimates as 0.0 | loud, logged, stops, alerts | raise when the response lacks model_dump instead of recording empty usage |
| `assemblyzero/nodes/check_type_renames.py:135` | git grep fails (return code other than 0 or 1) | `continue` with no log; zero usages found, check can report passed | loud, logged, stops, alerts | raise with return code and stderr |
| `assemblyzero/nodes/check_type_renames.py:146` | a git grep output line does not parse | skipped silently | loud, logged, stops | raise naming the unparseable line |
| `assemblyzero/nodes/check_type_renames.py:160` | git grep line number is not an int | skipped silently | loud, logged, stops | raise naming the line |
| `assemblyzero/nodes/check_type_renames.py:171` | any error running or parsing git grep | WARNING, continue; check may report passed with no search done | loud, stops, alerts | log ERROR and raise |
| `assemblyzero/nodes/check_type_renames.py:239` | git diff --staged fails | return code never checked; empty stdout means no removed types and type_rename_check_passed=True | loud, logged, stops, alerts | check returncode and raise (or return error_message to HALT) with stderr |
| `assemblyzero/nodes/check_type_renames.py:272` | git rev-parse --show-toplevel fails (return code also unchecked) | silently falls back to Path.cwd() and searches the wrong tree | loud, logged, stops, alerts | check returncode and raise; never fall back to cwd |
| `assemblyzero/nodes/inventory.py:20` | docs directory missing or not a directory | returns []; node then writes an empty inventory table | loud, logged, stops, alerts | raise naming the missing docs dir |
| `assemblyzero/nodes/inventory.py:97` | any failure scanning or writing the inventory | prints to stdout and returns errors list with inventory_updated False; no error_message so no HALT | loud, stops, alerts | log ERROR to stderr and return error_message (routed to HALT) or raise |
| `assemblyzero/nodes/smoke_test_node.py:47` | tools/ directory missing | returns []; integration_smoke_test then reports smoke_test_passed True | loud, logged, stops, alerts | raise or return error_message when there is nothing to test |
| `assemblyzero/nodes/smoke_test_node.py:139` | the smoke-test subprocess cannot even launch (infra error) | converted to a failed SmokeTestResult, indistinguishable from a test failure, no log | loud, logged, alerts | log ERROR and raise for infrastructure errors |
| `assemblyzero/nodes/smoke_test_node.py:160` | project_root missing from state | returns smoke_test_passed False with no error_message; no ERROR log, no HALT | loud, stops, alerts | return error_message routed to HALT (or raise) |
| `assemblyzero/nodes/smoke_test_node.py:177` | zero entry points discovered | treated as a pass ("could not check" read as passed) | loud, logged, stops, alerts | fail loudly when no entry point is found |
| `assemblyzero/nodes/smoke_test_node.py:190` | one or more smoke tests failed | returns smoke_test_passed False only; no error_message, no ERROR log | loud, logged, stops, alerts | set error_message naming the failing entry points so the graph routes to HALT |
| `assemblyzero/spelunking/engine.py:129` | a probe crashes | converted to ProbeResult(passed=False, summary="Error: ..."), same as a probe that found drift; no log | loud, logged, stops, alerts | log ERROR and raise (a crashed probe is not a finding) |
| `assemblyzero/spelunking/engine.py:156` | a probe crashes during run_all_probes | converted to a failed ProbeResult and the loop continues; no log | loud, logged, stops, alerts | log ERROR, alert and raise |
| `assemblyzero/spelunking/extractors.py:84` | target document does not exist | returns no claims; run_spelunking yields an empty report whose drift_score is 100.0 (PASS) | loud, logged, stops, alerts | raise FileNotFoundError naming the document |
| `assemblyzero/spelunking/models.py:89` | no verifiable claims (all unverifiable or none extracted) | drift score 100.0, reported as PASS | loud, logged, stops, alerts | return a value the report renders as cannot-check (or raise), never 100 |
| `assemblyzero/spelunking/verifiers.py:41` | no verifier exists for the claim type (STATUS_MARKER) | marked UNVERIFIABLE, which drift_score excludes | loud, logged, stops, alerts | raise for an unsupported claim type |
| `assemblyzero/spelunking/verifiers.py:49` | a verifier crashes | status ERROR with error_message; no log, run continues | loud, logged, alerts | log ERROR and raise |
| `assemblyzero/spelunking/verifiers.py:106` | directory named in a count claim is missing | status ERROR result, no log | loud, logged, alerts | log ERROR or raise naming the directory |
| `assemblyzero/spelunking/verifiers.py:206` | a source file cannot be read during the absence grep | skipped silently; claim can be reported MATCH (term absent) without checking that file | loud, logged, stops, alerts | raise with the path and cause |
| `assemblyzero/spelunking/verifiers.py:251` | directory for a unique-prefix claim missing | status ERROR result, no log | loud, logged, alerts | log ERROR or raise naming the directory |
| `assemblyzero/spelunking/verifiers.py:310` | claimed date does not parse | status ERROR result, no log | loud, logged, alerts | log ERROR or raise naming the date and source line |
| `assemblyzero/telemetry/actor.py:34` | gh auth status fails (return code never checked) | output scanned anyway; falls through to "unknown" | loud, logged, stops, alerts | check returncode and raise with stderr |
| `assemblyzero/telemetry/actor.py:48` | gh missing, timeout, or parse failure | `pass`, caches "unknown" for the process lifetime | loud, logged, stops, alerts | log ERROR and raise (or alert) instead of caching "unknown" |
| `assemblyzero/telemetry/cascade_events.py:72` | writing the cascade event to JSONL fails | plain print to stderr (not ERROR level), event lost, continues | loud, stops, alerts | log ERROR with path and alert_operator; raise |
| `assemblyzero/telemetry/cascade_events.py:152` | a log line is corrupt | skipped silently; stats undercount | loud, logged, stops, alerts | raise naming the line number |
| `assemblyzero/telemetry/cascade_events.py:161` | event timestamp invalid | skipped silently | loud, logged, stops, alerts | raise naming the line |
| `assemblyzero/telemetry/cascade_events.py:170` | reading the event log fails | WARNING, returns partial or zero stats | loud, stops, alerts | raise with path and cause |
| `assemblyzero/telemetry/cost.py:73` | no cost entry for the model | WARNING, returns 0.0, indistinguishable from a free call in cost records | loud, stops, alerts | raise for an unknown model, or return None that callers must handle |
| `assemblyzero/telemetry/emitter.py:54` | telemetry credentials file missing | returns None silently; events go only to the local buffer | loud, logged, alerts | log ERROR once and alert when telemetry is enabled but credentials are absent |
| `assemblyzero/telemetry/emitter.py:68` | boto3 import, credentials parse, or DynamoDB client init fails | returns None silently | loud, logged, stops, alerts | log ERROR with cause and alert_operator |
| `assemblyzero/telemetry/emitter.py:84` | writing to the local buffer fails | `pass`; event dropped entirely | loud, logged, stops, alerts | log ERROR and alert_operator; raise |
| `assemblyzero/telemetry/emitter.py:151` | DynamoDB put_item fails | `pass`, falls through to the buffer | loud, logged, alerts | log ERROR with cause before falling back |
| `assemblyzero/telemetry/emitter.py:156` | building or emitting the event fails | `pass` | loud, logged, stops, alerts | log ERROR and alert_operator |
| `assemblyzero/telemetry/emitter.py:171` | no DynamoDB client during flush | returns 0; sync CLI prints "No buffered events to sync." | loud, logged, stops, alerts | raise when the client cannot be built |
| `assemblyzero/telemetry/emitter.py:192` | a buffered event fails to parse or upload | kept for retry, no log | loud, logged, alerts | log ERROR with the cause |
| `assemblyzero/telemetry/emitter.py:200` | reading or rewriting a buffer file fails | `continue` silently | loud, logged, stops, alerts | log ERROR and raise |
| `assemblyzero/telemetry/emitter.py:203` | the flush as a whole fails | `pass`, returns partial count | loud, logged, stops, alerts | log ERROR and raise |
| `assemblyzero/telemetry/emitter.py:237` | the tracked tool raises | emits tool.error and re-raises | compliant | none |
| `assemblyzero/telemetry/store.py:71` | writing an LLM call record fails | WARNING with traceback, record lost, continues | loud, stops, alerts | log ERROR and alert_operator; raise |
| `assemblyzero/telemetry/store.py:88` | corrupt JSONL line in read_day | WARNING, line skipped, partial result | loud, stops, alerts | raise naming file and line |
| `assemblyzero/telemetry/store.py:114` | telemetry filename has an unparseable date | file skipped silently in query | loud, logged, stops | raise naming the file |
| `assemblyzero/telemetry/store.py:127` | corrupt JSONL line in query | skipped silently, partial result | loud, logged, stops, alerts | raise naming file and line |
| `assemblyzero/telemetry/sync.py:13` | flush returns 0 after swallowed failures (no client, read errors) | treated as success | loud, logged, stops, alerts | have flush raise and let main exit non-zero |
| `assemblyzero/telemetry/sync.py:17` | sync could not run or uploaded nothing | prints a success-sounding line to stdout and exits 0 | loud, logged, stops, alerts | distinguish empty buffer from failure and exit non-zero on failure |
| `assemblyzero/utils/ast_sentinel.py:472` | target file does not parse | returned as a SentinelError finding; the only caller (validate_mechanical.py:1512) downgrades it to a WARNING "symbol '<syntax>' may not be imported" | loud, logged, stops, alerts | raise; a parse failure is not an undefined-symbol finding |
| `assemblyzero/utils/ast_sentinel.py:498` | target file cannot be read | returned as a SentinelError finding; the caller downgrades it to an advisory WARNING | loud, logged, stops, alerts | raise with path and cause |
| `assemblyzero/utils/codebase_reader.py:152` | stat of the file fails | DEBUG, returns empty result; read_files_within_budget drops the file silently | loud, stops, alerts | raise with path and cause |
| `assemblyzero/utils/codebase_reader.py:164` | symlink resolves outside the repo | WARNING, returns empty result, file silently dropped | loud, stops, alerts | raise a security error naming both paths |
| `assemblyzero/utils/codebase_reader.py:171` | path resolve fails | DEBUG, returns empty result | loud, stops, alerts | raise with path and cause |
| `assemblyzero/utils/codebase_reader.py:198` | file not decodable as UTF-8 | DEBUG, treated as binary and dropped | loud, alerts | log ERROR or raise for non-binary-extension files that fail to decode |
| `assemblyzero/utils/codebase_reader.py:201` | reading the file fails | DEBUG, returns empty result; file dropped from LLM context | loud, stops, alerts | raise with path and cause |
| `assemblyzero/utils/codebase_reader.py:340` | pyproject.toml present but fails to parse | DEBUG, falls through to package.json or {} | loud, stops, alerts | raise naming the file and parse error |
| `assemblyzero/utils/codebase_reader.py:369` | package.json present but fails to parse | DEBUG, returns {} | loud, stops, alerts | raise naming the file and parse error |
| `assemblyzero/utils/git.py:50` | git rev-parse fails | raises GitBranchError with stderr | compliant | none |
| `assemblyzero/utils/git.py:56` | detached HEAD | raises GitBranchError | compliant | none |
| `assemblyzero/utils/github_metrics_client.py:59` | GitHub call fails after three attempts | tenacity raises RetryError (no reraise=True), so the original exception is wrapped and nothing logs the exhaustion | loud, logged | pass reraise=True and log ERROR on exhaustion |
| `assemblyzero/utils/github_metrics_client.py:151` | path does not exist (404) | DEBUG, returns [] | compliant | none |
| `assemblyzero/utils/github_metrics_client.py:188` | rate-limit status fetch fails | WARNING, returns remaining=0 limit=0, which reads as exhausted | loud, stops, alerts | raise with cause |
| `assemblyzero/utils/lld_path_enforcer.py:97` | LLD has no Section 2.1 | returns an empty spec silently; prompt section and path advisory both go empty | loud, logged, stops, alerts | raise naming the LLD as missing Section 2.1 |
| `assemblyzero/utils/lld_verification.py:282` | path comparison fails | raises LLDVerificationError | compliant | none |
| `assemblyzero/utils/lld_verification.py:307` | no project_root passed | path-traversal security check skipped entirely, gate continues | loud, logged, stops, alerts | always validate (default to repo root) or raise when project_root is missing |
| `assemblyzero/utils/markdown_inventory.py:31` | existing inventory lacks the bounding tags | returns []; every hand-set status is reset when the node rewrites the table | loud, logged, stops, alerts | raise when the file exists but its tags are missing |
| `assemblyzero/utils/markdown_inventory.py:44` | inventory row has too few cells | row dropped silently; its entry lost on rewrite | loud, logged, stops, alerts | raise naming the malformed row |
| `assemblyzero/utils/metrics_aggregator.py:73` | issue metrics collection fails | WARNING, zeroed metrics substituted into the report | loud, stops, alerts | raise, or record the repo in repos_failed and log ERROR plus alert |
| `assemblyzero/utils/metrics_aggregator.py:82` | workflow metrics collection fails | WARNING, zeroed metrics substituted | loud, stops, alerts | raise, or record the repo as failed and alert |
| `assemblyzero/utils/metrics_aggregator.py:93` | Gemini metrics collection fails | WARNING, zeroed metrics substituted | loud, stops, alerts | raise, or record the repo as failed and alert |
| `assemblyzero/utils/metrics_aggregator.py:158` | issue timestamps fail to parse | `pass`; close time silently omitted from the average | loud, logged, stops, alerts | raise naming the issue number |
| `assemblyzero/utils/metrics_aggregator.py:243` | fetching issues for label counts fails | DEBUG, counts stay 0 | loud, stops, alerts | raise with repo and cause |
| `assemblyzero/utils/metrics_aggregator.py:297` | verdict file name carries no approve or block marker | counted as an approval by default (fabricated outcome) | loud, logged, stops, alerts | count as unknown or raise; never default to approval |
| `assemblyzero/utils/process.py:33` | taskkill fails to kill the tree (return code never checked) | ignored; grandchildren may survive holding pipes (the #1874 hang) | loud, logged, stops, alerts | check returncode, treating only "not found" as success, and raise otherwise |
| `assemblyzero/utils/process.py:41` | killpg fails with EPERM or another OSError, or taskkill times out | `pass`, same as already-dead | loud, logged, stops, alerts | swallow only ProcessLookupError; log ERROR and raise for the rest |
| `assemblyzero/utils/retry.py:220` | retries exhausted or failure not worth retrying | prints halt line to stdout, logs at INFO, returns the failed LLMCallResult | loud, alerts | log at ERROR to stderr with description and cause; callers must route result.success False to HALT |
| `assemblyzero/utils/shell.py:110` | the command exits non-zero | returns CompletedProcess without checking returncode | compliant | none |
| `assemblyzero/utils/speedrun.py:144` | writing the lap-split file fails | WARNING, continues; split record lost | loud, stops, alerts | log ERROR with path and alert_operator; raise |
| `assemblyzero/utils/speedrun.py:320` | appending the run-log entry fails | WARNING, the durable cross-attempt record is lost | loud, stops, alerts | log ERROR and raise |
| `assemblyzero/utils/speedrun.py:335` | malformed run-log line | WARNING, skipped, partial history returned | loud, stops, alerts | raise naming the line |
| `assemblyzero/utils/workflow_timeout.py:74` | workflow exceeds its wall-clock timeout | prints a stderr banner (not an ERROR log record) and hard-exits 42, never reaching alert_operator | loud, logged, alerts | call alert_operator (what, where, issue, cause, consequence) before os._exit |
| `assemblyzero/visual_gate/config.py:77` | declared gate has no renderer_cmd | defaults to an empty command, which fails only later at render time | loud, logged, stops, alerts | raise at load naming the missing required key |
| `assemblyzero/visual_gate/config.py:79` | declared gate has no separation_floor | defaults to 0, which disables the palette-floor guardrail silently | loud, logged, stops, alerts | raise at load when separation_floor is absent |
| `assemblyzero/visual_gate/gate.py:87` | webbrowser.open reports failure | one stdout log line, wait proceeds | loud, logged, alerts | log at ERROR to stderr and alert_operator (summoning the operator is the gate's job) |
| `assemblyzero/visual_gate/gate.py:88` | browser auto-open raises | one stdout line, continues | loud, logged, alerts | log ERROR and call alert_operator; remove the fail-open tag |
| `assemblyzero/visual_gate/gate.py:89` | `# fail-open:` tag (withdrawn convention) | present | loud, logged, stops, alerts | delete the tag and make the handler meet the standard |
| `assemblyzero/visual_gate/gate.py:271` | a git step of the ruling codification fails | returns error string; run_gate returns halted and the orchestrator marks the stage failed (stages.py:1033) | compliant | none |
| `assemblyzero/visual_gate/gate.py:369` | codification failed after stamp_approved already wrote approved.json (line 430 runs before 440) | on resume the gate reports "approved" and passes, so the failed codification is skipped forever | loud, logged, stops, alerts | stamp approved.json only after codification succeeds, or record and check a codified marker before the shortcut |
| `assemblyzero/visual_gate/gate.py:386` | renderer failed or bundle incomplete | returns halted outcome; the orchestrator turns it into a failed stage | compliant | none |
| `assemblyzero/visual_gate/gate.py:446` | codification failed | feedback is consumed before the error is checked, so a resume cannot re-dispatch it (compounds line 369) | stops | leave feedback unconsumed when codification fails |
| `assemblyzero/visual_gate/gate.py:485` | Modify model pass raises | returns halted outcome (orchestrator marks the stage failed); no ERROR log at the point of failure | loud, logged | log ERROR with exception type at the point of failure; remove the fail-open tag |
| `assemblyzero/visual_gate/gate.py:486` | `# fail-open:` tag (withdrawn convention) | present | loud, logged, stops, alerts | delete the tag |
| `assemblyzero/visual_gate/server.py:73` | HTTP handler errors (log_error routes here) | all server error logging suppressed | loud, logged, alerts | override only access logging and keep log_error at ERROR |
| `assemblyzero/visual_gate/server.py:242` | operator toast notification fails | one stdout log line, wait continues | loud, logged, alerts | log ERROR to stderr and escalate through alert_operator |
| `assemblyzero/visual_gate/server.py:264` | backstop email to the operator fails | one stdout log line, returns; the email is never retried | loud, logged, stops, alerts | raise AlertDeliveryError (or alert through alert_operator) per the standard |
| `assemblyzero/visual_gate/server.py:284` | pending sentinel unreadable or corrupt | returns "" | loud, logged, alerts | log ERROR with path and cause before falling back; remove the fail-open tag |
| `assemblyzero/visual_gate/server.py:285` | `# fail-open:` tag (withdrawn convention) | present | loud, logged, stops, alerts | delete the tag |
| `tools/_pat_session.py:143` | encrypted classic PAT file missing | raises FileNotFoundError with setup text | alerts | library raise is correct; every calling tool's entry handler must call alert_operator |
| `tools/_pat_session.py:178` | gpg decrypt of classic PAT fails MAX_GPG_ATTEMPTS times | raises RuntimeError carrying last gpg stderr | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:243` | Cerberus PEM file missing | raises FileNotFoundError | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:279` | Cerberus PEM decrypt retries exhausted | raises RuntimeError with last stderr | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:324` | missing or declined pr-sentinel credential | docstring instructs callers to treat it as "unverifiable, not failed" | loud, stops, alerts | rewrite the contract: missing/declined credential is a failure callers must raise on |
| `tools/_pat_session.py:334` | pr-sentinel bundle missing | raises FileNotFoundError | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:362` | operator cancels pinentry | raises RuntimeError | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:375` | pr-sentinel decrypt retries exhausted | raises RuntimeError with last stderr | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:413` | generic secret file missing | raises FileNotFoundError | alerts | caller entry handlers must route to alert_operator |
| `tools/_pat_session.py:442` | generic secret decrypt retries exhausted | raises RuntimeError with last stderr | alerts | caller entry handlers must route to alert_operator |
| `tools/audit_fleet_branch_protection.py:130` | gh repo list fails | message on stderr, exit 1 | alerts | call alert_operator before exiting |
| `tools/audit_fleet_branch_protection.py:132` | gh returns empty stdout | treated as zero repos; prints "All audited repos pass" and exits 0 | loud, logged, stops, alerts | raise when the listing is empty |
| `tools/audit_fleet_branch_protection.py:145` | network error on a GitHub GET | returns (0, {"_error"}); caller records UNKNOWN and drops the message | loud, logged, stops, alerts | log ERROR with repo and cause and count it as a failure |
| `tools/audit_fleet_branch_protection.py:149` | non-JSON response body | body=None; repo becomes UNKNOWN | loud, logged, stops, alerts | raise with status and body excerpt |
| `tools/audit_fleet_branch_protection.py:186` | repo has no default branch | classified UNKNOWN, never counted as failing | loud, stops, alerts | count UNKNOWN as failure |
| `tools/audit_fleet_branch_protection.py:201` | fallback GET /branches/{default} fails | protected_flag left None so repo is mislabelled WEAK, error lost | loud, logged, stops, alerts | set an error when the fallback GET fails |
| `tools/audit_fleet_branch_protection.py:228` | rulesets GET fails | ruleset_count silently blank | loud, logged | record the rulesets error in the verdict |
| `tools/audit_fleet_branch_protection.py:255` | requested repos not found | WARNING, continues, can exit 0 | loud, stops, alerts | ERROR and exit non-zero |
| `tools/audit_fleet_branch_protection.py:295` | repos whose audit could not run (UNKNOWN) | excluded; tool prints "All audited repos pass" and exits 0 | loud, stops, alerts | include UNKNOWN in the failing set |
| `tools/audit_fleet_branch_protection.py:301` | policy failures found | summary on stdout, exit 2 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/audit_fleet_branch_protection.py:308` | any unhandled exception (PAT decrypt, TSV write) | traceback, non-zero, no alert | alerts | wrap main in a handler that calls alert_operator |
| `tools/backfill_assemblyzero_flag.py:104` | .unleashed.json unreadable or malformed | returns False; repo reported ALREADY_TRUE | loud, logged, stops, alerts | raise with path and cause |
| `tools/backfill_assemblyzero_flag.py:129` | Projects root missing | returns []; main prints "No repos" and exits 0 | loud, logged, stops, alerts | raise |
| `tools/backfill_assemblyzero_flag.py:156` | git status fails (is_working_tree_clean) | returns False as if dirty | loud, logged, stops, alerts | raise with stderr |
| `tools/backfill_assemblyzero_flag.py:171` | git status on .unleashed.json fails | returns False; reported as "uncommitted changes" (wrong cause), SKIPPED not error, exit 0 | loud, logged, stops, alerts | raise with stderr |
| `tools/backfill_assemblyzero_flag.py:179` | git rev-parse fails | returns None; repo SKIPPED_UNSAFE, exit 0 | loud, logged, stops, alerts | raise with stderr |
| `tools/backfill_assemblyzero_flag.py:205` | git remote get-url fails | returns None; SKIPPED_NO_GH, exit 0 | loud, logged, stops, alerts | raise with stderr |
| `tools/backfill_assemblyzero_flag.py:224` | gh api call fails each poll | return code ignored, polls to timeout | loud, logged | check returncode and raise |
| `tools/backfill_assemblyzero_flag.py:244` | safety precondition fails | not counted as error, exit 0 | loud, stops, alerts | count as error and exit non-zero |
| `tools/backfill_assemblyzero_flag.py:251` | checkout main fails | return code ignored, flow continues | loud, logged, stops, alerts | check returncode and stop |
| `tools/backfill_assemblyzero_flag.py:252` | fetch fails | ignored; branch cut from stale main | loud, logged, stops, alerts | check returncode and stop |
| `tools/backfill_assemblyzero_flag.py:253` | ff-only merge fails | ignored | loud, logged, stops, alerts | check returncode and stop |
| `tools/backfill_assemblyzero_flag.py:269` | git add fails | ignored | loud, logged, stops, alerts | check returncode |
| `tools/backfill_assemblyzero_flag.py:279` | rollback unstage fails | ignored | loud, logged | check returncode and report |
| `tools/backfill_assemblyzero_flag.py:281` | rollback branch delete fails | ignored, branch left behind | loud, logged | check returncode and report |
| `tools/backfill_assemblyzero_flag.py:290` | checkout after push failure fails | ignored | loud, logged | check returncode and report |
| `tools/backfill_assemblyzero_flag.py:306` | gh pr create returns empty stdout | IndexError traceback, no context | logged, alerts | check for empty output and raise with detail |
| `tools/backfill_assemblyzero_flag.py:310` | PR number unparseable | ERROR_PR_PARSE result printed to stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/backfill_assemblyzero_flag.py:327` | post-merge cleanup checkout fails | ignored, reported MERGED | loud, logged | check returncode |
| `tools/backfill_assemblyzero_flag.py:330` | branch cleanup fails | ignored | loud, logged | check returncode |
| `tools/backfill_assemblyzero_flag.py:352` | --repos names nothing that exists | prints "No repos" to stdout, exit 0 | loud, stops, alerts | exit non-zero when requested repos are missing |
| `tools/backfill_assemblyzero_flag.py:364` | per-repo ERROR_* results | printed to stdout only | loud | write errors to stderr at ERROR |
| `tools/backfill_assemblyzero_flag.py:391` | one or more repos errored | exit 2, no alert | alerts | call alert_operator |
| `tools/batch_cleanup_quality_hooks.py:86` | settings.json malformed | returns False; hook files already deleted while settings still reference them, PR proceeds | loud, logged, stops, alerts | raise before any file is removed |
| `tools/batch_cleanup_quality_hooks.py:149` | no default branch found | status string on stdout, exit 1 at end | loud, alerts | ERROR to stderr and alert_operator |
| `tools/batch_cleanup_quality_hooks.py:152` | pull fails | ignored; branch cut from stale base | loud, logged, stops, alerts | use check=True |
| `tools/batch_cleanup_quality_hooks.py:258` | any per-repo step fails, possibly after issue/branch created | stdout ERROR line, partial state left, loop continues | loud, logged, alerts | ERROR to stderr naming partial state and alert_operator |
| `tools/batch_cleanup_quality_hooks.py:276` | errors occurred | exit 1, no alert | alerts | call alert_operator |
| `tools/batch_deploy_hooks.py:101` | settings.json malformed | returns False; repo treated as unpatched and redeployed | loud, logged, stops, alerts | raise |
| `tools/batch_deploy_hooks.py:135` | neither main nor master exists | falls back to current HEAD as the base | loud, logged, stops | raise when no default branch resolves |
| `tools/batch_deploy_hooks.py:208` | pull fails | ignored | loud, logged, stops, alerts | use check=True |
| `tools/batch_deploy_hooks.py:243` | existing settings.json malformed | set to None, then whole file overwritten, losing content | loud, logged, stops, alerts | raise instead of overwriting |
| `tools/batch_deploy_hooks.py:328` | any per-repo step fails | stdout ERROR, continues, partial state | loud, logged, alerts | ERROR to stderr and alert_operator |
| `tools/batch_deploy_hooks.py:354` | errors occurred | exit 1, no alert | alerts | call alert_operator |
| `tools/check_requirements_form.py:91` | issue/file cannot be read | ERROR line on stderr, exit 2 | alerts | call alert_operator |
| `tools/check_requirements_form.py:102` | other exceptions (gh failure, OSError, decode error) | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/collect-cross-project-metrics.py:106` | config cannot load | logger.error, return 2 | alerts | call alert_operator |
| `tools/collect-cross-project-metrics.py:113` | token env var empty | WARNING, continues; private repos then fail | loud, stops, alerts | ERROR and stop |
| `tools/collect-cross-project-metrics.py:145` | a repo's metrics collection fails | WARNING, continues, partial snapshot written | loud, stops, alerts | ERROR, write no partial output, alert |
| `tools/collect-cross-project-metrics.py:151` | every repo failed | ERROR, return 2 | alerts | call alert_operator |
| `tools/collect-cross-project-metrics.py:189` | some repos failed | exit 1 after partial snapshot and markdown already written | stops, alerts | write nothing on partial failure and alert |
| `tools/collect-cross-project-metrics.py:194` | unhandled exceptions (write_snapshot, cache) | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/compare_profiles.py:94` | records file unreadable/missing | returns []; empty table written, exit 0 | loud, logged, stops, alerts | raise with path and cause |
| `tools/compare_profiles.py:102` | malformed JSONL line | skipped silently | loud, logged, stops, alerts | raise or exit non-zero with file:line |
| `tools/compare_profiles.py:103` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/compare_profiles.py:114` | timestamp unparseable | returns None; stage time silently dropped | loud, logged, stops | raise with the bad value |
| `tools/compare_profiles.py:121` | review response not JSON | returns ""; counted as "unparsed" in table | loud, logged | ERROR naming the call row |
| `tools/compare_profiles.py:131` | answer-key audit unreadable | empty set; coverage reported as 0 | loud, logged, stops, alerts | raise |
| `tools/compare_profiles.py:279` | any of the above degraded reads | exit 0 regardless | stops, alerts | exit non-zero when any read failed |
| `tools/dependabot_morning_status.py:57` | scheduled-task log missing | stdout note, exit 0 | loud, stops, alerts | ERROR and exit non-zero |
| `tools/dependabot_morning_status.py:64` | log empty | stdout note, exit 0 | loud, stops, alerts | ERROR and exit non-zero |
| `tools/dependabot_morning_status.py:76` | nightly run exited non-zero | stdout verdict only, exit 0 | loud, stops, alerts | exit non-zero and alert_operator |
| `tools/dependabot_morning_status.py:78` | nightly wrapper error | stdout verdict only, exit 0 | loud, stops, alerts | exit non-zero and alert_operator |
| `tools/dependabot_morning_status.py:96` | gh search (open PRs) fails | stdout line, section returns, exit 0 | loud, stops, alerts | ERROR to stderr and exit non-zero |
| `tools/dependabot_morning_status.py:99` | gh returns empty stdout | reported as count 0 | loud, logged, stops | raise on empty output |
| `tools/dependabot_morning_status.py:117` | gh api review count fails | stdout line, exit 0 | loud, stops, alerts | ERROR and exit non-zero |
| `tools/dependabot_morning_status.py:120` | empty count output | prints "?" | loud, logged, stops | raise on empty output |
| `tools/dependabot_morning_status.py:134` | gh search (closed PRs) fails | stdout line, exit 0 | loud, stops, alerts | ERROR and exit non-zero |
| `tools/dependabot_morning_status.py:177` | any section failed | exit 0 always | stops, alerts | track failures and exit non-zero |
| `tools/deploy_auto_reviewer_fleet.py:79` | gh call times out | returns (1, "TIMEOUT"); callers treat any rc!=0 inconsistently (e.g. as "no protection") | loud, logged, stops, alerts | raise TimeoutExpired with the command |
| `tools/deploy_auto_reviewer_fleet.py:81` | gh CLI not installed | returns (1, msg) | loud, stops, alerts | raise |
| `tools/deploy_auto_reviewer_fleet.py:86` | gh auth status fails | rc ignored; token type "unknown" | loud, logged, stops | check rc and raise |
| `tools/deploy_auto_reviewer_fleet.py:103` | repo listing fails | stdout ERROR, returns [], then exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_fleet.py:129` | sha lookup fails for a reason other than 404 | treated as new file, PUT without sha | loud, logged, stops | distinguish 404 from error and raise |
| `tools/deploy_auto_reviewer_fleet.py:133` | DELETE enforce_admins fails | result ignored | loud, logged, stops, alerts | check rc and stop |
| `tools/deploy_auto_reviewer_fleet.py:149` | re-enabling enforce_admins fails | result ignored; protection silently left weakened | loud, logged, stops, alerts | check rc, ERROR and alert_operator |
| `tools/deploy_auto_reviewer_fleet.py:168` | GET protection fails for any reason | treated as "no protection", existing protection overwritten from scratch | loud, logged, stops, alerts | only 404 means absent; raise otherwise |
| `tools/deploy_auto_reviewer_fleet.py:195` | protection response unparseable | (False, msg) recorded, stdout, exit 2 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_fleet.py:317` | token type unknown | WARNING, proceeds | loud, stops, alerts | refuse and exit non-zero |
| `tools/deploy_auto_reviewer_fleet.py:324` | no repos found | exit 1 with no failure message | loud, logged, alerts | ERROR with cause and alert_operator |
| `tools/deploy_auto_reviewer_fleet.py:336` | default branch missing | defaults to "main" | loud, logged, stops | raise when the default branch is unknown |
| `tools/deploy_auto_reviewer_fleet.py:412` | workflow or review failures | exit 2 after stdout summary | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_fleet.py:416` | unhandled exceptions (report write) | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/deploy_auto_reviewer_poll_fix.py:285` | HTTP 404 | returns (404, {}); callers at 322 and 347 do not check status and crash on KeyError | logged, alerts | callers must check status and raise with context |
| `tools/deploy_auto_reviewer_poll_fix.py:289` | non-404 HTTP error | SystemExit with detail on stderr, exit 1 | alerts | call alert_operator before exiting |
| `tools/deploy_auto_reviewer_poll_fix.py:302` | payload verification fails | SystemExit on stderr | alerts | call alert_operator |
| `tools/deploy_auto_reviewer_poll_fix.py:304` | payload has CRLF | SystemExit on stderr | alerts | call alert_operator |
| `tools/deploy_auto_reviewer_poll_fix.py:323` | main ref GET returned 404 | KeyError traceback with no context | logged, alerts | check status and raise with detail |
| `tools/deploy_auto_reviewer_poll_fix.py:363` | URLError and other exceptions | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/deploy_auto_reviewer_workflow.py:116` | repo GET network error | returns None; cause discarded; caller prints generic stdout ERROR | loud, logged, alerts | return/raise with cause and log ERROR to stderr |
| `tools/deploy_auto_reviewer_workflow.py:118` | repo GET non-2xx | returns None; status discarded | loud, logged, alerts | raise with status and body |
| `tools/deploy_auto_reviewer_workflow.py:132` | workflow file GET network error | (None, None); cause discarded | loud, logged, alerts | raise with cause |
| `tools/deploy_auto_reviewer_workflow.py:136` | workflow file GET unexpected status | (None, None); status discarded | loud, logged, alerts | raise with status and body |
| `tools/deploy_auto_reviewer_workflow.py:165` | PUT network error | (False, msg); caller prints FAILED to stdout, exit 2 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:189` | GET protection network error | (None, msg); repo aborted, stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:224` | DELETE enforce_admins network error | (False, msg); stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:239` | POST enforce_admins (restore) network error | (False, msg) | loud, alerts | ERROR and alert_operator (protection weakened) |
| `tools/deploy_auto_reviewer_workflow.py:290` | GET rulesets network error | ([], msg) | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:299` | rulesets response not a list | returns ([], None): treated as no rulesets, direct PUT attempted | loud, logged, stops, alerts | raise on unexpected shape |
| `tools/deploy_auto_reviewer_workflow.py:311` | ruleset summary has no id | skipped silently | loud, logged, stops | raise |
| `tools/deploy_auto_reviewer_workflow.py:318` | GET ruleset detail network error | ([], msg) | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:350` | add-bypass GET network error | (False, None, msg) | loud, alerts | ERROR and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:379` | add-bypass PUT network error | (False, original, msg) | loud, alerts | ERROR and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:399` | restore-bypass GET network error | (False, msg) | loud, alerts | ERROR and alert_operator (ruleset weakened) |
| `tools/deploy_auto_reviewer_workflow.py:412` | restore-bypass PUT network error | (False, msg) | loud, alerts | ERROR and alert_operator (ruleset weakened) |
| `tools/deploy_auto_reviewer_workflow.py:484` | emergency unwind fails, protection left weakened | failure folded into a returned string printed on stdout | loud, alerts | ERROR to stderr with recovery and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:507` | restoring ruleset bypass_actors fails | CRITICAL line on stderr, continues | alerts | call alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:523` | restoring enforce_admins fails | CRITICAL line on stderr, continues | alerts | call alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:597` | default branch unresolved | stdout, repo counted failed | loud, logged, alerts | stderr ERROR with cause and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:603` | workflow state unknown | stdout, repo counted failed | loud, logged, alerts | stderr ERROR with cause and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:625` | deploy failed | stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/deploy_auto_reviewer_workflow.py:638` | failures occurred | exit 2, no alert | alerts | call alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:168` | file-on-main GET fails | HTTPError traceback, exit 1 | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:180` | branch GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:193` | file-on-branch GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:204` | open PR query fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:218` | main head GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:229` | branch create fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:246` | Contents PUT fails (branch already created) | HTTPError traceback, partial state | alerts | entry handler calls alert_operator naming partial state |
| `tools/deploy_boostgauge_landing_workflow.py:261` | PR create fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/deploy_boostgauge_landing_workflow.py:320` | any exception | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/enable_wikis.py:57` | gh repo list fails | CalledProcessError traceback; captured stderr never shown | logged, alerts | catch, log stderr at ERROR, alert, re-raise |
| `tools/enable_wikis.py:63` | unexpected gh output line | ValueError traceback | logged, alerts | raise with the offending line |
| `tools/enable_wikis.py:70` | network exception mid-fleet | unhandled, loop aborts, partial run, no summary | logged, alerts | catch per repo, ERROR, alert, exit non-zero |
| `tools/enable_wikis.py:78` | PATCH non-200 | (False, detail) printed FAILED on stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/enable_wikis.py:119` | any repo failed | exit 1, no alert | alerts | call alert_operator |
| `tools/fix_gemini_ack.py:72` | gh auth token fails | CalledProcessError traceback, stderr hidden | logged, alerts | log stderr at ERROR and alert |
| `tools/fix_gemini_ack.py:104` | GEMINI.md GET fails | HTTPError aborts discovery or fix | alerts | entry handler calls alert_operator |
| `tools/fix_gemini_ack.py:120` | repo listing page fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/fix_gemini_ack.py:145` | mergeable poll fails | HTTPError, caught per repo | alerts | call alert_operator |
| `tools/fix_gemini_ack.py:150` | mergeable wait times out | returns last state as a value | loud, stops, alerts | raise on timeout |
| `tools/fix_gemini_ack.py:192` | PR never became mergeable | stdout status, not counted as failure, exit 0 | loud, stops, alerts | count as failure and exit non-zero |
| `tools/fix_gemini_ack.py:228` | any per-repo failure | stdout ERROR, continues | loud, alerts | ERROR to stderr and alert_operator |
| `tools/fix_gemini_ack.py:235` | failures occurred | exit 1, no alert | alerts | call alert_operator |
| `tools/fix_requires_python.py:64` | gh auth token fails | CalledProcessError traceback, stderr hidden | logged, alerts | log stderr at ERROR and alert |
| `tools/fix_requires_python.py:98` | pyproject GET fails | HTTPError aborts discovery | alerts | entry handler calls alert_operator |
| `tools/fix_requires_python.py:114` | normalizer output has no requires-python | silently returns the invalid original spec | loud, logged, stops, alerts | raise when normalization fails |
| `tools/fix_requires_python.py:129` | repo listing page fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/fix_requires_python.py:156` | mergeable poll fails | HTTPError caught per repo | alerts | call alert_operator |
| `tools/fix_requires_python.py:177` | normalizer left a known-invalid caret spec unchanged | reported as skipped, success | loud, logged, stops, alerts | treat as failure and raise |
| `tools/fix_requires_python.py:207` | PR never mergeable | not counted as failure, exit 0 | loud, stops, alerts | count as failure |
| `tools/fix_requires_python.py:245` | any per-repo failure | stdout ERROR, continues | loud, alerts | ERROR to stderr and alert_operator |
| `tools/fix_requires_python.py:252` | failures occurred | exit 1, no alert | alerts | call alert_operator |
| `tools/fleet_set_permission_mode.py:130` | code search fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/fleet_set_permission_mode.py:131` | search results exceed one page or are incomplete | silently truncated to first page | loud, logged, stops | paginate and raise on incomplete_results |
| `tools/fleet_set_permission_mode.py:171` | .unleashed.json malformed | returns False (not set) | loud, logged, stops | raise |
| `tools/fleet_set_permission_mode.py:312` | malformed file at compute time | reported as "skipping", counted skipped | loud, stops, alerts | count as error |
| `tools/fleet_set_permission_mode.py:347` | PR never mergeable | status string, not counted as error | loud, stops, alerts | count as error |
| `tools/fleet_set_permission_mode.py:355` | merge fails | status string lacks "ERROR", not counted as error | loud, stops, alerts | count as error |
| `tools/fleet_set_permission_mode.py:384` | repo count exceeds safety cap | stdout refusal, exit 1 | loud, alerts | ERROR to stderr and alert |
| `tools/fleet_set_permission_mode.py:391` | per-repo HTTP error | stdout line, continues | loud, alerts | ERROR to stderr and alert_operator |
| `tools/fleet_set_permission_mode.py:393` | any per-repo exception | stdout line, continues | loud, alerts | ERROR to stderr and alert_operator |
| `tools/fleet_set_permission_mode.py:405` | errors counted in summary | exit 0 regardless of errors | stops, alerts | exit non-zero when errors > 0 |
| `tools/generate_dependabot_yml.py:309` | gh repo list fails | stderr message, exit 1 | alerts | call alert_operator |
| `tools/generate_dependabot_yml.py:310` | empty gh output | zero targets, exit 0 | loud, logged, stops, alerts | raise on empty output |
| `tools/generate_dependabot_yml.py:384` | PR never mergeable | ok=False, stdout, exit 2 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/generate_dependabot_yml.py:395` | merge fails | ok=False, stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/generate_dependabot_yml.py:450` | more targets than the cap | NOTE on stdout, remainder deferred, exit 0 | loud, stops | exit non-zero when work is deferred |
| `tools/generate_dependabot_yml.py:469` | per-repo HTTP failure | stdout ERROR, continues | loud, alerts | ERROR to stderr and alert_operator |
| `tools/generate_dependabot_yml.py:485` | errors occurred | exit 2, no alert | alerts | call alert_operator |
| `tools/generate_dependabot_yml.py:490` | non-RequestException errors (KeyError etc.) | abort mid-fleet, traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/harvest_reviewer_idioms.py:44` | corpus file missing | stderr note, returns ""; every idiom reported uncovered, exit 0 | loud, stops, alerts | raise |
| `tools/harvest_reviewer_idioms.py:67` | lineage directory missing | non-ERROR stderr line, exit 2 | loud, alerts | ERROR line and alert_operator |
| `tools/harvest_reviewer_idioms.py:72` | no readiness verdicts | non-ERROR stderr line, exit 2 | loud, alerts | ERROR line and alert_operator |
| `tools/harvest_reviewer_idioms.py:81` | verdict file unreadable | skipped silently, still counted as scanned | loud, logged, stops, alerts | raise with path |
| `tools/heal_report.py:156` | ledger missing/unreadable or --repo wrong | treated as an empty ledger, exit 0 | loud, stops, alerts | distinguish missing file from empty and exit non-zero on missing |
| `tools/hermes_add_ci_workflow.py:170` | file-on-main GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:181` | open PR query fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:194` | main head GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:205` | branch create returns 422 for any validation reason | assumed "already exists", continues | loud, logged, stops | confirm the branch exists before reusing |
| `tools/hermes_add_ci_workflow.py:209` | branch create fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:224` | Contents PUT fails | HTTPError traceback, partial state | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:234` | PR create fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:262` | mergeable poll fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:280` | merge fails | HTTPError traceback after PR opened | alerts | entry handler calls alert_operator |
| `tools/hermes_add_ci_workflow.py:309` | resumed PR not mergeable | stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/hermes_add_ci_workflow.py:333` | new PR not mergeable | stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/hermes_add_ci_workflow.py:345` | any exception | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/land_aletheia_ci_oidc.py:100` | git show of the local branch fails | CalledProcessError traceback, captured stderr hidden | logged, alerts | log stderr at ERROR and alert |
| `tools/land_aletheia_ci_oidc.py:110` | branch head GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:121` | 422 for any validation reason | assumed "already exists" | loud, logged, stops | confirm the ref exists before reusing |
| `tools/land_aletheia_ci_oidc.py:124` | branch create fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:132` | file sha GET fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:148` | Contents PUT fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:164` | existing PR lookup fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:165` | 422 "already exists" but no open PR listed | IndexError with no context | logged, alerts | check emptiness and raise with detail |
| `tools/land_aletheia_ci_oidc.py:168` | PR create fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:177` | mergeable poll fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:207` | merge fails | HTTPError traceback | alerts | entry handler calls alert_operator |
| `tools/land_aletheia_ci_oidc.py:214` | remote branch delete returns an error status | response never checked | loud, logged, alerts | check status and report ERROR |
| `tools/land_aletheia_ci_oidc.py:218` | remote branch delete network error | `pass`, swallowed | loud, logged, stops, alerts | ERROR, alert, exit non-zero |
| `tools/land_aletheia_ci_oidc.py:231` | sentinel missing from payload | stdout ERROR, exit 1 | loud, alerts | write to stderr and alert_operator |
| `tools/land_aletheia_ci_oidc.py:258` | PR not mergeable | stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/land_aletheia_ci_oidc.py:269` | any exception | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/model_scorecard.py:45` | model has no known pricing | invented default price used silently | loud, logged, stops | raise on an unknown model |
| `tools/model_scorecard.py:56` | raw_response has no token counts | zeros reported as real counts | loud, logged, stops | raise or mark the entry unmeasured |
| `tools/model_scorecard.py:98` | logs directory missing | no entries; "No data found", exit 0 | loud, stops, alerts | raise when the directory is missing |
| `tools/model_scorecard.py:105` | malformed log line | skipped silently | loud, logged, stops | raise with file and line |
| `tools/model_scorecard.py:108` | record lacks timestamp | defaults to year 2000 | loud, logged, stops | raise on missing timestamp |
| `tools/model_scorecard.py:146` | audit file missing | returns [], workflow stats empty | loud, stops | raise when the file is missing |
| `tools/model_scorecard.py:155` | malformed audit line | skipped silently | loud, logged, stops | raise with file and line |
| `tools/model_scorecard.py:238` | no data | stdout, exit 0 | stops, alerts | exit non-zero when inputs were missing |
| `tools/model_scorecard.py:309` | any exception | traceback, no alert; otherwise always exit 0 | stops, alerts | return an exit code and wrap with an alert_operator handler |
| `tools/prompt_failure_report.py:15` | documented policy | exit 0 even when the telemetry file cannot be found | stops, alerts | exit non-zero when the file is missing |
| `tools/prompt_failure_report.py:54` | telemetry file missing (e.g. wrong --repo) | stdout note, exit 0 | loud, stops, alerts | ERROR and exit non-zero |
| `tools/prove_idle_timeout.py:131` | a proof half fails | FAIL lines on stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/prove_idle_timeout.py:135` | spawn or transport exception | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/readonly_attribute_audit.py:81` | stat fails on a path | returns None, counted as unmarked | loud, logged, stops | raise or count as unverified |
| `tools/readonly_attribute_audit.py:83` | no file attributes | returns None, counted as unmarked | loud, logged | raise |
| `tools/readonly_attribute_audit.py:90` | directory listing fails | returns []; ratio 0/0 feeds the verdict | loud, logged, stops, alerts | raise with path |
| `tools/readonly_attribute_audit.py:106` | stat for ctime fails | entry skipped silently | loud, logged | raise or report as unverified |
| `tools/readonly_attribute_audit.py:131` | root not a directory | ERROR on stderr, exit 2 | alerts | call alert_operator |
| `tools/readonly_attribute_audit.py:135` | not Windows | ERROR on stderr, exit 2 | alerts | call alert_operator |
| `tools/readonly_attribute_audit.py:173` | file listing fails | `pass` | loud, logged, stops | raise |
| `tools/readonly_attribute_audit.py:196` | staging dir mtime unreadable | stdout note, continues | loud, logged | raise or report as unverified |
| `tools/readonly_attribute_audit.py:226` | marking is spreading | stdout banner, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/repo_drift_check.py:163` | git times out | returns (124, "", cause); COMPLIANT as documented contract: fetch/rev-list callers record fetch_error/rev_list_error, report on stderr and exit 2/3 | compliant | none |
| `tools/repo_drift_check.py:165` | git missing | returns (127, "", cause); same contract and callers as above | compliant | none |
| `tools/repo_drift_check.py:183` | origin/HEAD and main/master unresolvable, including git errors | falls back to "main" silently | loud, logged, stops | raise or record an error status |
| `tools/repo_drift_check.py:216` | rev-list returned empty output | treated as 0 commits behind | loud, logged, stops | raise on empty output |
| `tools/repo_drift_check.py:299` | handoff file missing | ERROR on stderr, exit 1 | alerts | call alert_operator |
| `tools/repo_drift_check.py:316` | repos could not be checked | non-ERROR-level stderr block, exit 2 or 3 | loud, alerts | prefix ERROR with identity and call alert_operator |
| `tools/run_audit.py:130` | command file unreadable | LOW finding, status stays PASS | loud, logged, stops, alerts | mark ERROR and fail the run |
| `tools/run_audit.py:173` | git worktree list cannot run | ERROR status, stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/run_audit.py:182` | git worktree list fails | ERROR status, stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/run_audit.py:195` | empty worktree list | IndexError, swallowed by the 801 handler | loud, logged, alerts | check emptiness and raise with context |
| `tools/run_audit.py:223` | git status in a worktree fails | return code never checked; failure reads as clean | loud, logged, stops, alerts | check returncode and mark ERROR |
| `tools/run_audit.py:238` | git status times out | `pass`; uncommitted-change check skipped | loud, logged, stops, alerts | mark ERROR |
| `tools/run_audit.py:271` | .gitignore unreadable | `pass`; reported as missing patterns or no .gitignore | loud, logged, stops, alerts | mark ERROR with cause |
| `tools/run_audit.py:277` | parent .gitignore unreadable | `pass` | loud, logged, stops, alerts | mark ERROR with cause |
| `tools/run_audit.py:317` | git ls-files fails | return code ignored; reads as no tracked secrets | loud, logged, stops, alerts | check returncode and mark ERROR |
| `tools/run_audit.py:328` | tracked-secret check cannot run | `pass`; can report "no tracked secrets" | loud, logged, stops, alerts | mark ERROR and fail |
| `tools/run_audit.py:360` | README unreadable | ERROR status, stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/run_audit.py:445` | markdown file unreadable | skipped silently | loud, logged, stops, alerts | mark ERROR |
| `tools/run_audit.py:508` | inventory unreadable | ERROR status, stdout | loud, alerts | ERROR to stderr and alert_operator |
| `tools/run_audit.py:521` | inventory table cannot be parsed | WARN status, not counted as failed, exit 0 | loud, stops, alerts | mark ERROR |
| `tools/run_audit.py:777` | repo path missing | stderr, exit 1 | alerts | call alert_operator |
| `tools/run_audit.py:801` | an audit check crashes | ERROR status, stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/run_audit.py:840` | critical findings | stdout, exit 2 | loud, alerts | stderr ERROR and alert_operator |
| `tools/run_audit.py:843` | failed audits | stdout, exit 1 | loud, alerts | stderr ERROR and alert_operator |
| `tools/run_audit.py:852` | report write or other exception | traceback, no alert | alerts | wrap main with an alert_operator handler |
| `tools/speedrun_roll.py:72` | no_console import fails | `pass`; console suppression silently absent | loud, logged | raise |
| `tools/speedrun_roll.py:86` | utf8_console import fails | `pass`; UTF-8 protection silently absent | loud, logged | raise |
| `tools/speedrun_roll.py:206` | every failure EventLog records (ABORT, GATE, DETACH failed) | written to stdout and the file, never stderr at ERROR | loud | write failure records to stderr at ERROR |
| `tools/speedrun_roll.py:231` | heartbeat write fails | thread dies, roll continues without heartbeat | loud, logged, stops, alerts | catch, ERROR, alert, stop the roll |
| `tools/speedrun_roll.py:267` | git branch fails | return code ignored; next name may collide | loud, logged, stops | check returncode and raise |
| `tools/speedrun_roll.py:268` | ls-remote fails | return code ignored | loud, logged, stops | check returncode and raise |
| `tools/speedrun_roll.py:300` | ls-remote fails | returns "" (no attempt); callers establish a new attempt or skip the completed gate | loud, logged, stops, alerts | check returncode and raise |
| `tools/speedrun_roll.py:322` | new attempt branch cannot be established | stdout line, None, leads to exit 91 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:382` | git log errors on an existing ref | treated as no checkpoint, changing reset/preserve decision | loud, logged, stops | distinguish missing ref from error and raise |
| `tools/speedrun_roll.py:424` | issue fetch for settlement fails | body=None, launch continues | loud, logged, stops, alerts | raise |
| `tools/speedrun_roll.py:425` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/speedrun_roll.py:453` | settlement record malformed | skipped silently | loud, logged, stops | raise |
| `tools/speedrun_roll.py:540` | clean-check gate reports errors | stdout lines, None, exit 91 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:681` | owner/repo cannot be determined for reset | stdout log line, None, exit 91 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:841` | git fetch fails | returns False (LLD not landed); resume declined | loud, logged, stops | raise with stderr |
| `tools/speedrun_roll.py:861` | gh pr list fails | returns False (no open PR) | loud, logged, stops | raise with stderr |
| `tools/speedrun_roll.py:865` | gh output unparseable | returns False | loud, logged, stops | raise |
| `tools/speedrun_roll.py:990` | fetch fails | ignored; binding-doc comparison runs on stale refs and can report nothing to sync | loud, logged, stops, alerts | check returncode and return a problem |
| `tools/speedrun_roll.py:1037` | rev-parse fails | empty strings compare equal; absorb skipped | loud, logged, stops | check returncode and return a problem |
| `tools/speedrun_roll.py:1057` | merge --abort fails | ignored | loud, logged | check returncode and report |
| `tools/speedrun_roll.py:1074` | merge --abort fails | ignored | loud, logged | check returncode and report |
| `tools/speedrun_roll.py:1098` | sync worktree removal fails | ignored; worktree left registered | loud, logged | check returncode and report a problem |
| `tools/speedrun_roll.py:1149` | no lld settlement record | logs and returns True (draw fresh); COMPLIANT: docstring 1142-1146 defines unknowable as stale and the caller redraws, which is safe | compliant | none |
| `tools/speedrun_roll.py:1256` | profile cannot load for the START line | returns "unreadable(...)", continues | loud, logged, stops, alerts | raise |
| `tools/speedrun_roll.py:1257` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/speedrun_roll.py:1267` | persisted state unreadable | returns "" (no mismatch) | loud, logged, stops, alerts | raise |
| `tools/speedrun_roll.py:1268` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/speedrun_roll.py:1324` | orchestrator state corrupt/unreadable | resume declined on stdout, fresh paid redraw | loud, stops, alerts | ERROR, alert, stop |
| `tools/speedrun_roll.py:1330` | target repo path cannot resolve | resume declined, fresh redraw | loud, stops, alerts | ERROR, alert, stop |
| `tools/speedrun_roll.py:1436` | git for-each-ref fails | return code ignored; inventory reports nothing preserved | loud, logged | check returncode |
| `tools/speedrun_roll.py:1540` | visual-gate sentinel unreadable | `continue` | loud, logged | ERROR when it persists beyond a write window |
| `tools/speedrun_roll.py:1552` | visual-gate scan fails | `continue`; URL never announced | loud, logged, alerts | ERROR and alert |
| `tools/speedrun_roll.py:1593` | no usable base | stdout, return 91 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:1792` | USERNAME unset | empty user written into the task XML | loud, logged, stops | raise |
| `tools/speedrun_roll.py:1868` | --detach on a non-Windows platform | ERROR to stdout, return 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:1899` | schtasks /Create fails | stdout, return 91 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:1905` | schtasks /Run fails | stdout, return 91 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:1951` | tasklist fails | return code ignored; reads as not live, kill refused, exit 0 | loud, logged, stops, alerts | check returncode and raise |
| `tools/speedrun_roll.py:1994` | taskkill fails | stdout, exit 0 | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:2005` | stop or end-task failed | exit 0 regardless | stops, alerts | exit non-zero on failure |
| `tools/speedrun_roll.py:2019` | events-log listing fails | returns []; KILLED stamp silently skipped | loud, logged | raise |
| `tools/speedrun_roll.py:2041` | stamping a run log fails | `continue` | loud, logged, alerts | ERROR and alert |
| `tools/speedrun_roll.py:2062` | tree_kill fails | stdout, exit 0 | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:2104` | kill or dispose failures | exit 0 always | stops, alerts | exit non-zero on failure |
| `tools/speedrun_roll.py:2128` | worktree/branch disposal fails | stdout line, exit 0 | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:2129` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/speedrun_roll.py:2173` | schtasks /Query fails | returns ""; COMPLIANT: docstring 2169-2170 keeps unknown distinct from done, caller 2748-2757 bounds it and returns 1 | compliant | none |
| `tools/speedrun_roll.py:2221` | schtasks /End fails | reported as "was not running" | loud, logged, stops | report the real failure with stderr |
| `tools/speedrun_roll.py:2311` | log stat fails | `continue` | loud, logged | raise |
| `tools/speedrun_roll.py:2312` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/speedrun_roll.py:2328` | run log unreadable | `pass` | loud, logged | raise |
| `tools/speedrun_roll.py:2329` | fail-open tag | withdrawn convention present | loud, logged, stops, alerts | remove tag and fail loudly |
| `tools/speedrun_roll.py:2403` | atlas import fails | `pass`, empty map | loud, logged | ERROR line |
| `tools/speedrun_roll.py:2482` | key poll fails | `pass` | loud, logged | ERROR line |
| `tools/speedrun_roll.py:2503` | atlas import fails | returns {} | loud, logged | ERROR line |
| `tools/speedrun_roll.py:2667` | orientation file missing | stdout note, continues | loud | ERROR line |
| `tools/speedrun_roll.py:2757` | scheduler unqueryable 30 times | stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:2775` | Last Result unreadable (None) | coerced to 0, roll reported SUCCEEDED | loud, logged, stops, alerts | treat None as failure |
| `tools/speedrun_roll.py:2879` | signal handler cannot be installed | `continue` silently | loud, logged | ERROR line |
| `tools/speedrun_roll.py:2902` | fetch fails | ignored; staleness compared against stale origin/main, tree passes | loud, logged, stops, alerts | check returncode and refuse |
| `tools/speedrun_roll.py:2916` | git status fails | return code ignored; reads as no modifications | loud, logged, stops, alerts | check returncode and refuse |
| `tools/speedrun_roll.py:3004` | git status fails during RESTORE | return code ignored; tracked dirt unreported | loud, logged, stops | check returncode and add a failure |
| `tools/speedrun_roll.py:3093` | run blocked with no question numbers | stdout note, gate not written | loud, alerts | ERROR to stderr and alert_operator |
| `tools/speedrun_roll.py:3123` | log listing fails | returns "" run tag | loud, logged | raise |
| `tools/speedrun_roll.py:3146` | arc unresolved, including ls-remote failure | completed-redraw gate skipped | loud, logged, stops | distinguish no arc from failure and refuse on failure |
| `tools/speedrun_roll.py:3189` | no console to confirm | BLOCKED on stdout, 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:3237` | prereqs file corrupt/unreadable | blocking=[]; falls back to live query with stdout note | loud, logged, alerts | ERROR naming the file and alert |
| `tools/speedrun_roll.py:3256` | gh unreachable for prereq check | BLOCKED on stdout, 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:3291` | gh issue view fails | BLOCKED on stdout, 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:3340` | verdict rendering fails | stdout line; prereqs gate may not be written | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:3376` | unverified-requirements ledger unreadable | returns []; success prints without the UNVERIFIED banner | loud, logged, stops, alerts | raise or print an ERROR banner |
| `tools/speedrun_roll.py:3398` | archive cannot resolve run | ARCHIVE SKIPPED on stdout, exit unchanged (0) | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:3427` | archive manifest mismatch | stdout line only, exit 0 | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:3446` | archive fails | ARCHIVE FAILED on stdout, exit 0 | loud, stops, alerts | ERROR, alert, exit non-zero |
| `tools/speedrun_roll.py:3726` | repo is not a git root | stdout, 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:3739` | model profile refused | stdout, 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:3849` | must-resolve gate cannot run | WARNING, launch proceeds | loud, stops, alerts | refuse when the gate cannot run |
| `tools/speedrun_roll.py:3896` | contract-fidelity check refuses or fails | second (refusal) value discarded; roll proceeds | loud, stops, alerts | honour the refusal flag and return 91 |
| `tools/speedrun_roll.py:3962` | worktree sweep leaves problems | stdout line, roll continues | loud, stops, alerts | ERROR and stop |
| `tools/speedrun_roll.py:3970` | sweep raises | stdout "continuing" | loud, stops, alerts | ERROR, alert, stop |
| `tools/speedrun_roll.py:3997` | janitor leaves problems | stdout line, continues | loud, stops, alerts | ERROR and stop |
| `tools/speedrun_roll.py:4007` | janitor raises | stdout "continuing" | loud, stops, alerts | ERROR, alert, stop |
| `tools/speedrun_roll.py:4019` | binding-doc sync raises | becomes a problem; BLOCKED stdout, 91 | loud, alerts | stderr and alert_operator |
| `tools/speedrun_roll.py:4060` | resume planning raises | stdout log, continues with a fresh paid redraw | loud, stops, alerts | ERROR, alert, stop |
| `tools/speedrun_roll.py:4151` | an issue's child roll fails | STOPPED on stdout, exits with child code | loud, alerts | stderr ERROR and alert_operator |
| `tools/speedrun_roll.py:4180` | RESTORE fails | RESTORE INCOMPLETE on stdout, exit code unchanged (can be 0) | loud, stops, alerts | ERROR, alert, force non-zero exit |
| `tools/speedrun_roll.py:4202` | any unhandled exception | traceback, no alert; no alert_operator call anywhere in the file | alerts | wrap main with an alert_operator handler |
| `tools/test_gate/auditor.py:38` | explicitly passed audit file does not exist | silently falls through to defaults | loud, logged, stops | raise when the explicit file is missing |
| `tools/test_gate/auditor.py:71` | audit block has a start marker but no end | WARNING on stderr, returns None (tests then counted unaudited) | loud | log at ERROR |
| `tools/test_gate/auditor.py:118` | table row does not match the row format | row dropped silently | loud, logged, stops | raise naming the malformed row |
| `tools/test_gate/auditor.py:153` | no audit block | all skipped tests returned as unaudited; COMPLIANT: fails closed, documented in docstring 150-151 | compliant | none |
| `tools/validate_skill.py:122` | skill file unreadable | E000 finding on stdout, exit 1 (docstring promises 2) | loud, alerts | ERROR to stderr, exit 2, alert |
| `tools/validate_skill.py:124` | file not UTF-8 | E000 finding on stdout, exit 1 | loud, alerts | ERROR to stderr and alert |
| `tools/validate_skill.py:146` | path not a file | stderr ERROR, exit 1 (docstring promises 2) | alerts | exit 2 and alert_operator |
| `tools/verdict_analyzer/parser.py:58` | verdict type undeterminable | silently defaults to "lld" | loud, logged, stops | raise when no detection rule matches |
| `tools/verdict_analyzer/parser.py:79` | decision unparseable | record returned with "UNKNOWN" | loud, logged, stops | raise when no format matches |
| `tools/verdict_analyzer/parser.py:168` | neither blocking-issue format matches | empty list, indistinguishable from none | loud, logged | raise or flag when the section exists but parses empty |
| `tools/verdict_analyzer/patterns.py:68` | unknown category | silently mapped to a default section | loud, logged | raise on an unknown category |
| `tools/view_audit.py:31` | timestamp unparseable | raw value displayed; COMPLIANT: display-only, data still shown verbatim | compliant | none |
| `tools/view_audit.py:40` | verdict missing or unknown | displayed as BLOCKED | loud, logged | display UNKNOWN distinctly |
| `tools/view_audit.py:86` | log missing or unreadable | same message as empty, exit 0 | loud, stops, alerts | distinguish missing file and exit non-zero |
| `tools/view_audit.py:133` | log line unparseable (watchdog path) | `pass` | loud, logged, stops | ERROR naming the line |
| `tools/view_audit.py:149` | watchdog not installed | announced fallback to polling; COMPLIANT: equivalent behaviour, stated on stdout | compliant | none |
| `tools/view_audit.py:171` | log line unparseable (polling path) | `pass` | loud, logged, stops | ERROR naming the line |
| `tools/view_audit.py:240` | any exception | traceback, no alert; otherwise always exit 0 | alerts | return an exit code and wrap with an alert_operator handler |
| `tools/answer_key_audit.py:50` | --repo path is not a directory | prints to stdout and returns 2 | loud, alerts | Write an ERROR line to stderr and call alert_operator before exiting non-zero. |
| `tools/answer_key_audit.py:53` | audit of the target repo raises | unhandled exception ends the process with a traceback, nothing alerts | alerts | Wrap main in a handler that calls alert_operator and exits 1. |
| `tools/answer_key_audit.py:60` | writing the saved report fails | unhandled OSError, no alert | alerts | Route through the same alerting handler in main. |
| `tools/audit_deferred_scope.py:188` | gh retries run out or gh fails without a rate limit | returns the failed CompletedProcess; every caller (212, 238, 293) checks returncode and raises AuditFailed | compliant | none |
| `tools/audit_deferred_scope.py:208` | more than 2000 closed issues exist | corpus silently truncated at 2000, audit reports as complete | logged, stops, alerts | Raise AuditFailed when the returned count equals the limit. |
| `tools/audit_deferred_scope.py:288` | more than 5000 issues exist | state index silently truncated, xref states become unknown | logged, stops, alerts | Raise AuditFailed when the returned count equals the limit. |
| `tools/audit_deferred_scope.py:303` | a state-index item has no integer number | item dropped silently | loud, logged, stops, alerts | Raise AuditFailed naming the malformed item. |
| `tools/audit_deferred_scope.py:567` | classifier text is not direct JSON | falls through to block extraction, then returns None; the only caller (651) raises AuditFailed on None | compliant | none |
| `tools/audit_deferred_scope.py:656` | classifier JSON lacks required keys | defaults to False/empty, candidate silently counted as a false positive and cached | loud, logged, stops, alerts | Raise AuditFailed when any required key is missing or mistyped. |
| `tools/audit_deferred_scope.py:770` | UTF-8 reconfigure of stdout/stderr fails | swallowed with pass | loud, logged, stops, alerts | Remove the handler or alert and exit 1. |
| `tools/audit_deferred_scope.py:784` | any phase failure | alert_operator with phase, issue, spec, cause, consequence; returns 1; no report written | compliant | none |
| `tools/audit_fully_landed.py:42` | git or gh command times out | returns ("TIMEOUT", -1); callers read the text as data | loud, logged, stops, alerts | Raise with the command and repo, alert, exit 1. |
| `tools/audit_fully_landed.py:53` | git status fails | return code discarded; empty output reported as a clean directory | loud, logged, stops, alerts | Check the return code and fail the audit. |
| `tools/audit_fully_landed.py:57` | git worktree list fails | return code discarded; reported as no dangling worktrees | loud, logged, stops, alerts | Check the return code and fail the audit. |
| `tools/audit_fully_landed.py:62` | git stash list fails | return code discarded; reported as no stashes | loud, logged, stops, alerts | Check the return code and fail the audit. |
| `tools/audit_fully_landed.py:76` | gh pr list output is not JSON | bare except sets open_prs=-1, report continues, exit 0 | loud, logged, stops, alerts | Raise with the repo and parse error, alert, exit 1. |
| `tools/audit_fully_landed.py:79` | gh pr list fails | printed as an unchecked box, script continues and exits 0 | loud, logged, stops, alerts | Raise with stderr, alert, exit 1. |
| `tools/audit_fully_landed.py:85` | fetch fails | return code ignored; sync judged against stale origin/main | loud, logged, stops, alerts | Check the return code and fail. |
| `tools/audit_fully_landed.py:86` | git branch fails | return code ignored, wrong sync path taken | loud, logged, stops, alerts | Check the return code and fail. |
| `tools/audit_fully_landed.py:88` | git status -sb fails | empty output reported as synced | loud, logged, stops, alerts | Check the return code and fail. |
| `tools/audit_fully_landed.py:96` | rev-list comparison fails | reported as ahead/behind, exit 0 | loud, logged, stops, alerts | Raise with the command error, alert, exit 1. |
| `tools/audit_loud_failure.py:41` | git ls-files fails | CalledProcessError ends the process, no alert | alerts | Catch at main, alert_operator, exit 1. |
| `tools/audit_loud_failure.py:47` | baseline missing or corrupt | unhandled exception, no alert | alerts | Catch at main, alert_operator, exit 1. |
| `tools/audit_loud_failure.py:64` | write-baseline refused because new sites exist | stderr message, return 1 | alerts | Call alert_operator with the new sites. |
| `tools/audit_loud_failure.py:85` | check mode finds new or stale sites | stderr message, return 1 | alerts | Call alert_operator with the list. |
| `tools/audit_schedule_check.py:179` | an audit-record date cell does not parse | row skipped, latest date may be wrong | loud, logged, stops, alerts | Raise naming the file and row. |
| `tools/audit_schedule_check.py:202` | audit file unreadable | returns block with reason lacking the exception; stdout; exit 1 | loud, logged, alerts | Include type and message, ERROR to stderr, alert. |
| `tools/audit_schedule_check.py:206` | no parseable audit date in the file | status warn, run passes with exit 0 | loud, stops, alerts | Treat as a failure and exit non-zero with an alert. |
| `tools/audit_schedule_check.py:248` | docs/ missing (wrong cwd) | check skipped, exit 0 | loud, logged, stops, alerts | Fail with exit 1 and alert. |
| `tools/audit_schedule_check.py:254` | audit index missing or misnamed | check skipped, exit 0 | loud, logged, stops, alerts | Fail with exit 1 and alert. |
| `tools/audit_schedule_check.py:260` | index unreadable | unhandled exception, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/audit_schedule_check.py:264` | frequency table missing or unparseable | check skipped, exit 0 | loud, logged, stops, alerts | Fail with exit 1 and alert. |
| `tools/audit_schedule_check.py:289` | scheduled audit file not found | recorded as block, printed to stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator. |
| `tools/audit_schedule_check.py:348` | audits overdue | stdout, exit 1 | loud, alerts | ERROR to stderr and alert_operator. |
| `tools/auth-preflight.sh:14` | auth check fails all three attempts | loop ends and the script execs a login shell anyway | loud, logged, stops, alerts | After the loop, if auth never passed, print to stderr, alert, exit 1. |
| `tools/auth-preflight.sh:15` | an attempt fails | message on stdout with no cause (stderr discarded) | loud, logged | Write to stderr with the captured error output. |
| `tools/backfill_canonical_labels.py:69` | more repos than the limit | list silently truncated | logged, stops, alerts | Fail when the count equals the limit. |
| `tools/backfill_canonical_labels.py:76` | gh repo list fails | ERROR on stderr, returns empty; main exits 1 | alerts | Raise and alert_operator from main. |
| `tools/backfill_canonical_labels.py:81` | repo list is not JSON | ERROR on stderr, returns empty; main exits 1 | alerts | Raise and alert_operator from main. |
| `tools/backfill_canonical_labels.py:94` | gh label list fails | None with no stderr or cause | loud, logged, alerts | Raise with return code and stderr. |
| `tools/backfill_canonical_labels.py:98` | label list is not JSON | None with no cause | loud, logged, alerts | Raise with the parse error. |
| `tools/backfill_canonical_labels.py:137` | gh label create fails | recorded, FAILED printed to stdout, run continues, exit 2 | loud, alerts | ERROR to stderr and alert_operator. |
| `tools/backfill_canonical_labels.py:145` | labels unreadable | generic error without cause on stdout, exit 2 | loud, logged, alerts | Carry the cause, write to stderr, alert. |
| `tools/batch-workflow.sh:73` | every failure reported through log_error | written to stdout | loud, alerts | Redirect to stderr and alert the operator. |
| `tools/batch-workflow.sh:91` | an issue argument is not a number | skipped with a warning, batch runs on the rest | loud, stops, alerts | Exit 1 on any invalid issue. |
| `tools/batch-workflow.sh:167` | a workflow run fails | stdout banner; with --continue-on-fail the batch continues; nothing alerts | loud, alerts | Write the failure to stderr and alert the operator. |
| `tools/batch-workflow.sh:315` | git remote get-url on line 317 fails or is not GitHub | falls back to a hardcoded repo or the raw URL with no message | loud, logged, stops, alerts | Fail with exit 1 when the repo cannot be determined. |
| `tools/batch-workflow.sh:332` | gh issue list on line 330 fails | its stderr is discarded; under set -e and pipefail the script dies silently; --limit 100 truncates silently | loud, logged, alerts | Capture gh stderr, report it on stderr, alert, and fail on truncation. |
| `tools/batch-workflow.sh:373` | grep on line 375 matches nothing (empty log dir) | non-zero pipeline under set -e and pipefail ends the script silently | loud, logged, alerts | Tolerate no match explicitly and report real failures on stderr. |
| `tools/batch_cleanup_security_hooks.py:71` | more repos than the limit | list silently truncated | logged, stops, alerts | Fail when the count equals the limit. |
| `tools/batch_cleanup_security_hooks.py:94` | settings.json unparseable | returns False; hook files are still deleted and the stale registration stays | loud, logged, stops, alerts | Raise naming the file before any deletion. |
| `tools/batch_cleanup_security_hooks.py:150` | repo not cloned locally | counted as skipped, exit 0 | loud, logged, stops, alerts | Count as an error. |
| `tools/batch_cleanup_security_hooks.py:167` | no default branch | status string on stdout, next repo, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/batch_cleanup_security_hooks.py:171` | pull fails | return code ignored, branch cut from stale main | loud, logged, stops, alerts | Use check=True. |
| `tools/batch_cleanup_security_hooks.py:200` | settings cleanup fails | return value discarded | loud, logged, stops, alerts | Act on a False result. |
| `tools/batch_cleanup_security_hooks.py:289` | any step for a repo fails | stdout ERROR, next repo, created issue or branch left behind, exit 1 | loud, alerts | ERROR to stderr with the step, alert, stop. |
| `tools/campaign_timing_dashboard.py:162` | gh issue view fails | stdout note, empty set, chart rendered without hatching, exit 0 | loud, logged, stops, alerts | Raise with stderr, alert, exit 1. |
| `tools/campaign_timing_dashboard.py:166` | ledger output is not JSON | empty set returned silently | loud, logged, stops, alerts | Raise with the parse error. |
| `tools/campaign_timing_dashboard.py:181` | git remote fails or is not GitHub | empty slug passed on to gh | loud, logged, stops, alerts | Raise naming the repo and URL. |
| `tools/campaign_timing_dashboard.py:201` | no runs found | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/claude_spend_lock.py:106` | settings unreadable under --status | reported as a line, exit 0 | loud, stops, alerts | Exit non-zero with ERROR on stderr and alert. |
| `tools/claude_spend_lock.py:172` | staged write or replace fails | removes the .tmp and re-raises | compliant | none |
| `tools/claude_spend_lock.py:214` | one home fails | loop continues to the other home, lock can end half-thrown | stops, alerts | Stop at the first failing home and alert. |
| `tools/claude_spend_lock.py:238` | settings not usable | stdout, return 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/claude_spend_lock.py:274` | replace fails | stdout, return 3 | loud, alerts | ERROR to stderr and alert. |
| `tools/claude_spend_lock.py:278` | read-back mismatch | stdout, return 3 | loud, alerts | ERROR to stderr and alert. |
| `tools/claude_spend_lock.py:283` | lock file write fails after settings were changed | unhandled exception, half lock, no alert | alerts | Catch, alert naming both halves, exit 1. |
| `tools/factory_report.py:88` | --repo does not exist | stdout, exit 0 | loud, logged, stops, alerts | ERROR to stderr, alert, exit 1. |
| `tools/factory_report.py:97` | --since unparseable | argparse error on stderr, exit 2 | alerts | Alert before exiting. |
| `tools/factory_report.py:100` | building the report raises | unhandled, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/factory_report.py:115` | requested save fails | warning on stdout, exit 0 | loud, logged, stops, alerts | ERROR to stderr, alert, exit 1. |
| `tools/hermes_pin_workflow_shas.py:182` | any GitHub REST call fails | HTTPError ends the process, no alert | alerts | Catch at main, alert_operator, exit 1. |
| `tools/hermes_pin_workflow_shas.py:231` | branch create returns 422 for any reason | assumed to exist and reused without checking its base | loud, logged, stops, alerts | Check the 422 body and the branch head before reusing. |
| `tools/hermes_pin_workflow_shas.py:303` | mergeable poll times out | returns last state; caller prints to stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/hermes_pin_workflow_shas.py:335` | file on main differs from expectation | stderr, exit 2 | alerts | Call alert_operator. |
| `tools/hermes_pin_workflow_shas.py:359` | PR not mergeable | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/hermes_pin_workflow_shas.py:389` | PR not mergeable | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/hermes_pin_workflow_shas.py:406` | post-merge verification fails | stderr, exit 1 | alerts | Call alert_operator. |
| `tools/land_2283_ci_tiers.py:267` | file absent on main | returns (None, None); caller treats it as a create | compliant | none |
| `tools/land_2283_ci_tiers.py:269` | any GitHub REST call fails | HTTPError ends the process, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/land_2283_ci_tiers.py:291` | branch already exists | reused without checking it is based on current main | logged, stops, alerts | Refuse unless the branch head equals main or the expected commit. |
| `tools/land_2283_ci_tiers.py:356` | PR dirty | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/land_2283_ci_tiers.py:359` | poll budget runs out | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/land_2283_ci_tiers.py:383` | branch delete returns 422 | reported as deleted | loud, logged, stops, alerts | Treat only 204 (and 404) as success. |
| `tools/land_2283_ci_tiers.py:414` | embed is stale | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/land_career_test_ci.py:114` | contents GET returns a non-200, non-404, non-error status | treated as file absent | loud, logged, stops, alerts | Raise on any status other than 200 or 404. |
| `tools/land_career_test_ci.py:123` | any GitHub REST call fails | HTTPError ends the process, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/land_career_test_ci.py:134` | branch exists | reused without checking its base | logged, stops, alerts | Verify the branch head before reuse. |
| `tools/land_career_test_ci.py:212` | branch delete returns 422 | reported as cleaned up | loud, logged, stops, alerts | Treat only 204 (and 404) as success. |
| `tools/land_career_test_ci.py:238` | PR dirty or poll budget runs out | stderr, exit 1 | alerts | Call alert_operator. |
| `tools/land_polybolos_ci_workflow.py:201` | file absent on branch | returns None; caller creates instead of updating | compliant | none |
| `tools/land_polybolos_ci_workflow.py:203` | any GitHub REST call fails | HTTPError ends the process, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/land_polybolos_ci_workflow.py:247` | no protection on main | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/land_polybolos_ci_workflow.py:252` | required status checks off | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/land_staged_workflow.py:112` | file absent | returns None; every caller handles None explicitly | compliant | none |
| `tools/land_staged_workflow.py:137` | staged file not on main | message to stderr, exit 1 | alerts | Call alert_operator before exiting. |
| `tools/land_staged_workflow.py:181` | branch exists | reused without checking its base | logged, stops, alerts | Verify the branch head before reuse. |
| `tools/land_staged_workflow.py:294` | no top-level name in the workflow, found after the PR is already open | stderr, exit 1, PR left open | alerts | Parse the name before any write and alert. |
| `tools/land_staged_workflow.py:330` | no workflow run appears | caller prints to stderr, exit 1 | alerts | Call alert_operator. |
| `tools/land_staged_workflow.py:351` | PR never mergeable | caller prints to stderr, exit 1 | alerts | Call alert_operator. |
| `tools/land_staged_workflow.py:371` | branch delete returns 422 | reported as cleaned up | loud, logged, stops, alerts | Treat only 204 (and 404) as success. |
| `tools/land_staged_workflow.py:466` | installed workflow concludes red | stderr, exit 1 | alerts | Call alert_operator. |
| `tools/merge_aletheia_603_audit_gate.py:239` | branch delete returns 422 | reported as already deleted | loud, logged, stops, alerts | Treat only 204 (and 404) as success. |
| `tools/merge_aletheia_603_audit_gate.py:306` | PR creation fails | prints cleanup note to stdout, re-raises | loud, alerts | Print to stderr and alert before re-raising. |
| `tools/merge_aletheia_603_audit_gate.py:342` | local file missing | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/merge_aletheia_603_audit_gate.py:357` | any landing step fails | stdout FATAL without exception type, exit 2 | loud, logged, alerts | ERROR to stderr with type and step, alert. |
| `tools/merge_aletheia_603_audit_gate.py:367` | PR #584 nudge fails | WARNING on stdout, exit 0 | loud, logged, stops, alerts | ERROR to stderr, alert, exit non-zero. |
| `tools/merge_sentinel_permissions_prs.py:73` | more than 100 matching PRs | list silently truncated | logged, stops, alerts | Fail when the count equals the limit. |
| `tools/merge_sentinel_permissions_prs.py:81` | gh search fails | stdout ERROR, empty list; main prints "No PRs to merge. Done." and exits 0 | loud, stops, alerts | Raise, alert, exit 1. |
| `tools/merge_sentinel_permissions_prs.py:86` | search output not JSON | stdout ERROR, empty list, exit 0 | loud, stops, alerts | Raise, alert, exit 1. |
| `tools/merge_sentinel_permissions_prs.py:150` | disabling enforce_admins fails | recorded, next PR processed, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/merge_sentinel_permissions_prs.py:160` | merge fails | recorded, next PR processed, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/merge_sentinel_permissions_prs.py:165` | enforce_admins NOT restored | error appended, printed to stdout, batch continues to other repos | loud, stops, alerts | ERROR to stderr, alert immediately, stop the batch. |
| `tools/merge_sentinel_permissions_prs.py:297` | search record lacks repository or number | defaults to unknown/0 and calls the API on them | loud, logged, stops, alerts | Raise on a malformed record. |
| `tools/migrate_lineage_flat_to_run_scoped.py:67` | repo has no docs/lineage (wrong path) | reported "[OK] no migration needed", exit 0 | loud, logged, stops, alerts | Fail when docs/lineage is absent. |
| `tools/migrate_lineage_flat_to_run_scoped.py:86` | a move fails partway | unhandled, partial migration, no alert | alerts | Catch, report moved and pending files, alert, exit 1. |
| `tools/migrate_lineage_flat_to_run_scoped.py:114` | bad --repo | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:49` | deploy_cerberus_secrets import fails | swallowed; names stay undefined unless the next fallback runs, NameError later | loud, logged, stops, alerts | Let the import fail or re-import in the handler. |
| `tools/new_repo.py:409` | dup2 of stdin fails | returns False; the caller ignores it | loud, logged, stops, alerts | Raise; stdin detachment is a security property. |
| `tools/new_repo.py:466` | repo lookup returns 404 | returns None, documented; other failures raise RuntimeError | compliant | none |
| `tools/new_repo.py:1531` | poetry init fails | stdout warning, returns False, creation continues | loud, stops, alerts | Raise and stop repo creation. |
| `tools/new_repo.py:1534` | poetry init errors | stdout warning, returns False | loud, stops, alerts | Raise and stop repo creation. |
| `tools/new_repo.py:1542` | poetry add fails | stdout warning, returns False | loud, stops, alerts | Raise and stop repo creation. |
| `tools/new_repo.py:1546` | poetry add errors | stdout warning, returns False | loud, stops, alerts | Raise and stop repo creation. |
| `tools/new_repo.py:1560` | pyproject write fails | stdout warning, returns False | loud, stops, alerts | Raise. |
| `tools/new_repo.py:1574` | pyproject rewrite fails | stdout warning, returns False | loud, stops, alerts | Raise. |
| `tools/new_repo.py:1584` | conftest write fails | stdout warning, returns False | loud, stops, alerts | Raise. |
| `tools/new_repo.py:1612` | package skeleton write fails | stdout warning, returns False | loud, stops, alerts | Raise. |
| `tools/new_repo.py:1641` | description anchor missing | stdout warning, returns False | loud, stops, alerts | Raise. |
| `tools/new_repo.py:1661` | pyproject write fails | stdout warning, returns False | loud, stops, alerts | Raise. |
| `tools/new_repo.py:1930` | npm dirs lack a test script, so their PRs can never merge | warning only, creation continues | loud, stops, alerts | Refuse, or alert the operator. |
| `tools/new_repo.py:2045` | existing settings.json unparseable | backed up, overwritten, stdout warning, continues | loud, stops, alerts | Stop and alert. |
| `tools/new_repo.py:2139` | main branch absent on origin | stdout, returns False, run continues | loud, stops, alerts | Raise with gh stderr. |
| `tools/new_repo.py:2142` | gh times out or is missing | returns False with no message | loud, logged, stops, alerts | Raise with the cause. |
| `tools/new_repo.py:2167` | protection PUT rejected | False with no status or body logged | loud, logged, stops, alerts | Raise with status and body. |
| `tools/new_repo.py:2168` | protection PUT network error | False with no cause | loud, logged, stops, alerts | Raise with the cause. |
| `tools/new_repo.py:2201` | repo settings PATCH rejected | False with no status or body | loud, logged, stops, alerts | Raise with status and body. |
| `tools/new_repo.py:2202` | settings PATCH network error | False with no cause | loud, logged, stops, alerts | Raise with the cause. |
| `tools/new_repo.py:2260` | workflow upload fails | stdout message, returns (False, n); caller only warns | loud, stops, alerts | Raise and stop. |
| `tools/new_repo.py:2312` | label create fails | stdout warning, continues | loud, stops, alerts | Raise and stop. |
| `tools/new_repo.py:2314` | label command errors | stdout warning, continues | loud, stops, alerts | Raise and stop. |
| `tools/new_repo.py:2414` | verification GET fails | returns (False, message), documented; caller prints FAIL | compliant | none |
| `tools/new_repo.py:2595` | installation id not JSON | id shown as None; informational only, verdict already 200 | compliant | none |
| `tools/new_repo.py:2630` | sentinel credential not provisioned | outcome "skip", check excluded from the count | loud, logged, stops, alerts | Fail the check and alert. |
| `tools/new_repo.py:2635` | credential decrypt fails or is declined | outcome "skip" | loud, logged, stops, alerts | Fail the check and alert. |
| `tools/new_repo.py:2637` | credential bundle malformed | outcome "skip" | loud, logged, stops, alerts | Fail the check and alert. |
| `tools/new_repo.py:2676` | PEM invalid | stdout, status string, run ends in SUCCESS exit 0 | loud, stops, alerts | Raise and exit 1 with an alert. |
| `tools/new_repo.py:2690` | secret deploy fails | stdout, status string, exit 0 | loud, stops, alerts | Raise and exit 1 with an alert. |
| `tools/new_repo.py:2699` | secrets not verified | stdout warning, exit 0 | loud, stops, alerts | Raise and exit 1 with an alert. |
| `tools/new_repo.py:2709` | plaintext PEM cannot be deleted | warning, returns "OK", exit 0 | loud, logged, stops, alerts | Raise, alert, exit non-zero. |
| `tools/new_repo.py:2781` | post-create hook raises | FAILED status, creation continues, exit 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:2790` | stdin detach fails | return value ignored | loud, logged, stops, alerts | Check the result and stop. |
| `tools/new_repo.py:2918` | bad arguments | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:2960` | PEM missing | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:2976` | invalid name | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:2993` | directory exists | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:3003` | gh api user fails | stdout without stderr, exit 1 | loud, logged, alerts | Include gh stderr, ERROR to stderr, alert. |
| `tools/new_repo.py:3016` | any scaffold step raises | stdout, exit 1, partial state left | loud, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:3054` | .git file unreadable while diagnosing | shows "(unreadable)" inside a refusal that already exits 1 | compliant | none |
| `tools/new_repo.py:3076` | directory unreadable while diagnosing | entry count -1 inside a refusal that already exits 1 | compliant | none |
| `tools/new_repo.py:3125` | packaging unavailable | validation becomes advisory, gate passes | loud, logged, stops, alerts | Fail the gate. |
| `tools/new_repo.py:3147` | PyYAML unavailable | dependabot.yml not validated, gate passes | loud, logged, stops, alerts | Fail the gate. |
| `tools/new_repo.py:3192` | remote existence unknown | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:3257` | canonical hook source missing | warning, repo continues unprotected | loud, stops, alerts | FIXED in #4137: the per-repo hook step is removed; the guard is registered centrally |
| `tools/new_repo.py:3328` | Python bootstrap failed | warning, creation continues | loud, stops, alerts | Stop and alert. |
| `tools/new_repo.py:3466` | git check-ignore errors (rc 128) | read as "not ignored" without a message | loud, logged, stops, alerts | Treat return codes other than 0 and 1 as failures. |
| `tools/new_repo.py:3500` | local verification fails | warning, proceeds to create the GitHub repo | loud, stops, alerts | Exit 1 with an alert before any GitHub step. |
| `tools/new_repo.py:3510` | a validation could not run | warning, gate passes | loud, stops, alerts | Fail the gate. |
| `tools/new_repo.py:3518` | scaffold invalid | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/new_repo.py:3579` | repo create fails | stdout, run continues, ends [SUCCESS] exit 0 | loud, stops, alerts | Raise and exit 1 with an alert. |
| `tools/new_repo.py:3582` | repo create fails | stdout, ends [SUCCESS] exit 0 | loud, stops, alerts | Raise and exit 1 with an alert. |
| `tools/new_repo.py:3604` | git remote add fails | warning, continues | loud, stops, alerts | Raise. |
| `tools/new_repo.py:3613` | initial push fails | warning, every later GitHub step skipped, [SUCCESS] exit 0 | loud, stops, alerts | Raise and exit 1 with an alert. |
| `tools/new_repo.py:3628` | star fails | noted as non-fatal | loud, logged, stops, alerts | Fail, or drop the step. |
| `tools/new_repo.py:3643` | workflow upload fails | warning, continues, exit 0 | loud, stops, alerts | Raise. |
| `tools/new_repo.py:3660` | pull fails after the local workflows dir was removed at 3651 | warning, local workflows gone, exit 0 | loud, stops, alerts | Raise, and pull before deleting. |
| `tools/new_repo.py:3672` | settings PATCH fails | warning, exit 0 | loud, logged, stops, alerts | Raise with the cause. |
| `tools/new_repo.py:3686` | protection PUT fails | warning, repo left unprotected, exit 0 | loud, logged, stops, alerts | Raise with the cause. |
| `tools/new_repo.py:3690` | some labels fail | only a count printed, continues | loud, stops, alerts | Fail when created is less than total. |
| `tools/new_repo.py:3709` | Dependabot enablement fails | warning, exit 0 | loud, stops, alerts | Raise. |
| `tools/new_repo.py:3731` | plaintext PEM missing | warning, status string, exit 0 | loud, stops, alerts | Raise. |
| `tools/new_repo.py:3742` | encrypted PEM missing | warning, exit 0 | loud, stops, alerts | Raise. |
| `tools/new_repo.py:3745` | PEM decrypt fails | warning, exit 0 | loud, stops, alerts | Raise. |
| `tools/new_repo.py:3780` | GitHub-side verification fails | FAIL line, then only a warning at 3861, exit 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:3843` | sentinel check could not run | excluded from the denominator | loud, stops, alerts | Count it as a failure. |
| `tools/new_repo.py:3847` | classic PAT not configured | stdout ERROR, falls through to [SUCCESS] exit 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:3853` | gpg decrypt fails | stdout ERROR, [SUCCESS] exit 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:3861` | GitHub-side checks failed | warning, exit 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:3881` | a hook failed | warning, exit 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/new_repo.py:3885` | printed unconditionally after any of the failures above | main returns None, process exits 0 | loud, stops, alerts | FIXED in #4136: failed_steps names it, the run exits 1 and alerts |
| `tools/orchestrate.py:78` | started_at unparseable | elapsed shown as "?" in a progress display only | compliant | none |
| `tools/orchestrate.py:269` | merge driver missing | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/orchestrate.py:280` | profile invalid | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/orchestrate.py:299` | provider exhausted | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/orchestrate.py:328` | orchestrate raises anything other than the three caught types | traceback, no alert from this entry point | alerts | Catch Exception at main, alert_operator, exit 1. |
| `tools/orchestrate.py:360` | unverified-requirements banner cannot be read | swallowed with pass, so the run can read as verified | loud, logged, stops, alerts | Log ERROR to stderr, alert, exit non-zero. |
| `tools/orchestrate.py:381` | a stage failed | banner on stdout, exit 1; no alert call in this file (relies on the graph's halt) | loud | Write the banner to stderr. |
| `tools/orchestrate.py:409` | concurrent orchestration | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/orchestrate.py:412` | ValueError from the pipeline | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/pat_smoke_test.py:86` | GET /user body not JSON | login becomes empty and is reported as the wrong account, cause lost | logged, alerts | Report the parse failure as its own FAIL with the cause. |
| `tools/pat_smoke_test.py:95` | smoke test fails | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/remediate_fleet_branch_protection.py:95` | repo GET errors | None with no cause; caller prints a generic ERROR to stdout | loud, logged, alerts | Raise with the cause. |
| `tools/remediate_fleet_branch_protection.py:97` | repo GET rejected | None with no status | loud, logged, alerts | Raise with status and body. |
| `tools/remediate_fleet_branch_protection.py:109` | protection GET errors | None, read as unprotected; apply would PUT over it | loud, logged, stops, alerts | Raise; only 404 means unprotected. |
| `tools/remediate_fleet_branch_protection.py:113` | protection GET 403/5xx | None, read as unprotected | loud, logged, stops, alerts | Raise; only 404 means unprotected. |
| `tools/remediate_fleet_branch_protection.py:179` | PUT errors | stdout, False, next repo, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/remediate_fleet_branch_protection.py:254` | any repo failed | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/require_status_check.py:98` | branch unprotected | None; caller refuses and exits 1 | compliant | none |
| `tools/require_status_check.py:134` | GitHub API error | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/require_status_check.py:138` | any refusal or failure | stdout verdict, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/require_status_check.py:181` | adding the context fails | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/run_implementation_spec_workflow.py:293` | git rev-parse fails | falls back to the cwd silently | loud, logged, stops, alerts | Raise naming the cause. |
| `tools/run_implementation_spec_workflow.py:296` | not in a git repo (non-zero rc) | cwd used as target repo | loud, logged, stops, alerts | Refuse without --repo. |
| `tools/run_implementation_spec_workflow.py:335` | run in the AZ root | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/run_implementation_spec_workflow.py:414` | LLD not found | lld_path left empty and the workflow starts anyway | loud, logged, stops, alerts | Refuse before building state. |
| `tools/run_implementation_spec_workflow.py:557` | telemetry module missing | cost telemetry silently dropped | loud, logged, stops, alerts | Remove the guard or alert. |
| `tools/run_implementation_spec_workflow.py:635` | resume contract refused | exit 1, no alert from this file | alerts | Call alert_operator. |
| `tools/run_implementation_spec_workflow.py:683` | node error | stdout, exit 1 at end | loud | Write to stderr. |
| `tools/run_implementation_spec_workflow.py:696` | graph raises | stdout, no type, traceback only with --debug, exit 1 | loud, logged, alerts | ERROR to stderr with type, alert_operator. |
| `tools/run_implementation_spec_workflow.py:727` | bad issue | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/run_implementation_spec_workflow.py:738` | repo missing | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/run_janitor_workflow.py:85` | git rev-parse fails | return code ignored, repo_root may be empty | loud, logged, stops, alerts | Check the return code. |
| `tools/run_janitor_workflow.py:157` | not a git repo | --silent suppresses the only message, exit 2 | loud, logged, alerts | Always write the ERROR and alert. |
| `tools/run_janitor_workflow.py:169` | graph state lacks exit_code | defaults to 0 (success) | loud, logged, stops, alerts | Raise when exit_code is missing. |
| `tools/run_janitor_workflow.py:170` | graph raises | stderr only when not silent, no type, exit 2 | loud, logged, alerts | Always write ERROR with type and alert. |
| `tools/secret-inventory.sh:84` | git check-ignore errors | error hidden and reported as **NO** | loud, logged, stops, alerts | Distinguish exit 1 from other codes and fail. |
| `tools/secret-inventory.sh:106` | find errors (permissions, bad dir) | stderr discarded; process substitution failure ignored by set -e; inventory incomplete, exit 0 | loud, logged, stops, alerts | Capture find status and fail. |
| `tools/secret-inventory.sh:140` | grep errors | stderr discarded and status forced true | loud, logged, stops, alerts | Treat exit codes above 1 as failure. |
| `tools/sentinel_migrate.py:71` | audit CSV missing | unhandled, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/sentinel_migrate.py:166` | field missing from the GET response | default written into the PUT | logged, stops, alerts | Raise on a missing field. |
| `tools/sentinel_migrate.py:209` | GET protection fails | ERROR string printed to stdout, main exits 0 | loud, stops, alerts | Exit 1 with an alert. |
| `tools/sentinel_migrate.py:215` | unexpected protection shape | REFUSING string, exit 0 | loud, stops, alerts | Exit 1 with an alert. |
| `tools/sentinel_migrate.py:222` | worker check not green | REFUSING string, exit 0 | loud, stops, alerts | Exit 1 with an alert. |
| `tools/sentinel_migrate.py:239` | PUT fails | ERROR string, exit 0 | loud, stops, alerts | Exit 1 with an alert. |
| `tools/sentinel_migrate.py:246` | post-PUT verification fails | string, exit 0 | loud, stops, alerts | Exit 1 with an alert. |
| `tools/sentinel_migrate.py:271` | after any ERROR or REFUSING result | always exits 0 | stops, alerts | Track failures and exit non-zero. |
| `tools/speedrun_archive.py:97` | archive incomplete | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/speedrun_archive.py:111` | restore refused | stdout, exit 2 | loud, alerts | ERROR to stderr and alert. |
| `tools/speedrun_archive.py:113` | restore fails | stdout, no type, exit 2 | loud, logged, alerts | ERROR to stderr with type and alert. |
| `tools/speedrun_archive.py:120` | restore from an incomplete archive | warning, exit 0 | loud, stops, alerts | Exit non-zero with an alert. |
| `tools/speedrun_archive.py:136` | verify cannot run | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/speedrun_archive.py:159` | verify fails | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/update-doc-refs.py:158` | a markdown file unreadable | Warning on stdout, file skipped, exit 0 | loud, logged, stops, alerts | Raise, alert, exit 1. |
| `tools/update-doc-refs.py:219` | file update fails | stdout, returns 0, run exits 0 | loud, logged, stops, alerts | Raise, alert, exit 1. |
| `tools/update-doc-refs.py:261` | bad project path | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/update-doc-refs.py:278` | report write fails | unhandled, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/upgrade_boostgauge_auto_reviewer.py:134` | workflow file absent | (None, None); caller refuses with exit 1 | compliant | none |
| `tools/upgrade_boostgauge_auto_reviewer.py:150` | rulesets endpoint 404 | empty list meaning no rulesets, documented | compliant | none |
| `tools/upgrade_boostgauge_auto_reviewer.py:253` | contents PUT fails | stdout detail, then raise_for_status; finally restores; traceback, no alert | loud, alerts | Catch at main, alert, exit 1. |
| `tools/upgrade_boostgauge_auto_reviewer.py:312` | file absent | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/upgrade_boostgauge_auto_reviewer.py:358` | ruleset bypass restore fails | WARNING on stdout, script continues and exits 0 with admin bypass left in place | loud, logged, stops, alerts | ERROR to stderr, alert, exit non-zero. |
| `tools/upgrade_boostgauge_auto_reviewer.py:368` | enforce_admins restore fails | WARNING on stdout, exit 0 with protection weakened | loud, logged, stops, alerts | ERROR to stderr, alert, exit non-zero. |
| `tools/verdict-analyzer.py:67` | registry not found | falls back to scanning the cwd | loud, logged, stops, alerts | Refuse without a registry or --repos. |
| `tools/verdict-analyzer.py:88` | a verdict fails to parse or store | logger.error, continues, exit 0 | stops, alerts | Raise, alert, exit 1. |
| `tools/verdict-analyzer.py:119` | template missing | ERROR log, return 1 | alerts | Call alert_operator. |
| `tools/verdict_analyzer/database.py:53` | database schema newer than this code | no branch handles it, proceeds silently | loud, logged, stops, alerts | Raise on an unknown newer version. |
| `tools/verdict_analyzer/database.py:278` | foreign keys never enabled (no PRAGMA foreign_keys) | CASCADE does not run, blocking_issues orphaned silently | loud, logged, stops, alerts | Enable PRAGMA foreign_keys=ON at connect or delete the child rows explicitly. |
| `tools/verify_gpg_agent_ttl.py:35` | infrastructure problem | stderr, exit 2 | alerts | Call alert_operator. |
| `tools/verify_gpg_agent_ttl.py:59` | gpgconf --list-dirs fails | CalledProcessError traceback, exit 1 instead of the documented 2, no alert | logged, alerts | Catch, die() with stderr, alert. |
| `tools/verify_gpg_agent_ttl.py:79` | malformed conf line | skipped; the directive then reads as missing and FAILs | compliant | none |
| `tools/verify_gpg_agent_ttl.py:94` | gpgconf --list-options fails | traceback, no alert | logged, alerts | Catch, die() with stderr, alert. |
| `tools/verify_gpg_agent_ttl.py:156` | TTL non-compliant | remediation on stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/widen_boostgauge_auto_reviewer_trigger.py:85` | any GitHub REST call fails | HTTPError ends the process, no alert | alerts | Catch at main, alert, exit 1. |
| `tools/widen_boostgauge_auto_reviewer_trigger.py:96` | file shape unexpected | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/widen_boostgauge_auto_reviewer_trigger.py:123` | branch exists | reused without checking its base | logged, stops, alerts | Verify the branch head before reuse. |
| `tools/widen_boostgauge_auto_reviewer_trigger.py:170` | mergeable poll times out | stdout, exit 1 | loud, alerts | ERROR to stderr and alert. |
| `tools/_gate.py:73` | stdin closes before the confirmation phrase is typed | converts EOF to an empty answer, which then fails the phrase match and exits 2 | loud, alerts | write an ERROR line to stderr naming EOF as the cause and call alert_operator before exiting 2 |
| `tools/_gate.py:89` | the refusal log cannot be written (OSError) | unhandled exception ends the process before the refusal message is printed | loud, logged, alerts | catch OSError, log ERROR with the path and cause, alert, exit 2 |
| `tools/_gate.py:92` | gate phrase mismatch | prints the refusal to stdout, appends JSONL, exits 2 | loud, alerts | print at ERROR to stderr and call alert_operator before sys.exit |
| `tools/_gh_retry.py:90` | network error on a GitHub call | retries with backoff, then re-raises on exhaustion to the caller | compliant | none |
| `tools/_gh_retry.py:101` | non-integer Retry-After header | ValueError escapes, and callers that catch only RequestException crash without context | loud, logged, alerts | parse defensively and raise requests.HTTPError carrying the header value |
| `tools/_gh_retry.py:127` | permanent 4xx response | returned as-is per the docstring contract ("caller decides what to do with non-retried 4xx") | compliant | none |
| `tools/archive_worktree_lineage.py:53` | the worktree has no lineage to archive before the PR | stdout note, archives nothing, prints "Done" and exits 0 | loud, logged, stops, alerts | treat missing lineage as a failure (ERROR, alert, exit 1), or document it as a legitimate state |
| `tools/archive_worktree_lineage.py:74` | the copy fails partway (OSError), after the previous archive was already renamed aside | unhandled traceback, exit 1, archive left partial | loud, logged, alerts | catch, log ERROR with issue/src/dest, alert_operator, re-raise |
| `tools/archive_worktree_lineage.py:94` | git rev-parse fails | returns None, read as "not a linked worktree"; git rc and stderr discarded | logged, alerts | carry the git rc and stderr into the refusal and alert |
| `tools/archive_worktree_lineage.py:108` | path is not a linked worktree | message to stderr, exit 1 | loud, alerts | prefix ERROR and call alert_operator before exiting |
| `tools/archive_worktree_lineage.py:124` | git add of the archived lineage fails | CalledProcessError traceback, exit 1 | loud, logged, alerts | catch, log ERROR with stderr and issue, alert, exit 1 |
| `tools/archive_worktree_lineage.py:131` | git diff --cached errors (rc 128) | any non-zero rc is read as "staged changes", reported as success | loud, logged, stops, alerts | accept only rc 1 as staged and fail loudly on any other non-zero rc |
| `tools/archive_worktree_lineage.py:145` | parent-process enumeration fails | pass; the own-lineage set is silently incomplete | loud, logged, stops, alerts | log ERROR and raise; the busy-process guard cannot be trusted |
| `tools/archive_worktree_lineage.py:189` | --evict-venv was requested but cannot run | silent return, exit 0 | loud, logged, stops, alerts | report ERROR that the requested eviction did not run and exit non-zero |
| `tools/archive_worktree_lineage.py:197` | another process is running from the worktree | refusal on stderr, exit 1 | loud, alerts | prefix ERROR and alert_operator |
| `tools/archive_worktree_lineage.py:222` | poetry env remove --all returns non-zero | prints WARNING to stdout, continues, exits 0 | loud, stops, alerts | log ERROR with rc/stderr, alert, exit non-zero |
| `tools/assemblyzero-harvest.py:27` | the config module cannot be imported | config=None, silently falls back to a derived path | loud, logged, stops, alerts | let the ImportError raise, or log ERROR and alert |
| `tools/assemblyzero-harvest.py:63` | the registry file is missing | ERROR on stderr, exit 1 | alerts | call alert_operator before exiting |
| `tools/assemblyzero-harvest.py:68` | the registry has invalid JSON | unhandled traceback, exit 1 | loud, logged, alerts | catch JSONDecodeError, log ERROR with the path, alert, exit 1 |
| `tools/assemblyzero-harvest.py:75` | the AssemblyZero commands baseline directory is missing | empty baseline, so every child command is reported as a promotion candidate | loud, logged, stops, alerts | raise when the baseline directory is absent |
| `tools/assemblyzero-harvest.py:83` | the AssemblyZero tools baseline directory is missing | empty baseline, so every child tool is flagged | loud, logged, stops, alerts | raise when the baseline directory is absent |
| `tools/assemblyzero-harvest.py:95` | the AssemblyZero templates baseline directory is missing | empty baseline, so every child dir is flagged | loud, logged, stops, alerts | raise when the baseline directory is absent |
| `tools/assemblyzero-harvest.py:136` | undecodable bytes in a tool file | silently dropped; genericity judged on partial text | loud, logged, stops, alerts | read strictly and raise with the file path |
| `tools/assemblyzero-harvest.py:199` | a project's settings.local.json is unreadable | returns no candidates silently | loud, logged, stops, alerts | log ERROR with project/path/cause, alert, exit non-zero |
| `tools/assemblyzero-harvest.py:213` | AssemblyZero's own settings are unreadable | pass; empty baseline, so every project permission is flagged | loud, logged, stops, alerts | raise; the comparison baseline is required |
| `tools/assemblyzero-harvest.py:255` | CLAUDE.md is unreadable | returns no candidates silently | loud, logged, stops, alerts | log ERROR and raise |
| `tools/assemblyzero-harvest.py:308` | a registered active project's path is missing | skipped (message only with --verbose) yet still listed as scanned; exit 0 | loud, logged, stops, alerts | ERROR, alert, exit non-zero for a missing active project |
| `tools/assemblyzero-harvest.py:446` | the registry has no children | ERROR on stderr, exit 1 | alerts | call alert_operator |
| `tools/assemblyzero-permissions.py:40` | the config module cannot be imported | config=None, silent fallback path | loud, logged, stops, alerts | let it raise, or ERROR plus alert |
| `tools/assemblyzero-permissions.py:102` | a settings file has invalid JSON | prints "ERROR" to stdout and returns None, which callers read as "no settings file" | loud, stops, alerts | raise; log ERROR to stderr with path and cause, alert |
| `tools/assemblyzero-permissions.py:215` | master settings and backup both invalid | stdout note, recorded failed, exit 1 at the end | loud, alerts | ERROR on stderr and alert_operator |
| `tools/assemblyzero-permissions.py:219` | master settings invalid with no backup | stdout note, exit 1 at the end | loud, alerts | ERROR on stderr and alert_operator |
| `tools/assemblyzero-permissions.py:276` | settings cannot be serialized | raises without chaining; the tool dies with a traceback | loud, alerts | raise from e, with an ERROR log and alert at the entry point |
| `tools/assemblyzero-permissions.py:292` | the written temp file fails validation | raises; the tool dies with a traceback | loud, alerts | ERROR log and alert at the entry point |
| `tools/assemblyzero-permissions.py:492` | a project's settings are missing or invalid during --audit | returns an error dict; print_audit_report prints ERROR to stdout; exit 0 | loud, stops, alerts | raise, or have main exit non-zero with stderr ERROR and alert |
| `tools/assemblyzero-permissions.py:578` | clean_project cannot load settings | main ignores the return value (--clean, and --merge-up step 1 carry on); exit 0 | loud, logged, stops, alerts | check the result in main, ERROR, alert, exit non-zero |
| `tools/assemblyzero-permissions.py:641` | quick-check cannot load settings | stdout, returns 2 | loud, alerts | write to stderr and alert |
| `tools/assemblyzero-permissions.py:685` | a project's settings unloadable (including invalid JSON) during merge-up | skipped; merge proceeds on partial data | loud, logged, stops, alerts | stop the merge with ERROR and alert |
| `tools/assemblyzero-permissions.py:937` | master settings unloadable | stdout, exit 1 | loud, alerts | stderr plus alert_operator |
| `tools/assemblyzero-permissions.py:946` | --restore with no backup | stdout, exit 1 | loud, alerts | stderr plus alert_operator |
| `tools/assemblyzero_config.py:187` | path normalization fails | pass; keeps the regex-sanitized path | loud, logged, stops, alerts | raise ConfigError with the cause |
| `tools/assemblyzero_config.py:192` | a path still contains '..' after sanitization | WARNING; the path becomes "" and is returned to callers | loud, stops, alerts | raise ConfigError naming the key |
| `tools/assemblyzero_config.py:213` | no config file | returns derived DEFAULTS | compliant | none |
| `tools/assemblyzero_config.py:219` | the operator's config file is invalid JSON | WARNING; defaults silently replace the operator's configuration | loud, logged, stops, alerts | raise ConfigError with path and cause |
| `tools/assemblyzero_config.py:223` | the config file cannot be read | WARNING; defaults used | loud, logged, stops, alerts | raise ConfigError |
| `tools/assemblyzero_config.py:231` | the config fails schema validation | WARNING with details at DEBUG only; defaults used | loud, logged, stops, alerts | raise ConfigError listing the errors |
| `tools/assemblyzero_config.py:259` | the requested format key is missing | silently falls back to the windows spelling or "" | loud, logged, stops, alerts | raise ConfigError for a missing key/format |
| `tools/audit_cerberus_health.py:84` | gh repo list fails | CalledProcessError traceback, exit 1 | loud, logged, alerts | catch, ERROR with stderr, alert, exit 1 |
| `tools/audit_cerberus_health.py:92` | gh api fails (auth, rate limit, network) | read as "workflow not deployed"; the repo drops out of the pre-rotation audit | loud, logged, stops, alerts | distinguish 404 from other failures and raise on the latter |
| `tools/audit_cerberus_health.py:106` | the runs API call fails | empty list gives an UNKNOWN classification; the tool can exit 0 | loud, logged, stops, alerts | raise with repo/rc/stderr; exit non-zero |
| `tools/audit_cerberus_health.py:110` | runs JSON cannot be parsed | empty list, classified UNKNOWN | loud, logged, stops, alerts | raise with the repo and parse error |
| `tools/audit_cerberus_health.py:140` | a run timestamp cannot be parsed | the run is silently dropped from classification | loud, logged, stops, alerts | raise with the run id and value |
| `tools/audit_fleet_rulesets.py:175` | gh times out | returns rc 124 with a message; callers check rc and record an error | compliant | none |
| `tools/audit_fleet_rulesets.py:177` | gh cannot be executed | returns rc 1 with a message | compliant | none |
| `tools/audit_fleet_rulesets.py:187` | repo listing fails | message on stderr, exit 1 | loud, alerts | ERROR prefix plus alert_operator |
| `tools/audit_fleet_rulesets.py:203` | 404 (also returned for a missing repo or insufficient token) | read as "zero rulesets", no error | loud, logged, stops, alerts | confirm the repo exists; otherwise record the error and fail |
| `tools/audit_fleet_rulesets.py:210` | unexpected payload shape | read as zero rulesets | loud, logged, stops, alerts | return an error naming the payload type |
| `tools/audit_fleet_rulesets.py:272` | listing a repo's rulesets fails | recorded in the TSV and stdout; the run continues | loud, stops, alerts | log ERROR to stderr, alert, exit non-zero at the end |
| `tools/audit_fleet_rulesets.py:278` | a ruleset summary has no id | silently skipped while still counted in ruleset_count | loud, logged, stops, alerts | record an error for the repo |
| `tools/audit_fleet_rulesets.py:356` | one or more repos errored | exits 0 regardless | stops, alerts | return 1 when any verdict has an error, after alerting |
| `tools/audit_halt_sites.py:86` | the baseline file is unreadable | stated=None, reported as drift on every count (exit 1), cause discarded | loud, logged, alerts | log ERROR with path and exception, alert |
| `tools/audit_halt_sites.py:234` | the walker could not parse some files (coverage.files_unparseable) | --check prints PASS and exits 0, ignoring unparsed files | loud, logged, stops, alerts | fail --check when files_unparseable is non-empty |
| `tools/audit_halt_sites.py:264` | registry check fails | stdout, exit 1 | loud, alerts | write ERROR to stderr and alert |
| `tools/backfill_issue_audit.py:144` | the gh auth check cannot run | returns False, misreported as "not authenticated"; exit 1 | logged, alerts | report the real cause (timeout or missing gh) and alert |
| `tools/backfill_issue_audit.py:224` | fetching an issue's comments fails | empty list; "No comments on this issue" files are written and counted created | loud, logged, stops, alerts | raise RuntimeError with repo/issue/stderr |
| `tools/backfill_issue_audit.py:228` | the comments payload cannot be parsed | empty list, files written as if no comments | loud, logged, stops, alerts | raise with issue number and parse error |
| `tools/backfill_issue_audit.py:560` | comment fetch raises | error result printed to stdout; the loop continues | loud, alerts | ERROR to stderr and alert |
| `tools/backfill_issue_audit.py:581` | writing audit files fails | error result on stdout; continues, exits 1 at the end with partial output | loud, stops, alerts | ERROR to stderr, alert, stop the run |
| `tools/backfill_issue_audit.py:643` | fetching the issue list fails | ERROR on stderr, then an empty list; main counts 0 errors and exits 0 | stops, alerts | raise or return a failure so main exits 1, and alert |
| `tools/backfill_issue_audit.py:809` | gh not authenticated | ERROR stderr, exit 1 | alerts | call alert_operator |
| `tools/check_requirements.py:99` | the requirements gate could not run | ERROR on stderr, exit 2 | alerts | call alert_operator before returning EXIT_ERROR |
| `tools/collect_cross_project_metrics.py:67` | config load fails | ERROR log, return 2 | alerts | call alert_operator |
| `tools/collect_cross_project_metrics.py:124` | collecting one repo's metrics fails | WARNING (traceback only with --verbose); continues and writes partial aggregate output; exit 1 | loud, stops, alerts | log ERROR with the exception, alert, and write no partial output |
| `tools/collect_cross_project_metrics.py:132` | every repo failed | ERROR, return 2 | alerts | call alert_operator |
| `tools/collect_cross_project_metrics.py:148` | output write fails | ERROR, return 2 | alerts | call alert_operator |
| `tools/dependabot_review.py:121` | the run log cannot be written | pass; the log silently stops recording | loud, logged, stops, alerts | log ERROR once to the terminal and alert |
| `tools/dependabot_review.py:125` | the terminal cannot encode text | lossy terminal render; the UTF-8 log copy written first is faithful | compliant | none |
| `tools/dependabot_review.py:160` | flushing the log file fails | pass | loud, logged, stops, alerts | log ERROR and alert |
| `tools/dependabot_review.py:164` | flushing the stream fails | pass | loud, logged, stops, alerts | log ERROR and alert |
| `tools/dependabot_review.py:198` | the stream cannot be reconfigured to UTF-8 | pass; _Tee.write's fallback covers it | compliant | none |
| `tools/dependabot_review.py:221` | the per-run log cannot be created | WARNING on stderr; the run continues | loud, stops, alerts | ERROR plus alert, or stop |
| `tools/dependabot_review.py:410` | a subprocess times out | returns rc 124 and prints TIMEOUT to stdout | loud, alerts | print ERROR to stderr with the command; callers already check rc |
| `tools/dependabot_review.py:552` | git worktree add fails | ERROR on stderr; the PR is recorded errored; the run ends exit 0 | alerts | alert_operator, and make the run exit non-zero (see line 2402) |
| `tools/dependabot_review.py:589` | venv eviction fails | return code ignored | loud, logged, stops, alerts | check rc and raise or record an error |
| `tools/dependabot_review.py:776` | package.json is unreadable | None, reported as "no runnable npm test script"; the real cause is lost | loud, logged, alerts | raise or return the parse/read error so the deferral states it |
| `tools/dependabot_review.py:806` | git rev-parse fails (rc ignored) or not a linked worktree | refusal on stderr; node_modules left; cleanup continues | loud, stops, alerts | ERROR with git rc/stderr and alert; mark the PR errored |
| `tools/dependabot_review.py:817` | node_modules removal fails | WARNING on stderr; continues | loud, stops, alerts | ERROR, alert, record the PR errored |
| `tools/dependabot_review.py:844` | a touched manifest dir has no package.json | dir skipped; the JS gate can pass with "nothing to run" | loud, logged, stops, alerts | fail the gate when a touched dir cannot be tested |
| `tools/dependabot_review.py:950` | the mergeable query is unreadable | WARNING on stdout; polls to timeout, then deferred | loud, stops, alerts | ERROR to stderr with the raw payload and stop polling |
| `tools/dependabot_review.py:1004` | merge rc ignored | merged state re-queried; False makes the caller mark the PR errored | compliant | none |
| `tools/dependabot_review.py:1022` | posting an @dependabot recreate/rebase comment fails | result discarded | loud, logged, stops, alerts | check rc and record an error for the PR |
| `tools/dependabot_review.py:1103` | the gh api base/main SHA queries fail | reported as "not stale"; cause discarded | loud, logged, alerts | log ERROR with rc/stderr and alert |
| `tools/dependabot_review.py:1152` | the reviews query fails | read as "not deferred" (re-audit); silent | loud, logged, alerts | log ERROR with rc/stderr and alert |
| `tools/dependabot_review.py:1155` | the reviews payload cannot be parsed | False, silent | loud, logged, alerts | log ERROR and alert |
| `tools/dependabot_review.py:1191` | the reviews query fails | read as "already reviewed"; silent | loud, logged, alerts | log ERROR and alert |
| `tools/dependabot_review.py:1194` | the reviews payload cannot be parsed | True, silent | loud, logged, alerts | log ERROR and alert |
| `tools/dependabot_review.py:1230` | PR listing fails in the zero-review pre-pass | continue, silently | loud, logged, alerts | log ERROR with the repo and alert |
| `tools/dependabot_review.py:1373` | git status fails (quiet) | empty output is read as a clean worktree | loud, logged, stops, alerts | check rc and report ERROR |
| `tools/dependabot_review.py:1449` | git branch --list fails | the orphan canary reports clean and processing proceeds | loud, logged, stops, alerts | raise or mark the repo errored |
| `tools/dependabot_review.py:1464` | git worktree list fails | the orphan canary reports clean | loud, logged, stops, alerts | raise or mark the repo errored |
| `tools/dependabot_review.py:1529` | the baseline worktree is unusable | (0,"") makes the caller write "base is green -- this bump introduced the failure" into the review | logged, alerts | return a distinct "baseline unavailable" result and alert |
| `tools/dependabot_review.py:1564` | gh pr checkout fails | stdout; PR errored | loud, alerts | stderr with gh stderr and alert |
| `tools/dependabot_review.py:1573` | gh pr diff fails | the JS gate is skipped entirely, so an npm bump can merge after only the Python gate | loud, logged, stops, alerts | error the PR when the changed files cannot be listed |
| `tools/dependabot_review.py:1591` | poetry install fails | stdout; counted as deferred, not errored | loud, alerts | stderr ERROR and alert |
| `tools/dependabot_review.py:1594` | posting the install-failure review fails | bool return ignored | loud, logged, stops, alerts | check the return and record an error |
| `tools/dependabot_review.py:1678` | posting the deferral review fails | bool return ignored | loud, logged, stops, alerts | check the return and record an error |
| `tools/dependabot_review.py:1701` | the PR body edit fails | stdout; errored | loud, alerts | stderr ERROR and alert |
| `tools/dependabot_review.py:1725` | the state query fails | "" is read as an in-flight state; the PR is deferred as "cerberus-arrival tail" | loud, logged, alerts | check rc and mark errored on failure |
| `tools/dependabot_review.py:1752` | merge did not land | stdout; errored | loud, alerts | stderr ERROR and alert |
| `tools/dependabot_review.py:1793` | worktree/branch cleanup fails | WARNING on stderr; the PR outcome is unchanged; the run continues and exits 0 | loud, stops, alerts | record errored, alert, exit non-zero |
| `tools/dependabot_review.py:1850` | gh repo list fails | stderr, exit 1 | loud, alerts | ERROR prefix plus alert |
| `tools/dependabot_review.py:1866` | gh search fails | stderr, exit 1 | loud, alerts | ERROR prefix plus alert |
| `tools/dependabot_review.py:1922` | no local clone | stderr; recorded errored | loud, alerts | ERROR plus alert |
| `tools/dependabot_review.py:1961` | PR listing fails | ERROR on stderr; recorded errored; continues | alerts | alert_operator |
| `tools/dependabot_review.py:2034` | git cannot be executed | (1,"") makes is_linked_worktree return False, so the worktree guard passes | loud, logged, stops, alerts | raise; the guard cannot run |
| `tools/dependabot_review.py:2041` | git rev-parse fails | the guard reports "not a worktree" and the tool proceeds | loud, logged, stops, alerts | raise when git cannot answer |
| `tools/dependabot_review.py:2051` | path resolution fails | pass; falls back to the parts heuristic | loud, logged, stops, alerts | raise |
| `tools/dependabot_review.py:2302` | a repo worker raises (including SystemExit) | ERROR printed to stdout; repo recorded errored; continues | loud, alerts | stderr ERROR with traceback and alert |
| `tools/dependabot_review.py:2402` | any PR or repo errored | main returns None, so the process exits 0 after the summary | stops, alerts | exit non-zero when results["errored"] is non-empty, after alert_operator |
| `tools/deploy_cerberus_secrets.py:75` | gh repo list fails | CalledProcessError traceback | loud, logged, alerts | catch, ERROR with stderr, alert, exit 1 |
| `tools/deploy_cerberus_secrets.py:102` | public-key fetch raises | None; the exception is discarded | loud, logged, alerts | log ERROR with repo/scope/exception |
| `tools/deploy_cerberus_secrets.py:105` | public-key fetch returns non-2xx | None; the status is discarded | loud, logged, alerts | log ERROR with status and body |
| `tools/deploy_cerberus_secrets.py:153` | secret PUT raises | False; the cause is discarded | loud, logged, alerts | log ERROR with repo/scope/name/exception |
| `tools/deploy_cerberus_secrets.py:208` | listing secrets raises | read as "secrets missing"; the repo is targeted; cause discarded | loud, logged, alerts | log ERROR and raise |
| `tools/deploy_cerberus_secrets.py:212` | listing secrets returns non-2xx | read as missing; cause discarded | loud, logged, alerts | log ERROR with status and raise |
| `tools/deploy_cerberus_secrets.py:340` | gpg decrypt fails | ERROR on stderr, exit 1 | alerts | call alert_operator |
| `tools/deploy_cerberus_secrets.py:405` | the deploy to a repo fails | stdout; continues; exit 1 at the end | loud, alerts | ERROR to stderr and alert |
| `tools/fleet_delete_pr_sentinel.py:147` | code-search discovery fails | HTTPError traceback | loud, logged, alerts | catch, ERROR, alert, exit 1 |
| `tools/fleet_delete_pr_sentinel.py:362` | the PR never becomes mergeable | returns a status line not counted as an error; exit 0 | loud, stops, alerts | count as errored, ERROR, alert, exit non-zero |
| `tools/fleet_delete_pr_sentinel.py:369` | the merge fails | returns "merge failed" text without "ERROR", so it is not counted; exit 0 | loud, logged, stops, alerts | raise or count errored and exit non-zero with an alert |
| `tools/fleet_delete_pr_sentinel.py:395` | invalid argument | stdout, exit 1 | loud, alerts | stderr ERROR |
| `tools/fleet_delete_pr_sentinel.py:414` | over the safety cap | stdout, exit 1 | loud, alerts | stderr ERROR and alert |
| `tools/fleet_delete_pr_sentinel.py:428` | processing a repo fails | stdout line; continues | loud, stops, alerts | stderr ERROR, alert, exit non-zero at the end |
| `tools/fleet_delete_pr_sentinel.py:430` | an unexpected error processing a repo | stdout line; continues | loud, stops, alerts | stderr ERROR with traceback, alert, exit non-zero |
| `tools/fleet_delete_pr_sentinel.py:441` | repos errored or were not merged | always exits 0 | stops, alerts | return 1 when errors > 0 |
| `tools/github_protection_audit.py:95` | the gh api call times out | status 0, classified ERROR; the run continues and exits 0 | loud, stops, alerts | count ERROR verdicts and exit non-zero with an alert |
| `tools/github_protection_audit.py:112` | the HTTP status line cannot be parsed | pass; status inferred later | loud, logged, stops, alerts | raise with the raw line |
| `tools/github_protection_audit.py:142` | an unclassified gh failure | 999 falls through classify_verdict to "INFORMATIONAL" | loud, logged, stops, alerts | classify unknown statuses as ERROR and fail the run |
| `tools/github_protection_audit.py:162` | the gh api call times out (silent variant) | status 0; audit checks record WARN | loud, stops, alerts | ERROR plus non-zero exit |
| `tools/github_protection_audit.py:176` | an unclassified gh failure | 999; audit records WARN "HTTP 999" | loud, logged, stops, alerts | raise or record ERROR and exit non-zero |
| `tools/github_protection_audit.py:204` | gh auth token fails | the token type is reported "unknown"; run continues | loud, logged, alerts | log ERROR with stderr |
| `tools/github_protection_audit.py:236` | repo listing cannot run | returns [] silently; main reports "no repos found", cause lost | logged, alerts | ERROR with the cause and alert |
| `tools/github_protection_audit.py:515` | wiki ls-remote cannot run | pass; reads as "no wiki content" | loud, logged, stops, alerts | record an ERROR probe result |
| `tools/github_protection_audit.py:768` | the signatures API fails | WARN; continues | loud, stops, alerts | record ERROR and exit non-zero |
| `tools/github_protection_audit.py:776` | protection unreadable (0, 999, other) | WARN; continues | loud, stops, alerts | record ERROR and exit non-zero |
| `tools/github_protection_audit.py:782` | the rulesets API fails | count 0, WARN | loud, logged, stops, alerts | record ERROR when rs_status is not 200 |
| `tools/github_protection_audit.py:802` | wiki ls-remote cannot run | pass; wiki_has_content False | loud, logged, stops, alerts | record ERROR |
| `tools/github_protection_audit.py:808` | the repo API fails | wiki_enabled False, so A10 reports PASS "Wiki disabled" | loud, logged, stops, alerts | record ERROR instead of PASS |
| `tools/github_protection_audit.py:903` | settings.json unreadable | pass; no check recorded | loud, logged, stops, alerts | record a FAIL/ERROR hook check |
| `tools/github_protection_audit.py:920` | secret-guard.sh unreadable | pass; no checks recorded | loud, logged, stops, alerts | record ERROR |
| `tools/github_protection_audit.py:945` | bash-gate.sh unreadable | pass | loud, logged, stops, alerts | record ERROR |
| `tools/github_protection_audit.py:970` | global settings.json unreadable | pass | loud, logged, stops, alerts | record ERROR |
| `tools/github_protection_audit.py:993` | global settings.local.json unreadable | pass | loud, logged, stops, alerts | record ERROR |
| `tools/github_protection_audit.py:1402` | FAIL, ERROR or VULNERABLE results, or checks that could not run | always exits 0 | stops, alerts | exit non-zero on any ERROR/FAIL and alert |
| `tools/golden_disasters.py:66` | a case's fixtures are missing | digest "MISSING" printed; --list exits 0 | loud, logged, stops, alerts | ERROR with the case and path; exit non-zero |
| `tools/land_1104_auto_reviewer_fix.py:99` | network error or timeout | unhandled traceback | loud, logged, alerts | catch RequestException, ERROR, alert, exit 1 |
| `tools/land_1104_auto_reviewer_fix.py:106` | contents GET fails | stderr, exit 1 | loud, alerts | ERROR prefix plus alert |
| `tools/land_1104_auto_reviewer_fix.py:117` | the expected dispatch block is missing | ERROR on stderr, exit 1 | alerts | alert_operator |
| `tools/land_1104_auto_reviewer_fix.py:128` | the main ref GET fails | stderr with status only, exit 1 | loud, logged, alerts | include the body; ERROR plus alert |
| `tools/land_1104_auto_reviewer_fix.py:138` | branch creation returns 422 for any validation reason | read as "already exists"; continues | loud, logged, stops, alerts | verify the branch exists at the expected SHA, else fail |
| `tools/land_1104_auto_reviewer_fix.py:142` | branch creation fails | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/land_1104_auto_reviewer_fix.py:164` | the contents PUT fails | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/land_1104_auto_reviewer_fix.py:200` | PR creation fails | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/land_1104_auto_reviewer_fix.py:209` | a poll GET fails | silently retried until the timeout | loud, logged, alerts | log ERROR with the status; fail after repeated errors |
| `tools/land_1104_auto_reviewer_fix.py:217` | the PR never becomes mergeable | stderr, exit 1 | loud, alerts | ERROR with the last state plus alert |
| `tools/land_1104_auto_reviewer_fix.py:224` | the merge fails | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/land_1104_auto_reviewer_fix.py:278` | the branch blob GET fails | stderr exit 1; the status is discarded at line 148 | loud, logged, alerts | carry status/body; ERROR plus alert |
| `tools/land_aletheia_775.py:80` | git show of the local branch fails | CalledProcessError traceback | loud, logged, alerts | catch, ERROR with stderr, alert, exit 1 |
| `tools/land_aletheia_775.py:88` | GitHub API calls fail (this and the other raise_for_status sites) | HTTPError traceback | loud, logged, alerts | wrap main in a handler that logs ERROR and alerts |
| `tools/land_aletheia_775.py:97` | 422 for any reason on branch creation | read as "already exists" | loud, logged, stops, alerts | verify the branch exists, else fail |
| `tools/land_aletheia_775.py:174` | the remote branch delete fails (status also never checked) | pass | loud, logged, stops, alerts | check the status; ERROR plus alert on failure |
| `tools/land_aletheia_775.py:187` | content guard fails | stdout, exit 1 | loud, alerts | stderr plus alert |
| `tools/land_aletheia_775.py:190` | content guard fails | stdout, exit 1 | loud, alerts | stderr plus alert |
| `tools/land_aletheia_775.py:218` | the PR is not mergeable | stdout, exit 1 | loud, alerts | ERROR to stderr plus alert |
| `tools/land_career_lint_workflow.py:105` | GitHub API calls fail (this and the other raise_for_status sites) | HTTPError traceback | loud, logged, alerts | handler that logs ERROR and alerts |
| `tools/land_career_lint_workflow.py:116` | 422 for any reason on branch creation | read as "already exists" | loud, logged, stops, alerts | verify the branch exists, else fail |
| `tools/land_career_lint_workflow.py:171` | merge conflict | stdout, exit 1 | loud, alerts | stderr ERROR plus alert |
| `tools/land_career_lint_workflow.py:174` | the poll loop runs out without "clean" | timeout message on stdout, exit 1 | loud, alerts | stderr ERROR with the last state plus alert |
| `tools/land_career_lint_workflow.py:184` | the merge fails | stdout, exit 1 | loud, alerts | stderr ERROR plus alert |
| `tools/land_dependabot_skip_1251.py:136` | network error | unhandled traceback | loud, logged, alerts | catch, ERROR, alert, exit 1 |
| `tools/land_dependabot_skip_1251.py:178` | the PR never becomes mergeable | traceback, exit 1 | loud, alerts | ERROR plus alert in the entry point |
| `tools/land_dependabot_skip_1251.py:193` | the local file lacks the marker | stderr, exit 2 | loud, alerts | ERROR prefix plus alert |
| `tools/land_dependabot_skip_1251.py:239` | 422 for any reason on branch creation | read as "already exists" | loud, logged, stops, alerts | verify the branch, else fail |
| `tools/land_dependabot_skip_1251.py:304` | post-merge verification fails | stderr, exit 1 | loud, alerts | ERROR plus alert_operator |
| `tools/mine_quality_patterns.py:164` | telemetry schema mismatch | uncaught in main; traceback, exit 1 | loud, alerts | catch in main, ERROR, alert, exit 1 |
| `tools/mine_quality_patterns.py:201` | the detail field is not JSON | falls back to detail[:64] as the grouping key | compliant | none |
| `tools/mine_quality_patterns.py:344` | the telemetry DB is missing | stderr, exit 1 | loud, alerts | ERROR prefix plus alert |
| `tools/mine_quality_patterns.py:347` | the DB is corrupt | stderr, exit 1 | loud, alerts | ERROR prefix plus alert |
| `tools/mine_verdict_patterns.py:54` | a verdict file is unreadable | None; silently skipped; exit 0 | loud, logged, stops, alerts | ERROR with path/cause and exit non-zero |
| `tools/mine_verdict_patterns.py:64` | the verdict line is not found | defaults to "UNKNOWN", counted among failing verdicts | loud, logged, stops, alerts | raise a parse error naming the file |
| `tools/mine_verdict_patterns.py:375` | the lineage dir is missing | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/mine_verdict_patterns.py:381` | no verdicts | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/modernize_dependencies.py:45` | poetry show fails | warning on stdout; [] makes the tool print "All dependencies are up to date!" and exit 0 | loud, logged, stops, alerts | raise; ERROR, alert, exit 1 |
| `tools/modernize_dependencies.py:101` | the rollback reinstall fails | return code ignored; the venv may not match the restored lock | loud, logged, stops, alerts | check rc; ERROR plus alert, then stop |
| `tools/modernize_dependencies.py:150` | git add fails | return code ignored | loud, logged, stops, alerts | check rc and raise |
| `tools/modernize_dependencies.py:230` | poetry add fails | stdout; recorded failed; exit 1 at the end | loud, alerts | stderr ERROR plus alert |
| `tools/modernize_dependencies.py:245` | tests fail after an update | stdout; rollback; exit 1 at the end | loud, alerts | stderr ERROR plus alert |
| `tools/modernize_dependencies.py:259` | git commit fails | prints OK, counts updated, exits 0 | loud, logged, stops, alerts | treat as failure, ERROR, alert, exit 1 |
| `tools/modernize_dependencies.py:304` | no pyproject | stderr, exit 1 | loud, alerts | ERROR plus alert |
| `tools/replay_run.py:162` | the recording has no final LLD | recorded as a divergence row; exit 0 | loud, stops, alerts | ERROR to stderr and a non-zero exit |
| `tools/replay_run.py:232` | the graph raises during replay | recorded as divergence text in the table; exit 0 | loud, stops, alerts | log ERROR with traceback, alert, exit non-zero |
| `tools/replay_run.py:368` | no runs | stdout, exit 1 | loud, alerts | stderr ERROR plus alert |
| `tools/replay_run.py:398` | runs were skipped or crashed | exits 0 (also the --markdown path at line 374) | stops, alerts | exit non-zero when any result crashed or every run was skipped |
| `tools/run_scout_workflow.py:149` | the internal file cannot load | stdout, exit 1 | loud, alerts | stderr plus alert |
| `tools/run_scout_workflow.py:182` | confirmation node errors | stdout, exit 1 | loud, alerts | stderr plus alert |
| `tools/run_scout_workflow.py:188` | the explorer node returns errors | errors never checked; continues | loud, logged, stops, alerts | check result errors, ERROR, alert, exit 1 |
| `tools/run_scout_workflow.py:196` | empty search (including an API failure) | warning, exit 0 | loud, logged, stops, alerts | distinguish failure from an empty result; fail on failure |
| `tools/run_scout_workflow.py:200` | extractor errors | never checked; continues | loud, logged, stops, alerts | check errors and stop |
| `tools/run_scout_workflow.py:206` | gap analysis errors | never checked; an empty gap_analysis defaults to "" in the brief | loud, logged, stops, alerts | check errors and stop |
| `tools/run_scout_workflow.py:211` | scribe errors | never checked; the brief is written anyway | loud, logged, stops, alerts | check errors and stop |
| `tools/send_test_alert.py:31` | the alert channel fails | reason on stderr, exit 1 | compliant | none |
| `tools/speedrun_new_attempt.py:59` | git rev-parse fails | "" is treated the same as a detached HEAD, so the graveyard step is silently dropped | loud, logged, stops, alerts | raise on git failure, separate from detached |
| `tools/speedrun_new_attempt.py:85` | git ls-remote fails | False makes the "origin already has branch" precondition pass | loud, logged, alerts | raise when ls-remote fails |
| `tools/speedrun_new_attempt.py:93` | rev-parse errors (not "absent") | False makes the precondition pass | loud, logged, stops, alerts | separate rc 1 from other failures |
| `tools/speedrun_new_attempt.py:148` | git worktree list fails | rc ignored; no extra worktrees reported, so the precondition passes | loud, logged, stops, alerts | check rc and add a problem/raise |
| `tools/speedrun_new_attempt.py:301` | preconditions fail | stdout, exit 1 | loud, alerts | stderr ERROR plus alert |
| `tools/speedrun_new_attempt.py:341` | a git step fails mid-change | stdout, exit 2 | loud, alerts | stderr ERROR plus alert |
| `tools/speedrun_new_attempt.py:360` | postconditions fail | stdout, exit 2 | loud, alerts | stderr ERROR plus alert |
| `tools/stash_audit.py:99` | the stash has no third parent | returns [] | compliant | none |
| `tools/stash_audit.py:116` | git show fails | None; on the stash side classify raises AuditError; on the ref side it becomes ABSENT, so "DO NOT DROP" and exit 1 | compliant | none |
| `tools/stash_audit.py:236` | the audit cannot run | ERROR on stderr, exit 2 | alerts | call alert_operator |
| `tools/test-gate.py:57` | bad argument | ERROR on stderr, exit 2 | alerts | alert_operator |
| `tools/test-gate.py:116` | the skip parser matched nothing (format change or crashed pytest) | read as "no skips"; returns pytest's code and the gate passes | loud, logged, alerts | confirm pytest produced a summary before concluding there are no skips |
| `tools/test-gate.py:123` | the skip gate is bypassed | WARNING; returns pytest's exit code, so the gate is skipped | loud, stops, alerts | log at ERROR and alert on every bypass |
| `tools/test-gate.py:141` | no audit block | stderr, exit 1 | alerts | alert_operator |
| `tools/test-gate.py:178` | unaudited skips | stderr, exit 1 | alerts | alert_operator |
| `tools/test-gate.py:200` | unverified critical skips | stderr, exit 1 | alerts | alert_operator |
| `tools/test_gate/parser.py:62` | pytest times out | returns (1, "", message); the caller prints it to stderr and exits 1 | loud, alerts | raise with an ERROR log, or have the caller alert |
| `tools/test_gate/parser.py:72` | pytest cannot be found | returns (1, "", message) | loud, alerts | raise with an ERROR log and alert |
| `tools/update_clio_repo_metadata.py:104` | network error (ConnectionError/Timeout is not caught) | unhandled traceback | loud, logged, alerts | catch RequestException in main, ERROR, alert |
| `tools/update_clio_repo_metadata.py:150` | GitHub rejects the request | ERROR on stderr, exit 1 | alerts | alert_operator |
| `tools/update_clio_repo_metadata.py:155` | the PAT file is missing | ERROR on stderr, exit 1 | alerts | alert_operator |
| `tools/update_clio_repo_metadata.py:160` | gpg attempts are exhausted | ERROR on stderr, exit 1 | alerts | alert_operator |
| `tools/upgrade_auto_reviewer_caller.py:153` | the secrets list fails | shown as a "missing" entry; --apply proceeds; exit 0 | loud, stops, alerts | raise; ERROR plus alert |
| `tools/upgrade_auto_reviewer_caller.py:168` | the contents PUT fails | stdout, then raise_for_status traceback after the finally restore | loud, alerts | stderr ERROR plus alert |
| `tools/upgrade_auto_reviewer_caller.py:176` | the file is absent | stdout, exit 1 | loud, alerts | stderr ERROR plus alert |
| `tools/upgrade_auto_reviewer_caller.py:209` | restoring a ruleset's bypass_actors fails | WARNING on stdout; returns 0 with branch protection left weakened | loud, logged, stops, alerts | keep restoring, then ERROR, alert, exit non-zero |
| `tools/upgrade_auto_reviewer_caller.py:214` | re-enabling enforce_admins fails | WARNING on stdout; returns 0 with protection weakened | loud, logged, stops, alerts | ERROR, alert, exit non-zero |
| `tools/verdict_analyzer/scanner.py:60` | a registered repository is missing | WARNING; skipped | loud, stops, alerts | raise, or ERROR plus alert |
| `tools/verdict_analyzer/scanner.py:82` | the path is outside the base | False | compliant | none |
| `tools/verdict_analyzer/scanner.py:113` | scanning a verdict dir fails | WARNING; continues | loud, stops, alerts | raise with dir and cause |
| `tools/verdict_analyzer/scanner.py:132` | the directory cannot be resolved | silent return | loud, logged, stops, alerts | raise |
| `tools/verdict_analyzer/scanner.py:149` | iterdir fails | WARNING; continues | loud, stops, alerts | raise |
| `tools/verdict_analyzer/scanner.py:191` | parsing or upserting a verdict fails | ERROR log; continues; returns a partial count | stops, alerts | re-raise after logging, or collect and raise at the end with an alert |
| `tools/verdict_analyzer/template_updater.py:141` | path traversal detected | re-raised as ValueError | compliant | none |
| `tools/wait_for_pr.py:71` | gh api fails | {} reads as WAIT; a persistent failure ends as a timeout (exit 4) with the cause discarded | loud, logged, alerts | log ERROR with rc/stderr on each failure; fail fast after repeated failures |
| `tools/wait_for_pr.py:74` | the payload cannot be parsed | {} reads as WAIT | loud, logged, alerts | log ERROR with the raw output |
| `tools/wait_for_pr.py:120` | timeout with no verdict | stdout, exit 4 | loud, alerts | stderr ERROR plus alert |
| `tools/_npm_manifest.py:68` | reading or parsing package.json | returns None, so an unreadable manifest is reported as "no test script" and the cause is dropped | loud, logged, alerts | Raise (or alert_operator and raise) naming the manifest and the exception. |
| `tools/_npm_manifest.py:70` | package.json is not a JSON object | returns None, which looks the same as a missing test script | loud, logged, alerts | Raise ValueError naming the file. |
| `tools/append_session_log.py:172` | argument validation | writes to stderr and exits 1, with no alert | alerts | Call alert_operator before exit(1). |
| `tools/append_session_log.py:194` | OSError writing the log file (lines 122, 134) | unhandled; traceback and non-zero exit, with no alert | alerts | Wrap main in a handler that calls alert_operator and re-raises. |
| `tools/assemblyzero-generate.py:27` | project.json missing | prints to stdout and exits 1 | loud, alerts | Print to stderr and call alert_operator. |
| `tools/assemblyzero-generate.py:132` | template substitution incomplete | records a warning, writes the config with literal {{VAR}} anyway, exits 0 | loud, stops, alerts | Raise before writing when placeholders remain. |
| `tools/assemblyzero-generate.py:190` | project dir missing | prints to stdout and exits 1 | loud, alerts | Print to stderr and call alert_operator. |
| `tools/assemblyzero-generate.py:215` | templates dir missing | prints to stdout and exits 1 | loud, alerts | Print to stderr and call alert_operator. |
| `tools/assemblyzero-generate.py:245` | no *.template files found | prints Done with 0 files and exits 0 | loud, stops, alerts | Exit non-zero when nothing was generated. |
| `tools/assemblyzero-generate.py:249` | unhandled exceptions (json.loads at 30, file writes) | traceback, non-zero, no alert | alerts | Add an entry-point handler that calls alert_operator. |
| `tools/audit_default_arg_patches.py:156` | reading a test file | returns an empty patch list, so the file goes unaudited and the audit can report clean | loud, logged, stops, alerts | Raise naming the file. |
| `tools/audit_default_arg_patches.py:195` | configured source directory missing | skipped silently; the audit passes having examined nothing | loud, logged, stops, alerts | Raise when a configured directory is absent. |
| `tools/audit_default_arg_patches.py:200` | parsing a source module | continue; the module is silently excluded | loud, logged, stops, alerts | Raise naming the module and the error. |
| `tools/audit_default_arg_patches.py:245` | configured test directory missing | skipped silently; zero findings and exit 0 | loud, logged, stops, alerts | Raise when a configured directory is absent. |
| `tools/audit_default_arg_patches.py:321` | unhandled exceptions | traceback, non-zero, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/audit_fail_open.py:89` | baseline file missing | treated as an empty baseline; --check then fails on every site without saying the baseline is gone | loud, logged, alerts | Raise naming the missing baseline. |
| `tools/audit_fail_open.py:93` | baseline JSON unparseable | returns an empty set silently | loud, logged, alerts | Raise with the parse error. |
| `tools/audit_fail_open.py:151` | the scanner could not parse some files | listed only in the report; --check can print PASS and exit 0 without having examined them | loud, stops, alerts | Fail --check (ERROR on stderr, exit 1) whenever any file is unparseable. |
| `tools/audit_fail_open.py:262` | reading measured_against | stated=None, reported as drift in every count with the read error dropped | loud, logged, alerts | Raise with the read error. |
| `tools/audit_fail_open.py:317` | strict denominator check fails | stdout, return 1, no alert | loud, alerts | Write to stderr and call alert_operator. |
| `tools/audit_fail_open.py:324` | the gate finds new sites | stdout, return 1, no alert | loud, alerts | Write to stderr and call alert_operator. |
| `tools/audit_fail_open.py:350` | unhandled exceptions (e.g. write_baseline OSError) | traceback, non-zero, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/audit_fleet_auto_merge_readiness.py:110` | HTTP request to the GitHub API | converted to (0, {"_error": ...}); the caller files it as an error string and the repo becomes UNKNOWN | loud, logged, stops, alerts | Log ERROR with repo and cause, and make UNKNOWN fail the run. |
| `tools/audit_fleet_auto_merge_readiness.py:114` | response JSON undecodable | body=None; check_workflow still reports the file present on a 200 | loud, logged, alerts | Raise on an undecodable body. |
| `tools/audit_fleet_auto_merge_readiness.py:128` | gh repo list fails | stderr, exit 1, no alert | alerts | Call alert_operator before exiting. |
| `tools/audit_fleet_auto_merge_readiness.py:186` | repo has no default branch | verdict UNKNOWN; the run can still exit 0 | loud, stops, alerts | Count UNKNOWN as a failure and exit non-zero. |
| `tools/audit_fleet_auto_merge_readiness.py:193` | protection, workflow or secrets check cannot run | sets the error field; printed on stdout as " ERROR:", verdict UNKNOWN | loud, stops, alerts | Log ERROR on stderr and fail the run. |
| `tools/audit_fleet_auto_merge_readiness.py:224` | dependabot secrets query fails | error string discarded, TSV cell left blank | loud, logged, alerts | Record and report the error loudly. |
| `tools/audit_fleet_auto_merge_readiness.py:285` | repos whose verdict is UNKNOWN | prints "all ready" and returns 0 when nothing is NOT_READY, even if every repo errored | loud, stops, alerts | Return non-zero when any verdict is UNKNOWN. |
| `tools/audit_fleet_auto_merge_readiness.py:290` | unhandled exceptions (json.loads at 129, TSV write) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/audit_gitignore_drift.py:94` | any git subprocess | stderr discarded, so callers see only a code | loud, logged, alerts | Return stderr and log it at ERROR on non-zero. |
| `tools/audit_gitignore_drift.py:116` | git status fails | treated as dirty, and the git failure is never mentioned | loud, logged, alerts | Raise when git status fails. |
| `tools/audit_gitignore_drift.py:127` | git check-ignore errors (code 128) | treated as "data-g not ignored", so the finding silently passes | loud, logged, stops, alerts | Distinguish 0/1 from other codes and raise on the rest. |
| `tools/audit_gitignore_drift.py:171` | root missing | stderr, return 2, no alert | alerts | Call alert_operator. |
| `tools/audit_gitignore_drift.py:180` | reading a repo's .gitignore or running git | error goes into a row field that is never printed; the repo is reported as "NO .gitignore AT ALL" and the run exits 0 | loud, logged, stops, alerts | Print an ERROR with the cause and exit non-zero. |
| `tools/audit_gitignore_drift.py:233` | unhandled (e.g. backfill write OSError mid-apply) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/audit_tracked_log_writers.py:133` | reading a source file | returns []; the file goes unaudited silently | loud, logged, stops, alerts | Raise naming the file. |
| `tools/audit_tracked_log_writers.py:171` | git ls-files cannot run | returns an empty set, so every path looks untracked, no bug is found, exit 0 | loud, logged, stops, alerts | Raise. |
| `tools/audit_tracked_log_writers.py:173` | git ls-files exits non-zero | returns an empty set, giving the same false clean | loud, logged, stops, alerts | Raise with returncode and stderr. |
| `tools/audit_tracked_log_writers.py:224` | root not a repo | stderr, exit 1, no alert | alerts | Call alert_operator. |
| `tools/audit_tracked_log_writers.py:252` | unhandled exceptions (TSV write) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/backfill_telemetry.py:31` | usage log missing | stdout note, continues | loud, stops, alerts | Raise or ERROR+alert when a source log is missing. |
| `tools/backfill_telemetry.py:40` | malformed usage-log line | dropped silently | loud, logged, alerts | Count and report dropped lines as an error. |
| `tools/backfill_telemetry.py:61` | timestamp parse | event dropped silently | loud, logged, stops, alerts | Raise naming the line. |
| `tools/backfill_telemetry.py:74` | friction logs directory missing | stdout note, continues | loud, stops, alerts | Raise or ERROR+alert. |
| `tools/backfill_telemetry.py:85` | corrupt friction-log line | skipped silently | loud, logged, stops, alerts | Raise naming file and line. |
| `tools/backfill_telemetry.py:108` | timestamp parse | pass; the event is written with the backfill-time timestamp (wrong date) | loud, logged, stops, alerts | Raise or drop with an ERROR. |
| `tools/backfill_telemetry.py:124` | workflow logs directory missing | stdout note, continues | loud, stops, alerts | Raise or ERROR+alert. |
| `tools/backfill_telemetry.py:135` | corrupt workflow-log line | skipped silently | loud, logged, stops, alerts | Raise naming file and line. |
| `tools/backfill_telemetry.py:167` | timestamp parse | pass; the event keeps the wrong timestamp | loud, logged, stops, alerts | Raise. |
| `tools/backfill_telemetry.py:210` | Dynamo client unavailable | stdout with no cause, exit 1 | loud, logged, alerts | stderr with cause, then alert_operator. |
| `tools/backfill_telemetry.py:219` | put_item fails | counts errors, prints the first 3 to stdout, continues, exits 0 | loud, logged, stops, alerts | Raise (or exit non-zero after ERROR+alert). |
| `tools/backfill_telemetry.py:228` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/banned_command_sweep.py:88` | reading a command or skill file | WARNING on stderr, file skipped; the sweep can exit 0 | loud, stops, alerts | Raise or exit 2 with an ERROR and alert. |
| `tools/banned_command_sweep.py:161` | root missing | stderr, return 2, no alert | alerts | Call alert_operator. |
| `tools/banned_command_sweep.py:176` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/cerberus_worker_key.py:58` | wrangler secret put fails | stderr, exit 1, no alert | alerts | Call alert_operator before exiting. |
| `tools/cerberus_worker_key.py:65` | npx missing | stderr, exit 1, no alert | alerts | Call alert_operator before exiting. |
| `tools/cerberus_worker_key.py:78` | wrangler secret list fails | returncode never checked; prints whatever stdout holds and exits 0 | loud, logged, stops, alerts | Check returncode and fail loudly. |
| `tools/cerberus_worker_key.py:85` | unhandled (decrypt, PEM parse) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/claude-usage-scraper.py:37` | pywinpty import | winpty=None by documented contract; main() calls _require_winpty (line 368), which exits 1 before any use | compliant | none |
| `tools/claude-usage-scraper.py:49` | pywinpty not installed | error JSON on stdout, exit 1 | loud, alerts | Also write an ERROR to stderr and alert_operator. |
| `tools/claude-usage-scraper.py:177` | PTY read raises | reader thread stops silently, so the later parse failure loses the cause | loud, logged, alerts | Record the exception and surface it as the scrape error. |
| `tools/claude-usage-scraper.py:266` | claude process dies | returned as an error dict; main prints JSON to stdout and exits 1 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/claude-usage-scraper.py:303` | only some usage fields parsed | status "success" with null fields | loud, stops, alerts | Require all three fields, or fail. |
| `tools/claude-usage-scraper.py:311` | parse produced nothing | error dict, stdout, exit 1 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/claude-usage-scraper.py:320` | claude not on PATH | error dict, stdout, exit 1 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/claude-usage-scraper.py:325` | any scrape error | error dict with str(e) only (no type), stdout, exit 1 | loud, logged, alerts | Log type and message at ERROR on stderr and alert. |
| `tools/claude-usage-scraper.py:345` | graceful /exit of claude fails | falls back to terminate, silently | loud, logged, alerts | Log the cleanup failure at ERROR. |
| `tools/claude-usage-scraper.py:348` | terminate fails | pass; a claude process may be left running | loud, logged, alerts | Log at ERROR and alert. |
| `tools/claude-usage-scraper.py:414` | any scrape failure | exit 1 with the reason only in stdout JSON and the log; no alert | loud, alerts | Write the ERROR line to stderr and call alert_operator on failure. |
| `tools/claude_usage_compute.py:138` | timestamp unparseable | None; the usage record is dropped as if it were a non-usage event | loud, logged, stops, alerts | Raise naming the event. |
| `tools/claude_usage_compute.py:177` | projects root missing | returns []; the payload reports zero tokens, exit 0 | loud, logged, stops, alerts | Raise when the root is absent. |
| `tools/claude_usage_compute.py:204` | corrupt jsonl line | skipped silently, so token totals undercount | loud, logged, stops, alerts | Raise or count and fail. |
| `tools/claude_usage_compute.py:211` | reading a session file | pass; partial records returned, the rest lost | loud, logged, stops, alerts | Raise. |
| `tools/claude_usage_compute.py:398` | unhandled (int() on usage fields, output write) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/clean_transcript.py:235` | --fix-spaces requested without wordninja | silently a no-op; stats report 0 fixed | loud, logged, stops, alerts | Raise when the requested feature cannot run. |
| `tools/clean_transcript.py:347` | input missing | stdout, exit 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/clean_transcript.py:364` | unhandled (read/write errors) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/consolidate_logs.py:42` | malformed shard line | skipped, and the shard is deleted afterward (line 159), so the entry is destroyed | loud, logged, stops, alerts | Raise and keep the shard. |
| `tools/consolidate_logs.py:148` | closing the temp fd during failure cleanup | swallowed | loud, logged, alerts | Log at ERROR (the original exception still propagates). |
| `tools/consolidate_logs.py:153` | removing the temp file | swallowed; a stray temp file is left | loud, logged, alerts | Log at ERROR. |
| `tools/consolidate_logs.py:160` | deleting a merged shard | skipped; the next run merges the shard again and duplicates history | loud, logged, stops, alerts | Raise or alert. |
| `tools/consolidate_logs.py:174` | any consolidation failure | "Warning:" on stderr, exit 0 | loud, stops, alerts | ERROR on stderr, alert_operator, exit non-zero. |
| `tools/deploy_boostgauge_release_yml.py:306` | raise_for_status / RequestException at any API step (153-246), possibly after the branch exists without the file or PR | traceback, non-zero, no alert | alerts | Entry-point handler that calls alert_operator naming the step reached. |
| `tools/derive_stage_nominals.py:75` | reading a run log | skipped silently; the nominals come from a partial corpus | loud, logged, stops, alerts | Raise naming the log. |
| `tools/derive_stage_nominals.py:92` | empty sample list | returns 0.0, but every caller (lines 121, 133) skips empty lists before calling | compliant | none |
| `tools/derive_stage_nominals.py:110` | runs dir missing | stdout, return 2 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/derive_stage_nominals.py:115` | no data | stdout, return 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/derive_stage_nominals.py:149` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/enable_dependabot.py:60` | first import of _pat_session | retries with a path fix; the second import raises if it fails | compliant | none |
| `tools/enable_dependabot.py:112` | GET repo fails | ok=False result printed on stdout; next repo; exit 2 at end | loud, alerts | ERROR on stderr per repo plus alert_operator. |
| `tools/enable_dependabot.py:120` | GET raises | converted into an action string, stdout, exit 2 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/enable_dependabot.py:146` | PATCH fails | recorded, then still runs the two PUTs for that repo | loud, stops, alerts | Stop the repo's remaining steps and fail loudly. |
| `tools/enable_dependabot.py:151` | PATCH raises | recorded, continues to the PUTs | loud, stops, alerts | Stop the repo's remaining steps and fail loudly. |
| `tools/enable_dependabot.py:169` | PUT vulnerability-alerts fails | recorded, continues to automated-security-fixes | loud, stops, alerts | Stop and fail loudly. |
| `tools/enable_dependabot.py:172` | PUT raises | recorded, continues | loud, stops, alerts | Stop and fail loudly. |
| `tools/enable_dependabot.py:186` | PUT automated-security-fixes fails | recorded on stdout, exit 2 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/enable_dependabot.py:189` | PUT raises | recorded on stdout, exit 2 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/enable_dependabot.py:219` | gh repo list fails | stderr, exit 1, no alert | alerts | Call alert_operator. |
| `tools/enable_dependabot.py:278` | bad argument | stderr, return 1, no alert | alerts | Call alert_operator. |
| `tools/enable_dependabot.py:300` | per-repo failures | WARNING on stdout, return 2 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/enable_dependabot.py:310` | unhandled exceptions (json.loads, PAT session) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/fix_az_workflow_concurrency.py:53` | workflow file absent on a target branch | skipped silently; the run still prints "All branches updated" | loud, logged, alerts | Report each skipped file loudly. |
| `tools/fix_az_workflow_concurrency.py:97` | main branch fix fails | stdout, return 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/fix_az_workflow_concurrency.py:104` | a branch fix fails after main was already changed | stdout, return 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/fix_az_workflow_concurrency.py:111` | unhandled (requests exceptions, KeyError, decode) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/fix_branch_protections.py:100` | gh api lookup of the default branch fails | defaults to "main", so protection may be PUT on the wrong or a nonexistent branch | loud, logged, stops, alerts | Raise with gh's stderr. |
| `tools/fix_branch_protections.py:120` | verify read fails | FixResult failure on stdout; exit 1 at end | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fix_branch_protections.py:147` | verify response not JSON | FixResult failure on stdout | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fix_branch_protections.py:331` | protection PUT fails | stdout FAIL, continues, exit 1 at end | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fix_branch_protections.py:355` | wiki PATCH fails | stdout FAIL, exit 1 at end | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fix_branch_protections.py:378` | requests exception mid-batch (183, 209); no report written | traceback, no alert | alerts | Entry-point handler that alerts and writes the partial report. |
| `tools/fleet_remove_claude_key.py:147` | 404 on an ok_404 call | returns None by documented contract (docstring steps 1-2); callers at 204 and 213 treat it as a skip | compliant | none |
| `tools/fleet_remove_claude_key.py:196` | mergeable poll runs out | returns a value; the caller reports STUCK on stdout, exit 1 | loud, alerts | Raise or ERROR on stderr plus alert_operator. |
| `tools/fleet_remove_claude_key.py:205` | a repo the operator named does not exist | reported as a skip; exit 0 | loud, stops, alerts | Treat it as an error. |
| `tools/fleet_remove_claude_key.py:206` | default_branch absent from the response | silently defaults to main | loud, logged, alerts | Raise when the field is missing. |
| `tools/fleet_remove_claude_key.py:285` | merge did not land | stdout, exit 1 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fleet_remove_claude_key.py:303` | no repos | stderr, return 2, no alert | alerts | Call alert_operator. |
| `tools/fleet_remove_claude_key.py:314` | gh failure mid-cycle (issue or branch may already exist) | converted to an ERROR string on stdout; next repo; exit 1 | loud, alerts | ERROR on stderr with the step reached, plus alert_operator. |
| `tools/fleet_remove_claude_key.py:328` | unhandled (subprocess.TimeoutExpired) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/fleet_set_delete_branch_on_merge.py:189` | GET setting fails | ("error", ...) on stdout; exit 3 at end | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fleet_set_delete_branch_on_merge.py:192` | a named repo returns 404 | not counted as an error; exit 0 | loud, stops, alerts | Count not_found as a failure. |
| `tools/fleet_set_delete_branch_on_merge.py:199` | PATCH fails | status tuple on stdout; exit 3 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fleet_set_delete_branch_on_merge.py:222` | auth preflight fails | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/fleet_set_delete_branch_on_merge.py:236` | repo discovery fails | stdout, return 2 | loud, alerts | stderr plus alert_operator. |
| `tools/fleet_set_delete_branch_on_merge.py:247` | unexpected per-repo error | converted to an error tuple, continues, exit 3 | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/fleet_set_delete_branch_on_merge.py:268` | unhandled (PAT session, retry exhaustion at 115-116) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/land_aletheia_ci_pipestatus.py:177` | GET branch ref fails (401/5xx) | treated as branch absent; tries to create it | loud, logged, alerts | Return False only on 404 and raise otherwise. |
| `tools/land_aletheia_ci_pipestatus.py:254` | mergeable poll times out | returns the last state; the caller prints stdout and returns 1 | loud, alerts | Raise a timeout error naming the PR. |
| `tools/land_aletheia_ci_pipestatus.py:278` | local file missing | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/land_aletheia_ci_pipestatus.py:342` | PR dirty | stdout, return 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/land_aletheia_ci_pipestatus.py:345` | PR not mergeable | stdout, return 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/land_aletheia_ci_pipestatus.py:359` | unhandled raise_for_status | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/land_windows_ci_job.py:197` | any 422 (including validation errors) | assumed to mean the branch already exists | loud, logged, alerts | Check the 422 message, or confirm the ref exists. |
| `tools/land_windows_ci_job.py:258` | PR creation fails | stdout, then prints "The PR is open" and returns 0 | loud, stops, alerts | Exit non-zero with ERROR plus alert unless an existing PR is confirmed. |
| `tools/land_windows_ci_job.py:264` | existing-PR lookup fails | silently prints nothing | loud, logged, alerts | Raise on a failed lookup. |
| `tools/land_windows_ci_job.py:276` | unhandled raise_for_status | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/lint_per_repo_claude_md.py:79` | first config import | retries with a path fix; the second import raises if it fails | compliant | none |
| `tools/lint_per_repo_claude_md.py:200` | .unleashed.json unreadable | None ("no signal"), so marker 6 is skipped silently | loud, logged, stops, alerts | Raise or report an ERROR finding. |
| `tools/lint_per_repo_claude_md.py:272` | git show origin/main:CLAUDE.md fails for any reason | None, reported as MISSING with git's stderr dropped | loud, logged, alerts | Separate "absent" from "git failed" and raise on the latter. |
| `tools/lint_per_repo_claude_md.py:643` | root missing | stderr, return 1, no alert | alerts | Call alert_operator. |
| `tools/lint_per_repo_claude_md.py:649` | allowlist missing | stderr, return 1, no alert | alerts | Call alert_operator. |
| `tools/lint_per_repo_claude_md.py:670` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/prompt_revision_rank.py:56` | telemetry absent or unreadable (e.g. wrong --repo), if load_telemetry returns [] | reported as "no failures recorded", exit 0 | loud, logged, stops, alerts | Fail when the telemetry file does not exist, and keep exit 0 only for an existing empty file. |
| `tools/prompt_revision_rank.py:65` | runs.csv missing | note on stdout; ranks by count and flags duration-unknown, the documented contract (docstring lines 12-14) | compliant | none |
| `tools/prompt_revision_rank.py:80` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/push_workflow_fixes.py:65` | checked command fails | stdout, exit 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/push_workflow_fixes.py:124` | Fix 2 target string absent | WARNING on stdout, continues | loud, stops, alerts | Fail unless the new value is confirmed present. |
| `tools/push_workflow_fixes.py:157` | any 422 on branch create | treated as success | loud, logged, alerts | Confirm the branch exists on a 422. |
| `tools/push_workflow_fixes.py:194` | GET of the existing file fails (non-404) | ignored; PUT is sent without a sha | loud, logged, alerts | Raise on statuses other than 200/404. |
| `tools/push_workflow_fixes.py:254` | gh api reviews call fails | counted as "not approved"; polling continues | loud, logged, alerts | Raise on gh failure. |
| `tools/push_workflow_fixes.py:288` | main SHA lookup fails | skips Fix 3, run exits 0 | loud, logged, stops, alerts | Raise with the cause. |
| `tools/push_workflow_fixes.py:292` | branch create fails | skips, exit 0 | loud, stops, alerts | Raise. |
| `tools/push_workflow_fixes.py:296` | file PUT fails | skips, exit 0 | loud, stops, alerts | Raise. |
| `tools/push_workflow_fixes.py:301` | PR create fails | skips, exit 0 | loud, stops, alerts | Raise. |
| `tools/push_workflow_fixes.py:304` | merge fails or approval times out | return value ignored; DONE, exit 0 | loud, stops, alerts | Check the result and fail loudly. |
| `tools/push_workflow_fixes.py:320` | gh repo list fails | returns []; Fix 4 runs on zero repos, exit 0 | loud, logged, stops, alerts | Raise. |
| `tools/push_workflow_fixes.py:353` | PATCH fails for a repo | stdout, counted, exit 0 | loud, stops, alerts | Exit non-zero with ERROR plus alert when failed > 0. |
| `tools/push_workflow_fixes.py:395` | git push fails | stderr dropped; falls back to pushing the current branch | loud, logged, alerts | Log the first failure at ERROR before any fallback. |
| `tools/push_workflow_fixes.py:417` | rev-parse failure lands here too (toplevel empty) | stdout, return 1, git cause dropped | loud, logged, alerts | Check returncode separately; stderr plus alert. |
| `tools/push_workflow_fixes.py:475` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/remediate_patent_general_protection.py:95` | ruleset probe fails (non-200/404) | exists=False: the dry run says "already removed" and the post-fix check at 214-216 passes as gone | loud, stops, alerts | Raise on unexpected statuses. |
| `tools/remediate_patent_general_protection.py:105` | DELETE returns 404 | treated as already gone, per the documented idempotency (docstring lines 20-21) | compliant | none |
| `tools/remediate_patent_general_protection.py:187` | ruleset DELETE fails | stdout, return 2 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/remediate_patent_general_protection.py:196` | classic PUT fails after the ruleset was deleted (branch unprotected) | stdout, return 2 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/remediate_patent_general_protection.py:209` | verification fails | stdout, return 2 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/remediate_patent_general_protection.py:217` | ruleset survived | stdout, return 2 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/remediate_patent_general_protection.py:230` | unhandled requests exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/run_implement_from_lld.py:77` | git rev-parse fails | returns "" with stderr dropped; the caller refuses at 1095 on stdout | loud, logged, alerts | Raise with git's stderr. |
| `tools/run_implement_from_lld.py:123` | git worktree list fails | returns None, meaning "no existing worktree", the conflation _worktree_entries was built to prevent | loud, logged, alerts | Raise when entries is None. |
| `tools/run_implement_from_lld.py:296` | git status fails | returncode unchecked; empty listing, nothing kept, and the later worktree remove deletes ignored files such as lineage | loud, logged, stops, alerts | Check returncode and stop. |
| `tools/run_implement_from_lld.py:345` | git status fails | reads as clean; proceeds to push and remove | loud, logged, stops, alerts | Check returncode and stop. |
| `tools/run_implement_from_lld.py:353` | git fails | "" skips the push, the worktree is removed, and finished=True is returned | loud, logged, stops, alerts | Check returncode and stop. |
| `tools/run_implement_from_lld.py:961` | status file write fails | pass (best-effort) | loud, logged, stops, alerts | Log ERROR and alert; the status file is the run's record. |
| `tools/run_implement_from_lld.py:990` | repo missing | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:996` | repo root undetectable | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1003` | select returns None also for a missing LLD dir or no LLDs (496-503) | exit 0 | loud, stops, alerts | Exit non-zero when selection failed rather than being cancelled. |
| `tools/run_implement_from_lld.py:1008` | bad issue | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1087` | wrong branch | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1096` | branch unreadable | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1123` | worktree creation fails | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1181` | some context files fail validation | printed; the run continues with partial context | loud, stops, alerts | Fail on any context error. |
| `tools/run_implement_from_lld.py:1183` | all context invalid | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1199` | profile invalid | stdout, exit 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1331` | --resume asked for a checkpoint that does not exist | starts a fresh run | loud, stops, alerts | Refuse with an ERROR when --resume finds no checkpoint. |
| `tools/run_implement_from_lld.py:1344` | node returns error_message | stdout only; the stream continues | loud, alerts | Print to stderr; ensure HALT routing alerts. |
| `tools/run_implement_from_lld.py:1377` | workflow ends in error | stdout, return 1, no alert_operator in this tool | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1442` | end-state step fails (push, worktree remove, branch delete) | prints a note and returns 0 | loud, stops, alerts | Return non-zero with ERROR plus alert. |
| `tools/run_implement_from_lld.py:1458` | unexpected exception | [FATAL] on stdout plus traceback, return 1, no alert | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/run_implement_from_lld.py:1484` | graph produced no final state | records halt, then exits 0 | loud, stops, alerts | Return non-zero with ERROR plus alert. |
| `tools/run_implement_from_lld.py:1489` | unhandled exceptions outside main's try (e.g. re-raise at 1254) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/run_requirements_workflow.py:118` | checkpoint DB unreadable | returns False ("no checkpoint"); resume starts fresh | loud, logged, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:175` | brief unreadable | pass; title "(no title)" | loud, logged, alerts | Raise naming the brief. |
| `tools/run_requirements_workflow.py:192` | ideas dir missing | returns None; main reports "Selection cancelled" and exits 0 | loud, stops, alerts | Raise instead of returning None. |
| `tools/run_requirements_workflow.py:199` | no briefs | None, exit 0 via main | loud, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:259` | gh issue list fails | None, exit 0 as "cancelled" | loud, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:264` | gh times out | None, exit 0 | loud, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:267` | gh missing | None, exit 0 | loud, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:270` | gh output unparseable | None, exit 0 | loud, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:560` | git rev-parse for the brief's repo fails | pass; falls back to the CWD repo | loud, logged, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:582` | git rev-parse fails | pass; falls back to Path.cwd(), a possible non-repo target | loud, logged, stops, alerts | Raise. |
| `tools/run_requirements_workflow.py:585` | rev-parse returns non-zero | silently uses CWD as the target repo | loud, logged, stops, alerts | Raise with git's stderr. |
| `tools/run_requirements_workflow.py:633` | target is the AZ root | stderr, exit 1, no alert | alerts | Call alert_operator. |
| `tools/run_requirements_workflow.py:931` | workflow exception | stdout, traceback only with --debug, return 1, no alert | loud, logged, alerts | ERROR with type and traceback on stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:967` | no draft | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:991` | lineage 001-issue.md missing | review runs without the issue body or title | loud, stops, alerts | Raise when the issue file is absent. |
| `tools/run_requirements_workflow.py:1175` | resume-review exception | stdout, return 1, no alert | loud, logged, alerts | ERROR with traceback on stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1203` | no briefs, including a missing ideas dir (147-148) | exit 0 | loud, stops, alerts | Exit non-zero when the directory is missing. |
| `tools/run_requirements_workflow.py:1241` | a brief's workflow fails | stdout, continues; exit 1 at end | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1291` | --resume target absent | starts a fresh workflow | loud, stops, alerts | Refuse with an ERROR. |
| `tools/run_requirements_workflow.py:1306` | brief missing | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1330` | brief missing | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1446` | resumable draft present, no --yes | main returns 0 as "User aborted" with nothing generated | loud, stops, alerts | Exit non-zero with an ERROR explaining the choice needed. |
| `tools/run_requirements_workflow.py:1541` | workflow error | stdout only | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1551` | no issue URL and no error_message | exit 0 with nothing filed | loud, stops, alerts | Fail unless manual mode was chosen. |
| `tools/run_requirements_workflow.py:1558` | no LLD path and no error_message | exit 0 with nothing saved | loud, stops, alerts | Fail unless manual mode was chosen. |
| `tools/run_requirements_workflow.py:1612` | bad arguments | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1616` | bad arguments | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1621` | bad arguments | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1625` | bad arguments | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1630` | bad arguments | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1634` | bad arguments | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/run_requirements_workflow.py:1662` | select_brief_file returned None because of an error (192/199) | "Selection cancelled", exit 0 | loud, stops, alerts | Distinguish cancel from failure and exit non-zero on failure. |
| `tools/run_requirements_workflow.py:1668` | select_github_issue returned None because of an error (259-272) | "Selection cancelled", exit 0 | loud, stops, alerts | Distinguish cancel from failure and exit non-zero on failure. |
| `tools/run_requirements_workflow.py:1687` | merge driver not configured | stdout, return 1 | loud, alerts | stderr ERROR plus alert_operator. |
| `tools/run_requirements_workflow.py:1690` | also reached when the resumable-draft guard returns False (1446) | exit 0 | loud, stops, alerts | Exit non-zero when nothing was generated. |
| `tools/run_requirements_workflow.py:1698` | unhandled exceptions (build_initial_state, validate_integration_branch) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/speedrun_clean_check.py:54` | git remote get-url fails | "" with git's stderr dropped; the caller at 121 makes an ERROR finding (exit 2) | logged, alerts | Carry git's stderr into the finding. |
| `tools/speedrun_clean_check.py:65` | git worktree list fails | ERROR finding by contract; main (371-379) separates ERROR entries and exits 2 | compliant | none |
| `tools/speedrun_clean_check.py:91` | git branch fails | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:103` | ls-remote fails | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:107` | malformed ls-remote line | skipped silently | loud, logged, alerts | Report it as an ERROR finding. |
| `tools/speedrun_clean_check.py:121` | owner/repo undeterminable | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:130` | gh fails | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:134` | gh JSON bad | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:169` | git status fails | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:197` | fetch fails | returncode ignored; a stale origin ref is measured and may read CLEAN | loud, logged, stops, alerts | Check returncode and return an ERROR finding. |
| `tools/speedrun_clean_check.py:200` | fetch fails | returncode ignored; stale origin/<base> or a fallback to local | loud, logged, stops, alerts | Check returncode and return an ERROR finding. |
| `tools/speedrun_clean_check.py:206` | rev-parse fails for any reason | silently falls back to the local branch (the #2021 defect shape) | loud, logged, stops, alerts | Fall back only when origin truly lacks the ref, and raise on git errors. |
| `tools/speedrun_clean_check.py:248` | ls-tree fails | ERROR finding, exit 2 via main | compliant | none |
| `tools/speedrun_clean_check.py:266` | rev-parse fails | "" by contract; the caller at 349 refuses with exit 2 | compliant | none |
| `tools/speedrun_clean_check.py:283` | rev-list cannot measure divergence | None ("unknown"); the caller at 357 treats it as no divergence and proceeds | loud, logged, stops, alerts | Treat unknown as a refusal unless --base-branch was declared. |
| `tools/speedrun_clean_check.py:339` | not a repo | stdout, return 2 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_clean_check.py:351` | no base ref | stdout, return 2 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_clean_check.py:359` | undeclared divergent base | stdout, return 2 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_clean_check.py:378` | a check could not run | ERROR findings on stdout, return 2, no alert | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_clean_check.py:409` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/speedrun_overlay.py:52` | filename suffix not numeric | skipped: such a file is not an attempt file, so this is not a failure | compliant | none |
| `tools/speedrun_overlay.py:66` | splits file missing | returned as overlay text, exit 0 | loud, stops, alerts | Raise or exit non-zero in non-watch mode. |
| `tools/speedrun_overlay.py:69` | splits unreadable | returned as overlay text, exit 0 | loud, stops, alerts | Raise or exit non-zero in non-watch mode. |
| `tools/speedrun_overlay.py:122` | no attempts | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_overlay.py:136` | operator stops watch mode | return 0: an intentional stop, not a failure | compliant | none |
| `tools/speedrun_overlay.py:141` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/speedrun_reset.py:70` | chmod during an rmtree retry | swallowed, but func(failing) at line 72 re-raises if deletion still fails | compliant | none |
| `tools/speedrun_reset.py:113` | cannot list PRs | WARNING on stdout, returns 0, reset continues | loud, stops, alerts | Raise. |
| `tools/speedrun_reset.py:117` | gh output unparseable | returns 0 silently | loud, logged, stops, alerts | Raise. |
| `tools/speedrun_reset.py:127` | PR close fails | WARNING on stdout, continues | loud, stops, alerts | Raise or record as a failure. |
| `tools/speedrun_reset.py:140` | git status fails in the worktree | treated as dirty; the caller says "holds uncommitted work" and the git error is lost | loud, logged, alerts | Log the git failure at ERROR. |
| `tools/speedrun_reset.py:208` | moving an unregistered worktree aside fails | WARNING on stdout, returns False | loud, stops, alerts | Raise. |
| `tools/speedrun_reset.py:226` | registration removal fails | returncode ignored | loud, logged, alerts | Check returncode and log at ERROR. |
| `tools/speedrun_reset.py:233` | rev-parse fails | "" disables the checked-out-branch exclusion in the delete loops | loud, logged, stops, alerts | Raise. |
| `tools/speedrun_reset.py:262` | git branch --list fails | returns 0 silently | loud, logged, stops, alerts | Raise with stderr. |
| `tools/speedrun_reset.py:343` | git branch --list fails | returned as a failure description; no caller in this file, so handling depends on external callers and git's stderr is dropped | loud, logged, alerts | Raise with git's stderr. |
| `tools/speedrun_reset.py:408` | origin/HEAD unresolvable | silently measures against HEAD | loud, logged, alerts | Raise or require the base. |
| `tools/speedrun_reset.py:426` | rev-list fails | None by documented contract (docstring 418-419); the caller preserves the branch at 375-386 | compliant | none |
| `tools/speedrun_reset.py:450` | local branch list fails | silently a shorter candidate list | loud, logged, alerts | Raise on non-zero. |
| `tools/speedrun_reset.py:462` | ls-remote fails | skips the remote sweep | loud, stops, alerts | Raise. |
| `tools/speedrun_reset.py:485` | remote delete fails | WARNING on stdout, continues | loud, alerts | ERROR on stderr plus record as a failure. |
| `tools/speedrun_reset.py:525` | shutil.move fails | falls back to copytree plus rmtree, which raise into the handler at 537 | compliant | none |
| `tools/speedrun_reset.py:532` | copy did not produce the target | the gate is an assert, removed under python -O, so the source would be deleted anyway | stops | Replace it with an explicit check that raises. |
| `tools/speedrun_reset.py:537` | archiving a lineage dir fails | WARNING on stdout, continues | loud, stops, alerts | Raise. |
| `tools/speedrun_reset.py:563` | git log fails | treated as "no checkpoint"; branches are then deleted with nothing pinned | loud, logged, stops, alerts | Raise on git failure. |
| `tools/speedrun_reset.py:571` | update-ref fails | WARNING; the reset goes on to delete the branches that reach the checkpoint | loud, stops, alerts | Raise before any branch deletion. |
| `tools/speedrun_reset.py:585` | git ls-files errors | treated as untracked, so a tracked file may be relocated | loud, logged, stops, alerts | Distinguish "untracked" (1) from an error and raise on the latter. |
| `tools/speedrun_reset.py:650` | relocation fails | WARNING, continues | loud, stops, alerts | Raise. |
| `tools/speedrun_reset.py:656` | removing an emptied drafts dir fails | pass | loud, logged, alerts | Log at ERROR. |
| `tools/speedrun_reset.py:668` | gh issue view fails | returns False silently; the issue may stay closed | loud, logged, stops, alerts | Raise with stderr. |
| `tools/speedrun_reset.py:672` | gh output bad | returns False silently | loud, logged, stops, alerts | Raise. |
| `tools/speedrun_reset.py:683` | reopen fails | WARNING; the final clean check does not cover issue state | loud, stops, alerts | Raise or exit non-zero. |
| `tools/speedrun_reset.py:761` | run-log.jsonl missing | "nothing to reset", exit 0 | loud, stops, alerts | Raise when --all-issues finds no log. |
| `tools/speedrun_reset.py:772` | corrupt run-log line | skipped, so that issue is silently not reset | loud, logged, stops, alerts | Raise naming the line. |
| `tools/speedrun_reset.py:795` | repo missing | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_reset.py:801` | remote unreadable | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_reset.py:823` | live orchestrator | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_reset.py:839` | branch unreadable | silently verifies against HEAD | loud, logged, alerts | Raise. |
| `tools/speedrun_reset.py:844` | verification cannot run | stdout, return 2 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_reset.py:849` | debris remains | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_reset.py:859` | unhandled exceptions (rmtree, import) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/speedrun_summarize.py:109` | repo missing | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/speedrun_summarize.py:113` | run log missing or unreadable, if read_all returns [] for it | prints "No attempts logged yet", exit 0 | loud, stops, alerts | Fail when the log file does not exist. |
| `tools/speedrun_summarize.py:131` | unhandled exceptions | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/test_governance_system.py:102` | gh times out | converted to (1, "TIMEOUT"); fire-and-forget callers (165, 299, 302) ignore it | loud, logged, alerts | Raise, or log ERROR in run_gh. |
| `tools/test_governance_system.py:104` | gh missing | converted to (1, ...) | loud, logged, alerts | Raise. |
| `tools/test_governance_system.py:117` | curl output malformed or curl failed (returncode never checked) | status 0; T07 records a FAIL | loud, logged, alerts | Check the curl returncode and raise. |
| `tools/test_governance_system.py:118` | curl timeout or missing | status 0 | loud, logged, alerts | Raise. |
| `tools/test_governance_system.py:132` | gh repo list fails | returns []; main exits 1 with "No repos found" | loud, alerts | Raise with the cause and alert. |
| `tools/test_governance_system.py:151` | issue create fails | stdout; recorded as a test FAIL, not an error | loud, alerts | stderr plus alert_operator. |
| `tools/test_governance_system.py:159` | parse fails | stdout, None | loud, alerts | stderr plus alert_operator. |
| `tools/test_governance_system.py:165` | close fails | return ignored; test issues left open | loud, logged, alerts | Check rc and report. |
| `tools/test_governance_system.py:176` | SHA lookup fails | stdout, False | loud, alerts | stderr plus alert_operator. |
| `tools/test_governance_system.py:191` | branch create fails | stdout, False | loud, alerts | stderr plus alert_operator. |
| `tools/test_governance_system.py:210` | file PUT fails; the branch is left behind | stdout, False | loud, alerts | stderr plus alert_operator and delete the branch. |
| `tools/test_governance_system.py:231` | PR create fails | stdout, None | loud, alerts | stderr plus alert_operator. |
| `tools/test_governance_system.py:236` | parse fails | stdout, None | loud, alerts | stderr plus alert_operator. |
| `tools/test_governance_system.py:248` | PR SHA lookup fails | error dict; T02-T06 have no "error" branch, so they record FAIL with an empty actual | loud, logged, alerts | Raise, or handle "error" in every test. |
| `tools/test_governance_system.py:263` | check-run line unparseable | skipped silently | loud, logged, alerts | Raise. |
| `tools/test_governance_system.py:285` | gh api fails | "unknown"; polling continues | loud, logged, alerts | Raise on gh failure. |
| `tools/test_governance_system.py:294` | poll times out | the test records FAIL; exit 2 at end, no alert | loud, alerts | ERROR on stderr plus alert. |
| `tools/test_governance_system.py:299` | PR close fails | return ignored | loud, logged, alerts | Check rc and report. |
| `tools/test_governance_system.py:302` | branch delete fails | return ignored | loud, logged, alerts | Check rc and report. |
| `tools/test_governance_system.py:328` | T01 PR creation failed | issue closed but the test branch is never deleted | loud, logged, alerts | Delete the branch and report the leak. |
| `tools/test_governance_system.py:376` | T02 PR creation failed | returns FAIL; the created branch is left behind | loud, logged, alerts | Clean up the branch and report. |
| `tools/test_governance_system.py:424` | T03 PR creation failed | returns FAIL; the branch is left behind | loud, logged, alerts | Clean up the branch and report. |
| `tools/test_governance_system.py:472` | T04 PR creation failed | the branch is left behind | loud, logged, alerts | Clean up the branch and report. |
| `tools/test_governance_system.py:514` | T05 PR creation failed | the branch is left behind | loud, logged, alerts | Clean up the branch and report. |
| `tools/test_governance_system.py:554` | T06 PR creation failed | the branch is left behind | loud, logged, alerts | Clean up the branch and report. |
| `tools/test_governance_system.py:628` | any gh failure (auth, network) | reported as the workflow being "missing" | loud, logged, alerts | Separate 404 from other failures and raise on the latter. |
| `tools/test_governance_system.py:637` | base64 or UTF-8 decode fails | recorded as "cannot decode" with the cause dropped | loud, logged, alerts | Include the exception and alert. |
| `tools/test_governance_system.py:735` | protection read fails | recorded as an audit FAIL, not an error | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/test_governance_system.py:745` | protection JSON invalid | recorded as an audit FAIL | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/test_governance_system.py:983` | repo listing failed | stdout, exit 1, cause misreported | loud, logged, alerts | stderr with gh's cause plus alert_operator. |
| `tools/test_governance_system.py:992` | tests or audit failed | stdout summary, exit 2, no alert | loud, alerts | ERROR on stderr plus alert_operator when failed. |
| `tools/test_governance_system.py:996` | unhandled (requests exceptions in audit, json.loads at 134) | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
| `tools/upgrade_comp_environ_auto_reviewer.py:162` | rulesets endpoint 404 | [] (no rulesets); if protection actually blocks, the later PUT raises at 262 | compliant | none |
| `tools/upgrade_comp_environ_auto_reviewer.py:260` | Contents PUT fails | stdout, then raise_for_status, no alert | loud, alerts | ERROR on stderr plus alert_operator. |
| `tools/upgrade_comp_environ_auto_reviewer.py:281` | secrets listing fails | reported as missing; run proceeds | loud, alerts | Raise on a failed listing. |
| `tools/upgrade_comp_environ_auto_reviewer.py:348` | target file absent | stdout, return 1 | loud, alerts | stderr plus alert_operator. |
| `tools/upgrade_comp_environ_auto_reviewer.py:370` | Cerberus secrets missing (a known blocker) | --apply proceeds and returns 0 | loud, stops, alerts | Refuse --apply, or exit non-zero, while secrets are missing. |
| `tools/upgrade_comp_environ_auto_reviewer.py:408` | restoring ruleset bypass_actors fails | WARNING on stdout; if the PUT succeeded, main returns 0 with protection still weakened | loud, stops, alerts | ERROR on stderr, alert_operator, and exit non-zero. |
| `tools/upgrade_comp_environ_auto_reviewer.py:418` | re-enabling enforce_admins fails | WARNING on stdout; exit 0 with protection weakened | loud, stops, alerts | ERROR on stderr, alert_operator, and exit non-zero. |
| `tools/upgrade_comp_environ_auto_reviewer.py:434` | unhandled raise_for_status | traceback, no alert | alerts | Entry-point handler that calls alert_operator. |
