"""Workflow configuration for Unified Requirements Workflow.

Issue #101: Unified Requirements Workflow

Provides:
- WorkflowConfig dataclass for workflow parameterization
- GateConfig for human gate configuration
- Factory functions for common configurations
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class GateConfig:
    """Configuration for human gates.

    Attributes:
        draft_gate: If True, pause after draft generation for human review.
        verdict_gate: If True, pause after Gemini verdict for human review.
    """

    draft_gate: bool = True
    verdict_gate: bool = True

    @classmethod
    def from_string(cls, gates_str: str) -> "GateConfig":
        """Create GateConfig from CLI --gates string.

        Args:
            gates_str: Gate specification string.
                - "draft,verdict" (default): Both gates enabled
                - "draft": Only draft gate
                - "verdict": Only verdict gate
                - "none": No human gates (fully automated)

        Returns:
            Configured GateConfig instance.

        Raises:
            ValueError: If gates_str is invalid.
        """
        gates_lower = gates_str.lower().strip()

        if gates_lower == "none":
            return cls(draft_gate=False, verdict_gate=False)
        elif gates_lower == "draft":
            return cls(draft_gate=True, verdict_gate=False)
        elif gates_lower == "verdict":
            return cls(draft_gate=False, verdict_gate=True)
        elif gates_lower in ("draft,verdict", "verdict,draft", "both"):
            return cls(draft_gate=True, verdict_gate=True)
        else:
            raise ValueError(
                f"Invalid gates specification '{gates_str}'. "
                f"Valid options: draft,verdict | draft | verdict | none"
            )

    def __str__(self) -> str:
        """Return human-readable gate configuration."""
        if self.draft_gate and self.verdict_gate:
            return "draft,verdict"
        elif self.draft_gate:
            return "draft"
        elif self.verdict_gate:
            return "verdict"
        else:
            return "none"


@dataclass
class WorkflowConfig:
    """Configuration for the unified governance workflow.

    Attributes:
        workflow_type: Either "issue" or "lld".
        drafter: LLM provider spec for drafting (e.g., "claude:opus-4.5").
        reviewer: LLM provider spec for reviewing (e.g., "gemini:2.5-pro").
        draft_template_path: Path to template file (relative to assemblyzero_root).
        review_prompt_path: Path to review prompt (relative to assemblyzero_root).
        gates: Human gate configuration.
        max_iterations: Maximum revision cycles before prompting.
        auto_mode: If True, skip VS Code and auto-progress.
        mock_mode: If True, use mock providers for testing.
        debug_mode: If True, enable verbose logging.
        dry_run: If True, simulate without making API calls or writing files.
    """

    workflow_type: Literal["issue", "lld"]
    drafter: str = "claude:opus-4.5"
    reviewer: str = "gemini:3-pro-preview"
    draft_template_path: Path = field(default_factory=lambda: Path(""))
    review_prompt_path: Path = field(default_factory=lambda: Path(""))
    gates: GateConfig = field(default_factory=GateConfig)
    max_iterations: int = 20
    auto_mode: bool = False
    mock_mode: bool = False
    debug_mode: bool = False
    dry_run: bool = False

    def __post_init__(self):
        """Set default template/prompt paths based on workflow_type."""
        # Path("") becomes Path(".") on Windows, so check for both
        draft_path_str = str(self.draft_template_path)
        if draft_path_str in ("", "."):
            if self.workflow_type == "issue":
                self.draft_template_path = Path("docs/templates/0101-issue-template.md")
            else:
                self.draft_template_path = Path("docs/templates/0102-feature-lld-template.md")

        review_path_str = str(self.review_prompt_path)
        if review_path_str in ("", "."):
            if self.workflow_type == "issue":
                self.review_prompt_path = Path("docs/skills/0701c-Issue-Review-Prompt.md")
            else:
                self.review_prompt_path = Path("docs/skills/0702c-LLD-Review-Prompt.md")

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors.

        Returns:
            List of error messages. Empty if valid.
        """
        errors = []

        # Validate workflow_type
        if self.workflow_type not in ("issue", "lld"):
            errors.append(f"Invalid workflow_type: {self.workflow_type}")

        # Validate drafter spec
        if ":" not in self.drafter:
            errors.append(
                f"Invalid drafter spec '{self.drafter}'. Expected format: provider:model"
            )

        # Validate reviewer spec
        if ":" not in self.reviewer:
            errors.append(
                f"Invalid reviewer spec '{self.reviewer}'. Expected format: provider:model"
            )

        # Validate max_iterations
        if self.max_iterations < 1:
            errors.append(f"max_iterations must be >= 1, got {self.max_iterations}")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid.

        Returns:
            True if configuration is valid.
        """
        return len(self.validate()) == 0


def create_issue_config(
    drafter: str = "claude:opus-4.5",
    reviewer: str = "gemini:3-pro-preview",
    gates: str = "draft,verdict",
    max_iterations: int = 20,
    auto_mode: bool = False,
    mock_mode: bool = False,
    debug_mode: bool = False,
    dry_run: bool = False,
) -> WorkflowConfig:
    """Create configuration for Issue creation workflow.

    Args:
        drafter: LLM provider spec for drafting.
        reviewer: LLM provider spec for reviewing.
        gates: Human gate specification.
        max_iterations: Maximum revision cycles.
        auto_mode: Skip VS Code, auto-progress.
        mock_mode: Use mock providers.
        debug_mode: Enable verbose logging.
        dry_run: Simulate without API calls.

    Returns:
        Configured WorkflowConfig for issue workflow.
    """
    return WorkflowConfig(
        workflow_type="issue",
        drafter=drafter,
        reviewer=reviewer,
        draft_template_path=Path("docs/templates/0101-issue-template.md"),
        review_prompt_path=Path("docs/skills/0701c-Issue-Review-Prompt.md"),
        gates=GateConfig.from_string(gates),
        max_iterations=max_iterations,
        auto_mode=auto_mode,
        mock_mode=mock_mode,
        debug_mode=debug_mode,
        dry_run=dry_run,
    )


def create_lld_config(
    drafter: str = "claude:opus-4.5",
    reviewer: str = "gemini:3-pro-preview",
    gates: str = "draft,verdict",
    max_iterations: int = 20,
    auto_mode: bool = False,
    mock_mode: bool = False,
    debug_mode: bool = False,
    dry_run: bool = False,
) -> WorkflowConfig:
    """Create configuration for LLD creation workflow.

    Args:
        drafter: LLM provider spec for drafting.
        reviewer: LLM provider spec for reviewing.
        gates: Human gate specification.
        max_iterations: Maximum revision cycles.
        auto_mode: Skip VS Code, auto-progress.
        mock_mode: Use mock providers.
        debug_mode: Enable verbose logging.
        dry_run: Simulate without API calls.

    Returns:
        Configured WorkflowConfig for LLD workflow.
    """
    return WorkflowConfig(
        workflow_type="lld",
        drafter=drafter,
        reviewer=reviewer,
        draft_template_path=Path("docs/templates/0102-feature-lld-template.md"),
        review_prompt_path=Path("docs/skills/0702c-LLD-Review-Prompt.md"),
        gates=GateConfig.from_string(gates),
        max_iterations=max_iterations,
        auto_mode=auto_mode,
        mock_mode=mock_mode,
        debug_mode=debug_mode,
        dry_run=dry_run,
    )


# Preset configurations for common use cases
WORKFLOW_PRESETS = {
    # Standard issue workflow with full human oversight
    "issue-standard": create_issue_config(),
    # Automated issue workflow (for CI/batch processing)
    "issue-auto": create_issue_config(gates="none", auto_mode=True),
    # Standard LLD workflow with full human oversight
    "lld-standard": create_lld_config(),
    # LLD workflow with only draft gate (auto-approve clean verdicts)
    "lld-draft-only": create_lld_config(gates="draft"),
    # Automated LLD workflow
    "lld-auto": create_lld_config(gates="none", auto_mode=True),
    # Testing preset with mock providers
    "test-mock": WorkflowConfig(
        workflow_type="lld",
        drafter="mock:test-drafter",
        reviewer="mock:test-reviewer",
        mock_mode=True,
    ),
}
