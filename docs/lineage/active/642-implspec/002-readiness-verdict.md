{
  "verdict": "REVISE",
  "summary": "The implementation spec is exceptionally detailed, providing complete, production-ready code for the core logic, utilities, and tests. However, it fails to address Requirement 10 from the LLD. There are no instructions to update the LangGraph workflow state to track `retry_count`, nor are there instructions to modify the call site to pass the newly required `RetryContext`. Without these integration steps, the code will either be unused or cause runtime type errors.",
  "blocking_issues": [
    {
      "section": "2. Files to Implement",
      "issue": "Missing files for the workflow state definition and the `build_retry_prompt` call site. LLD Requirement 10 explicitly mandates updating the workflow state to include `retry_count` (default 0) and updating the call site to pass `retry_count` and `previous_attempt_snippet`. These files must be added to the implementation scope.",
      "severity": "BLOCKING"
    },
    {
      "section": "10. Test Mapping",
      "issue": "Tests T210 and T220 from the original LLD (which verify the workflow state and call site integration) have been completely dropped from the Implementation Spec's test mapping.",
      "severity": "BLOCKING"
    }
  ],
  "suggestions": [
    "Identify the file defining the LangGraph state (e.g., `assemblyzero/workflows/implementation_spec/state.py`) and add instructions to include a `retry_count` field.",
    "Identify the node file that currently invokes `build_retry_prompt()` and provide the diff required to properly construct and pass the new `RetryContext` TypedDict.",
    "Add test instructions for T210 and T220 to ensure the integration between the workflow state and the prompt builder is covered."
  ]
}