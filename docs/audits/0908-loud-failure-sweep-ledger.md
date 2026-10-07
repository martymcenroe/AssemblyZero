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
| `assemblyzero/workflows/implementation_spec/__init__.py` | 44 | not yet read | |
| `assemblyzero/workflows/implementation_spec/assertion_manifest.py` | 464 | not yet read | |
| `assemblyzero/workflows/implementation_spec/atlas.py` | 167 | not yet read | |
| `assemblyzero/workflows/implementation_spec/base_tree.py` | 99 | not yet read | |
| `assemblyzero/workflows/implementation_spec/check_classification.py` | 352 | not yet read | |
| `assemblyzero/workflows/implementation_spec/criteria_coverage.py` | 302 | not yet read | |
| `assemblyzero/workflows/implementation_spec/error_path_coverage.py` | 207 | not yet read | |
| `assemblyzero/workflows/implementation_spec/graph.py` | 515 | not yet read | |
| `assemblyzero/workflows/implementation_spec/lineage_seed.py` | 210 | not yet read | |
| `assemblyzero/workflows/implementation_spec/message_addressability.py` | 168 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/__init__.py` | 77 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/analyze_codebase.py` | 1165 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/compile_manifest.py` | 288 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/edit_script.py` | 235 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/finalize_spec.py` | 385 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/generate_spec.py` | 1486 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/human_gate.py` | 207 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/load_lld.py` | 304 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/retry_prompt_builder.py` | 266 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/review_spec.py` | 872 | not yet read | |
| `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py` | 4508 | not yet read | |
| `assemblyzero/workflows/implementation_spec/review_progress.py` | 206 | not yet read | |
| `assemblyzero/workflows/implementation_spec/revision_pinning.py` | 596 | not yet read | |
| `assemblyzero/workflows/implementation_spec/spec_step_budget.py` | 76 | not yet read | |
| `assemblyzero/workflows/implementation_spec/state.py` | 283 | not yet read | |
| `assemblyzero/workflows/implementation_spec/table_injection.py` | 228 | not yet read | |
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
| `assemblyzero/workflows/requirements/__init__.py` | 41 | not yet read | |
| `assemblyzero/workflows/requirements/atlas.py` | 229 | not yet read | |
| `assemblyzero/workflows/requirements/audit.py` | 1221 | not yet read | |
| `assemblyzero/workflows/requirements/best_of_n.py` | 189 | not yet read | |
| `assemblyzero/workflows/requirements/config.py` | 264 | not yet read | |
| `assemblyzero/workflows/requirements/contract_fidelity.py` | 1115 | not yet read | |
| `assemblyzero/workflows/requirements/discrimination_check.py` | 328 | not yet read | |
| `assemblyzero/workflows/requirements/feedback_window.py` | 184 | not yet read | |
| `assemblyzero/workflows/requirements/form_check.py` | 844 | not yet read | |
| `assemblyzero/workflows/requirements/form_gate.py` | 287 | not yet read | |
| `assemblyzero/workflows/requirements/git_operations.py` | 411 | not yet read | |
| `assemblyzero/workflows/requirements/graph.py` | 687 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/__init__.py` | 56 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/analyze_codebase.py` | 644 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/analyze_requirements.py` | 828 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/finalize.py` | 805 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/generate_draft.py` | 1206 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/human_gate.py` | 236 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/lld_revision.py` | 123 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/load_input.py` | 363 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/ponder.py` | 108 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/ponder_rules.py` | 359 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/review.py` | 917 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` | 1828 | not yet read | |
| `assemblyzero/workflows/requirements/nodes/validate_test_plan.py` | 257 | not yet read | |
| `assemblyzero/workflows/requirements/ownership_check.py` | 673 | not yet read | |
| `assemblyzero/workflows/requirements/parsers/__init__.py` | 20 | not yet read | |
| `assemblyzero/workflows/requirements/parsers/draft_updater.py` | 315 | not yet read | |
| `assemblyzero/workflows/requirements/parsers/verdict_parser.py` | 295 | not yet read | |
| `assemblyzero/workflows/requirements/precheck.py` | 374 | not yet read | |
| `assemblyzero/workflows/requirements/scope_coverage.py` | 504 | not yet read | |
| `assemblyzero/workflows/requirements/state.py` | 485 | not yet read | |
| `assemblyzero/workflows/requirements/step_budget.py` | 164 | not yet read | |
| `assemblyzero/workflows/requirements/table_injection.py` | 222 | not yet read | |
| `assemblyzero/workflows/requirements/verdict_summarizer.py` | 225 | not yet read | |
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
