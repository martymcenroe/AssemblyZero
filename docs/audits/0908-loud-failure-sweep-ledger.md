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
| `assemblyzero/__init__.py` | 3 | not yet read | |
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
| `assemblyzero/graphs/__init__.py` | 1 | not yet read | |
| `assemblyzero/hooks/__init__.py` | 32 | not yet read | |
| `assemblyzero/hooks/cascade_action.py` | 118 | not yet read | |
| `assemblyzero/hooks/cascade_detector.py` | 202 | not yet read | |
| `assemblyzero/hooks/cascade_patterns.py` | 292 | not yet read | |
| `assemblyzero/hooks/file_write_validator.py` | 182 | not yet read | |
| `assemblyzero/hooks/types.py` | 33 | not yet read | |
| `assemblyzero/metrics/__init__.py` | 71 | not yet read | |
| `assemblyzero/metrics/aggregator.py` | 61 | not yet read | |
| `assemblyzero/metrics/cache.py` | 128 | not yet read | |
| `assemblyzero/metrics/collector.py` | 241 | not yet read | |
| `assemblyzero/metrics/config.py` | 102 | not yet read | |
| `assemblyzero/metrics/formatters.py` | 99 | not yet read | |
| `assemblyzero/metrics/models.py` | 125 | not yet read | |
| `assemblyzero/nodes/__init__.py` | 13 | not yet read | |
| `assemblyzero/nodes/anthropic_provider.py` | 99 | not yet read | |
| `assemblyzero/nodes/check_type_renames.py` | 314 | not yet read | |
| `assemblyzero/nodes/document_assembler.py` | 46 | not yet read | |
| `assemblyzero/nodes/inventory.py` | 104 | not yet read | |
| `assemblyzero/nodes/smoke_test_node.py` | 205 | not yet read | |
| `assemblyzero/profiles/claude.toml` | 53 | not yet read | |
| `assemblyzero/profiles/gemini.toml` | 11 | not yet read | |
| `assemblyzero/profiles/mock.toml` | 29 | not yet read | |
| `assemblyzero/speedrun/__init__.py` | 1 | not yet read | |
| `assemblyzero/speedrun/answer_key.py` | 397 | not yet read | |
| `assemblyzero/speedrun/archive.py` | 836 | not yet read | |
| `assemblyzero/speedrun/box_health.py` | 337 | not yet read | |
| `assemblyzero/speedrun/convergence.py` | 251 | not yet read | |
| `assemblyzero/speedrun/emergency_stop.py` | 311 | not yet read | |
| `assemblyzero/speedrun/factory_report.py` | 1665 | not yet read | |
| `assemblyzero/speedrun/golden_disasters.py` | 336 | not yet read | |
| `assemblyzero/speedrun/healing.py` | 170 | not yet read | |
| `assemblyzero/speedrun/leavings.py` | 351 | not yet read | |
| `assemblyzero/speedrun/must_resolve.py` | 724 | not yet read | |
| `assemblyzero/speedrun/preserved.py` | 162 | not yet read | |
| `assemblyzero/speedrun/prompt_ranking.py` | 172 | not yet read | |
| `assemblyzero/speedrun/prompt_telemetry.py` | 254 | not yet read | |
| `assemblyzero/speedrun/replay.py` | 691 | not yet read | |
| `assemblyzero/speedrun/requirements_status.py` | 123 | not yet read | |
| `assemblyzero/speedrun/restore.py` | 156 | not yet read | |
| `assemblyzero/speedrun/roll_blockers.py` | 251 | not yet read | |
| `assemblyzero/speedrun/successes.py` | 139 | not yet read | |
| `assemblyzero/speedrun/timing.py` | 327 | not yet read | |
| `assemblyzero/speedrun/worktrees.py` | 361 | not yet read | |
| `assemblyzero/spelunking/__init__.py` | 6 | not yet read | |
| `assemblyzero/spelunking/engine.py` | 171 | not yet read | |
| `assemblyzero/spelunking/extractors.py` | 241 | not yet read | |
| `assemblyzero/spelunking/models.py` | 115 | not yet read | |
| `assemblyzero/spelunking/report.py` | 174 | not yet read | |
| `assemblyzero/spelunking/verifiers.py` | 343 | not yet read | |
| `assemblyzero/telemetry/__init__.py` | 51 | not yet read | |
| `assemblyzero/telemetry/__main__.py` | 5 | not yet read | |
| `assemblyzero/telemetry/actor.py` | 62 | not yet read | |
| `assemblyzero/telemetry/cascade_events.py` | 173 | not yet read | |
| `assemblyzero/telemetry/cost.py` | 92 | not yet read | |
| `assemblyzero/telemetry/emitter.py` | 243 | not yet read | |
| `assemblyzero/telemetry/instrumentation.py` | 133 | not yet read | |
| `assemblyzero/telemetry/llm_call_record.py` | 67 | not yet read | |
| `assemblyzero/telemetry/store.py` | 158 | not yet read | |
| `assemblyzero/telemetry/sync.py` | 21 | not yet read | |
| `assemblyzero/tracing.py` | 39 | not yet read | |
| `assemblyzero/utils/__init__.py` | 55 | not yet read | |
| `assemblyzero/utils/ast_sentinel.py` | 530 | not yet read | |
| `assemblyzero/utils/codebase_reader.py` | 372 | not yet read | |
| `assemblyzero/utils/cost_tracker.py` | 153 | not yet read | |
| `assemblyzero/utils/file_type.py` | 59 | not yet read | |
| `assemblyzero/utils/git.py` | 123 | not yet read | |
| `assemblyzero/utils/github_metrics_client.py` | 262 | not yet read | |
| `assemblyzero/utils/lld_path_enforcer.py` | 221 | not yet read | |
| `assemblyzero/utils/lld_section_extractor.py` | 146 | not yet read | |
| `assemblyzero/utils/lld_verification.py` | 361 | not yet read | |
| `assemblyzero/utils/markdown_inventory.py` | 113 | not yet read | |
| `assemblyzero/utils/metrics_aggregator.py` | 453 | not yet read | |
| `assemblyzero/utils/metrics_config.py` | 207 | not yet read | |
| `assemblyzero/utils/metrics_models.py` | 97 | not yet read | |
| `assemblyzero/utils/pattern_scanner.py` | 493 | not yet read | |
| `assemblyzero/utils/process.py` | 43 | not yet read | |
| `assemblyzero/utils/retry.py` | 265 | not yet read | |
| `assemblyzero/utils/shell.py` | 112 | not yet read | |
| `assemblyzero/utils/speedrun.py` | 337 | not yet read | |
| `assemblyzero/utils/workflow_timeout.py` | 106 | not yet read | |
| `assemblyzero/visual_gate/__init__.py` | 12 | not yet read | |
| `assemblyzero/visual_gate/bundle.py` | 118 | not yet read | |
| `assemblyzero/visual_gate/config.py` | 88 | not yet read | |
| `assemblyzero/visual_gate/floor.py` | 39 | not yet read | |
| `assemblyzero/visual_gate/gate.py` | 567 | not yet read | |
| `assemblyzero/visual_gate/modify.py` | 227 | not yet read | |
| `assemblyzero/visual_gate/server.py` | 288 | not yet read | |
| `assemblyzero/workflows/__init__.py` | 5 | not yet read | |
| `assemblyzero/workflows/checkpoint.py` | 77 | not yet read | |
| `assemblyzero/workflows/death/__init__.py` | 27 | not yet read | |
| `assemblyzero/workflows/death/age_meter.py` | 191 | not yet read | |
| `assemblyzero/workflows/death/constants.py` | 62 | not yet read | |
| `assemblyzero/workflows/death/drift_scorer.py` | 274 | not yet read | |
| `assemblyzero/workflows/death/hourglass.py` | 363 | not yet read | |
| `assemblyzero/workflows/death/models.py` | 115 | not yet read | |
| `assemblyzero/workflows/death/reconciler.py` | 243 | not yet read | |
| `assemblyzero/workflows/death/skill.py` | 138 | not yet read | |
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
| `assemblyzero/workflows/janitor/__init__.py` | 8 | not yet read | |
| `assemblyzero/workflows/janitor/fixers.py` | 204 | not yet read | |
| `assemblyzero/workflows/janitor/graph.py` | 206 | not yet read | |
| `assemblyzero/workflows/janitor/probes/__init__.py` | 63 | not yet read | |
| `assemblyzero/workflows/janitor/probes/adr_collision.py` | 88 | not yet read | |
| `assemblyzero/workflows/janitor/probes/dead_references.py` | 67 | not yet read | |
| `assemblyzero/workflows/janitor/probes/drift.py` | 57 | not yet read | |
| `assemblyzero/workflows/janitor/probes/harvest.py` | 101 | not yet read | |
| `assemblyzero/workflows/janitor/probes/inventory_drift.py` | 75 | not yet read | |
| `assemblyzero/workflows/janitor/probes/links.py` | 160 | not yet read | |
| `assemblyzero/workflows/janitor/probes/persona_status.py` | 99 | not yet read | |
| `assemblyzero/workflows/janitor/probes/readme_claims.py` | 67 | not yet read | |
| `assemblyzero/workflows/janitor/probes/stale_timestamps.py` | 109 | not yet read | |
| `assemblyzero/workflows/janitor/probes/todo.py` | 128 | not yet read | |
| `assemblyzero/workflows/janitor/probes/worktrees.py` | 187 | not yet read | |
| `assemblyzero/workflows/janitor/reporter.py` | 296 | not yet read | |
| `assemblyzero/workflows/janitor/state.py` | 74 | not yet read | |
| `assemblyzero/workflows/lld/__init__.py` | 8 | not yet read | |
| `assemblyzero/workflows/lld/nodes/assembly_node.py` | 83 | not yet read | |
| `assemblyzero/workflows/lld/state.py` | 18 | not yet read | |
| `assemblyzero/workflows/lld/templates.py` | 34 | not yet read | |
| `assemblyzero/workflows/narration.py` | 187 | not yet read | |
| `assemblyzero/workflows/orchestrator/__init__.py` | 40 | not yet read | |
| `assemblyzero/workflows/orchestrator/artifacts.py` | 176 | not yet read | |
| `assemblyzero/workflows/orchestrator/config.py` | 181 | not yet read | |
| `assemblyzero/workflows/orchestrator/graph.py` | 745 | not yet read | |
| `assemblyzero/workflows/orchestrator/orchestrator.py` | 0 | not yet read | |
| `assemblyzero/workflows/orchestrator/resume.py` | 182 | not yet read | |
| `assemblyzero/workflows/orchestrator/stages.py` | 2502 | not yet read | |
| `assemblyzero/workflows/orchestrator/state.py` | 245 | not yet read | |
| `assemblyzero/workflows/parallel/__init__.py` | 15 | not yet read | |
| `assemblyzero/workflows/parallel/coordinator.py` | 188 | not yet read | |
| `assemblyzero/workflows/parallel/credential_coordinator.py` | 127 | not yet read | |
| `assemblyzero/workflows/parallel/input_sanitizer.py` | 39 | not yet read | |
| `assemblyzero/workflows/parallel/output_prefixer.py` | 45 | not yet read | |
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
| `assemblyzero/workflows/scout/__init__.py` | 25 | not yet read | |
| `assemblyzero/workflows/scout/budget.py` | 76 | not yet read | |
| `assemblyzero/workflows/scout/graph.py` | 76 | not yet read | |
| `assemblyzero/workflows/scout/instrumentation.py` | 126 | not yet read | |
| `assemblyzero/workflows/scout/nodes.py` | 332 | not yet read | |
| `assemblyzero/workflows/scout/prompts.py` | 94 | not yet read | |
| `assemblyzero/workflows/scout/security.py` | 132 | not yet read | |
| `assemblyzero/workflows/scout/templates.py` | 139 | not yet read | |
| `assemblyzero/workflows/telemetry/__init__.py` | 16 | not yet read | |
| `assemblyzero/workflows/telemetry/hallucination_log.py` | 124 | not yet read | |
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
| `tools/_gate.py` | 103 | not yet read | |
| `tools/_gh_retry.py` | 132 | not yet read | |
| `tools/_npm_manifest.py` | 108 | not yet read | |
| `tools/_pat_session.py` | 445 | not yet read | |
| `tools/answer_key_audit.py` | 66 | not yet read | |
| `tools/append_session_log.py` | 194 | not yet read | |
| `tools/archive_worktree_lineage.py` | 265 | not yet read | |
| `tools/assemblyzero-generate.py` | 249 | not yet read | |
| `tools/assemblyzero-harvest.py` | 514 | not yet read | |
| `tools/assemblyzero-permissions.py` | 958 | not yet read | |
| `tools/assemblyzero_config.py` | 342 | not yet read | |
| `tools/audit_cerberus_health.py` | 274 | not yet read | |
| `tools/audit_default_arg_patches.py` | 321 | not yet read | |
| `tools/audit_deferred_scope.py` | 877 | not yet read | |
| `tools/audit_fail_open.py` | 350 | not yet read | |
| `tools/audit_fleet_auto_merge_readiness.py` | 290 | not yet read | |
| `tools/audit_fleet_branch_protection.py` | 308 | not yet read | |
| `tools/audit_fleet_rulesets.py` | 360 | not yet read | |
| `tools/audit_fully_landed.py` | 119 | not yet read | |
| `tools/audit_gitignore_drift.py` | 233 | not yet read | |
| `tools/audit_halt_sites.py` | 298 | not yet read | |
| `tools/audit_loud_failure.py` | 99 | not yet read | |
| `tools/audit_schedule_check.py` | 361 | not yet read | |
| `tools/audit_tracked_log_writers.py` | 252 | not yet read | |
| `tools/auth-preflight.sh` | 20 | not yet read | |
| `tools/backfill_assemblyzero_flag.py` | 396 | not yet read | |
| `tools/backfill_canonical_labels.py` | 237 | not yet read | |
| `tools/backfill_issue_audit.py` | 844 | not yet read | |
| `tools/backfill_telemetry.py` | 228 | not yet read | |
| `tools/banned_command_sweep.py` | 176 | not yet read | |
| `tools/batch-workflow.sh` | 405 | not yet read | |
| `tools/batch_cleanup_quality_hooks.py` | 280 | not yet read | |
| `tools/batch_cleanup_security_hooks.py` | 319 | not yet read | |
| `tools/batch_deploy_hooks.py` | 358 | not yet read | |
| `tools/campaign_timing_dashboard.py` | 229 | not yet read | |
| `tools/cerberus_worker_key.py` | 85 | not yet read | |
| `tools/check_requirements.py` | 113 | not yet read | |
| `tools/check_requirements_form.py` | 102 | not yet read | |
| `tools/claude-usage-scraper.py` | 418 | not yet read | |
| `tools/claude_spend_lock.py` | 293 | not yet read | |
| `tools/claude_usage_compute.py` | 398 | not yet read | |
| `tools/clean_transcript.py` | 364 | not yet read | |
| `tools/collect-cross-project-metrics.py` | 194 | not yet read | |
| `tools/collect_cross_project_metrics.py` | 351 | not yet read | |
| `tools/compare_profiles.py` | 283 | not yet read | |
| `tools/consolidate_logs.py` | 182 | not yet read | |
| `tools/dependabot_morning_status.py` | 181 | not yet read | |
| `tools/dependabot_review.py` | 2419 | not yet read | |
| `tools/deploy_auto_reviewer_fleet.py` | 416 | not yet read | |
| `tools/deploy_auto_reviewer_poll_fix.py` | 363 | not yet read | |
| `tools/deploy_auto_reviewer_workflow.py` | 643 | not yet read | |
| `tools/deploy_boostgauge_landing_workflow.py` | 320 | not yet read | |
| `tools/deploy_boostgauge_release_yml.py` | 306 | not yet read | |
| `tools/deploy_cerberus_secrets.py` | 419 | not yet read | |
| `tools/derive_stage_nominals.py` | 149 | not yet read | |
| `tools/enable_dependabot.py` | 310 | not yet read | |
| `tools/enable_wikis.py` | 124 | not yet read | |
| `tools/factory_report.py` | 121 | not yet read | |
| `tools/fix_az_workflow_concurrency.py` | 111 | not yet read | |
| `tools/fix_branch_protections.py` | 378 | not yet read | |
| `tools/fix_gemini_ack.py` | 239 | not yet read | |
| `tools/fix_requires_python.py` | 256 | not yet read | |
| `tools/fixtures/README.md` | 70 | not yet read | |
| `tools/fixtures/sample_comments.json` | 42 | not yet read | |
| `tools/fixtures/sample_issues.json` | 44 | not yet read | |
| `tools/fleet_delete_pr_sentinel.py` | 445 | not yet read | |
| `tools/fleet_remove_claude_key.py` | 328 | not yet read | |
| `tools/fleet_set_delete_branch_on_merge.py` | 268 | not yet read | |
| `tools/fleet_set_permission_mode.py` | 409 | not yet read | |
| `tools/generate_dependabot_yml.py` | 490 | not yet read | |
| `tools/github_protection_audit.py` | 1407 | not yet read | |
| `tools/golden_disasters.py` | 92 | not yet read | |
| `tools/harvest_reviewer_idioms.py` | 117 | not yet read | |
| `tools/heal_report.py` | 171 | not yet read | |
| `tools/hermes_add_ci_workflow.py` | 345 | not yet read | |
| `tools/hermes_pin_workflow_shas.py` | 413 | not yet read | |
| `tools/land_1104_auto_reviewer_fix.py` | 297 | not yet read | |
| `tools/land_2283_ci_tiers.py` | 448 | not yet read | |
| `tools/land_aletheia_775.py` | 230 | not yet read | |
| `tools/land_aletheia_ci_oidc.py` | 269 | not yet read | |
| `tools/land_aletheia_ci_pipestatus.py` | 359 | not yet read | |
| `tools/land_career_lint_workflow.py` | 191 | not yet read | |
| `tools/land_career_test_ci.py` | 249 | not yet read | |
| `tools/land_dependabot_skip_1251.py` | 314 | not yet read | |
| `tools/land_polybolos_ci_workflow.py` | 322 | not yet read | |
| `tools/land_staged_workflow.py` | 491 | not yet read | |
| `tools/land_windows_ci_job.py` | 276 | not yet read | |
| `tools/lint_per_repo_claude_md.py` | 670 | not yet read | |
| `tools/merge_aletheia_603_audit_gate.py` | 375 | not yet read | |
| `tools/merge_sentinel_permissions_prs.py` | 334 | not yet read | |
| `tools/migrate_lineage_flat_to_run_scoped.py` | 139 | not yet read | |
| `tools/mine_quality_patterns.py` | 374 | not yet read | |
| `tools/mine_verdict_patterns.py` | 411 | not yet read | |
| `tools/model_scorecard.py` | 309 | not yet read | |
| `tools/modernize_dependencies.py` | 321 | not yet read | |
| `tools/new_repo.py` | 4004 | not yet read | |
| `tools/orchestrate.py` | 421 | not yet read | |
| `tools/pat_smoke_test.py` | 100 | not yet read | |
| `tools/prompt_failure_report.py` | 63 | not yet read | |
| `tools/prompt_revision_rank.py` | 80 | not yet read | |
| `tools/prove_idle_timeout.py` | 135 | not yet read | |
| `tools/push_workflow_fixes.py` | 475 | not yet read | |
| `tools/readonly_attribute_audit.py` | 230 | not yet read | |
| `tools/remediate_fleet_branch_protection.py` | 260 | not yet read | |
| `tools/remediate_patent_general_protection.py` | 230 | not yet read | |
| `tools/replay_run.py` | 402 | not yet read | |
| `tools/repo_drift_check.py` | 332 | not yet read | |
| `tools/require_status_check.py` | 215 | not yet read | |
| `tools/run_audit.py` | 852 | not yet read | |
| `tools/run_implement_from_lld.py` | 1489 | not yet read | |
| `tools/run_implementation_spec_workflow.py` | 750 | not yet read | |
| `tools/run_janitor_workflow.py` | 177 | not yet read | |
| `tools/run_requirements_workflow.py` | 1698 | not yet read | |
| `tools/run_scout_workflow.py` | 256 | not yet read | |
| `tools/secret-inventory.sh` | 169 | not yet read | |
| `tools/send_test_alert.py` | 39 | not yet read | |
| `tools/sentinel_migrate.py` | 275 | not yet read | |
| `tools/speedrun_archive.py` | 212 | not yet read | |
| `tools/speedrun_clean_check.py` | 409 | not yet read | |
| `tools/speedrun_new_attempt.py` | 379 | not yet read | |
| `tools/speedrun_overlay.py` | 141 | not yet read | |
| `tools/speedrun_reset.py` | 859 | not yet read | |
| `tools/speedrun_roll.py` | 4202 | not yet read | |
| `tools/speedrun_summarize.py` | 131 | not yet read | |
| `tools/stash_audit.py` | 246 | not yet read | |
| `tools/test-gate.py` | 223 | not yet read | |
| `tools/test_gate/__init__.py` | 6 | not yet read | |
| `tools/test_gate/auditor.py` | 193 | not yet read | |
| `tools/test_gate/models.py` | 48 | not yet read | |
| `tools/test_gate/parser.py` | 162 | not yet read | |
| `tools/test_governance_system.py` | 996 | not yet read | |
| `tools/transcript_filters.py` | 376 | not yet read | |
| `tools/update-doc-refs.py` | 303 | not yet read | |
| `tools/update_clio_repo_metadata.py` | 176 | not yet read | |
| `tools/upgrade_auto_reviewer_caller.py` | 235 | not yet read | |
| `tools/upgrade_boostgauge_auto_reviewer.py` | 386 | not yet read | |
| `tools/upgrade_comp_environ_auto_reviewer.py` | 434 | not yet read | |
| `tools/validate_skill.py` | 163 | not yet read | |
| `tools/verdict-analyzer.py` | 258 | not yet read | |
| `tools/verdict_analyzer/__init__.py` | 68 | not yet read | |
| `tools/verdict_analyzer/database.py` | 353 | not yet read | |
| `tools/verdict_analyzer/parser.py` | 225 | not yet read | |
| `tools/verdict_analyzer/patterns.py` | 89 | not yet read | |
| `tools/verdict_analyzer/scanner.py` | 197 | not yet read | |
| `tools/verdict_analyzer/template_updater.py` | 178 | not yet read | |
| `tools/verify_encrypted_secret.py` | 189 | not yet read | |
| `tools/verify_gpg_agent_ttl.py` | 163 | not yet read | |
| `tools/view_audit.py` | 240 | not yet read | |
| `tools/wait_for_pr.py` | 128 | not yet read | |
| `tools/widen_boostgauge_auto_reviewer_trigger.py` | 187 | not yet read | |

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
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:45` | analysis holds no test cases | INFO, {} | loud, logged, stops, alerts | raise or ERROR |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:82` | writing a test file fails | ERROR and re-raise, but no alert (N7.5 has no HALT route) | alerts | alert before re-raising |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:90` | deleting the staging dir fails | ignored, leaves a staging dir | loud, logged, alerts | drop ignore_errors, ERROR on failure |
| `assemblyzero/workflows/testing/nodes/adversarial_writer.py:134` | a test case has empty code | skipped silently, partial file | loud, logged, stops, alerts | ERROR and raise |
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
| `assemblyzero/workflows/testing/adversarial_gemini.py:214` | response model neither Pro nor Flash | WARNING, verification passes | loud, logged, stops, alerts | raise GeminiModelDowngradeError |
| `assemblyzero/workflows/testing/adversarial_gemini.py:291` | unexpected provider exception | re-raised as a timeout, which the node treats as a skip | loud, alerts | ERROR and re-raise the original |
| `assemblyzero/workflows/testing/adversarial_gemini.py:361` | success with no text | empty string accepted | loud, logged, stops, alerts | raise on empty |
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
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:132` | no implementation files | INFO, skipped; router always goes to N8 | loud, logged, stops, alerts | error_message, route to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:148` | client cannot be built | WARNING, skipped | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:164` | quota exhausted | WARNING, skipped | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:167` | model not permitted | WARNING, skipped | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:174` | downgraded to Flash | WARNING, skipped | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:177` | call failed or timed out | WARNING, skipped | loud, logged, stops, alerts | ERROR, error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:184` | malformed response | ERROR, verdict error, proceeds to N8 | stops, alerts | error_message, route to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:235` | generated file has violations | WARNING, deleted, partial set | loud, logged, stops, alerts | ERROR and fail the node |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:239` | removing a rejected file failed | pass; the file stays | loud, logged, stops, alerts | ERROR and raise |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:250` | zero valid tests | verdict fail at INFO, proceeds | loud, logged, stops, alerts | error_message to HALT |
| `assemblyzero/workflows/testing/nodes/adversarial_node.py:372` | a file cannot be read for context | WARNING, "", partial context | loud, logged, stops, alerts | ERROR and raise |
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
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:63` | a test has no assertions | warning only, valid can be True | loud, stops, alerts | count it as an error |
| `assemblyzero/workflows/testing/nodes/adversarial_validator.py:79` | parse fails after compile succeeded | bare pass, duplicate check skipped | loud, logged, stops, alerts | append to errors and ERROR |
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
| `assemblyzero/workflows/requirements/nodes/finalize.py:642` | writing the durable LLD copy | prints WARNING to stdout and continues | loud, stops, alerts | alert_operator and set error_message. |
| `assemblyzero/workflows/requirements/nodes/finalize.py:643` | the withdrawn fail-open convention | the tag justifies continuing | loud, stops, alerts | Delete the tag and fail. |
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
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:779` | a withdrawn `# fail-open:` tag on the not-reproduced path | the tag text is present in source | loud, logged, stops, alerts | delete the `# fail-open:` tag |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:814` | recording the conflict telemetry fails | prints "skipped" and continues | loud, alerts | log ERROR and call alert_operator |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py:825` | must-resolve issue filing fails | prints WARNING and continues to the halt | loud, alerts | log ERROR and call alert_operator naming the repo/issue |
| `assemblyzero/workflows/requirements/graph.py:182` | the N1 drafter returns an error | routes to HALT | compliant | none |
| `assemblyzero/workflows/requirements/graph.py:230` | mechanical validation is still failing at the iteration cap | routes to HALT; the HALT node derives a reason and calls alert_operator | compliant | none |
| `assemblyzero/workflows/requirements/graph.py:235` | route_after_validate_mechanical never reads error_message | a mechanical-node error goes on to N1b instead of HALT | stops | check error_message first and return "HALT" |
| `assemblyzero/workflows/requirements/graph.py:308` | route_after_ponder is unconditional | a Ponder node error goes on to mechanical validation | stops | route a non-empty error_message to HALT |
| `assemblyzero/workflows/requirements/graph.py:334` | the draft human gate sets an unrecognized next_node | ends the workflow silently | loud, logged, stops, alerts | return "HALT" for any next_node outside the known set |
| `assemblyzero/workflows/requirements/graph.py:380` | the open-questions revision loop runs out (verdict_count >= max) | goes to the verdict gate instead of failing | loud, logged, stops, alerts | return "HALT" with an error describing the unanswered questions |
| `assemblyzero/workflows/requirements/graph.py:414` | the BLOCKED revise loop runs out | goes on to finalize a BLOCKED draft instead of failing | loud, logged, stops, alerts | return "HALT" when the cap is reached with lld_status BLOCKED |
| `assemblyzero/workflows/requirements/graph.py:505` | route_after_finalize ignores error_message | a finalize error goes to END, never HALT, so the operator is never alerted | loud, alerts | check error_message and return "HALT" (add HALT to the N5 edge map) |
| `assemblyzero/workflows/requirements/graph.py:578` | N0b returns error_message (arc worktree cannot be cut) | the unconditional edge runs N0c's model calls before the halt | stops | replace it with a conditional edge whose router sends error_message to HALT |
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
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1725` | a spec fence does not parse | withdrawn fail-open tag; the fence is silently skipped | loud, logged | Remove the tag; log the skip at ERROR or rely on python_fences_parse explicitly without a silent continue. |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1746` | a first-party callee module does not parse | withdrawn fail-open tag; the module's calls go unchecked and the check passes | loud, logged, stops, alerts | Remove the tag and fail the check, or the node, naming the module and the SyntaxError. |
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
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:130` | N6 receives an empty spec draft | prints to stdout and returns error_message, but N6 -> END is an unconditional edge (graph.py:513), so HALT and the alert never run | loud, logged, stops, alerts | Route N6 through a conditional edge to HALT on error_message. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:137` | the spec draft is too short to finalize | returns error_message on the unconditional N6 -> END edge; stdout print only | loud, logged, stops, alerts | Route N6 to HALT on error_message. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:153` | finalize is reached with a verdict other than APPROVED | returns error_message on the unconditional N6 -> END edge; stdout print only | loud, logged, stops, alerts | Route N6 to HALT on error_message. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:166` | the issue number is invalid | returns error_message on the unconditional N6 -> END edge | loud, logged, stops, alerts | Route N6 to HALT on error_message. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:179` | repo_root is missing from state | defaults to the current directory and writes the spec there | loud, logged, stops, alerts | Return an error routed to HALT when repo_root is empty. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:219` | writing or renaming the temp file fails | removes the temp file and re-raises into the OSError handler | compliant | none |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:224` | the spec file write fails | prints "ERROR" to stdout and returns error_message on the unconditional N6 -> END edge | loud, logged, stops, alerts | Log to stderr at ERROR and route N6 to HALT. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:234` | the spec file is absent after the write | prints to stdout and returns error_message on the unconditional N6 -> END edge | loud, logged, stops, alerts | Route N6 to HALT on error_message. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:257` | the durable handoff copy cannot be written (resume contract broken) | prints a WARNING to stdout, continues, and reports the stage completed | loud, logged, stops, alerts | Log at ERROR, call alert_operator, and return an error routed to HALT. |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py:271` | audit_dir is missing or absent on disk | silently skips the audit-trail save, and the lineage move at line 279 | loud, logged, stops, alerts | Fail loudly when audit_dir is unset or missing. |
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
| `assemblyzero/workflows/implementation_spec/graph.py:265` | N4 next_node is empty or unrecognised | routes to END as a normal exit, with no error and no alert | loud, logged, stops, alerts | route only the explicit manual choice to END and anything unrecognised to HALT |
| `assemblyzero/workflows/implementation_spec/graph.py:513` | finalize_spec returns a non-empty error_message (finalize_spec.py lines 134-238: empty draft, invalid issue, write failure, file not created) | unconditional edge to END; the error never reaches HALT | loud, alerts | replace with a conditional edge that sends a non-empty error_message to HALT |
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
