"""Models for simulation results."""

from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import List, Optional, Dict, Any
from enum import Enum


class AttemptStatus(Enum):
    """Status of a solution attempt."""
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class AttemptResult:
    """Result of a single attempt to solve the problem."""

    attempt_number: int
    status: AttemptStatus
    timestamp: datetime
    output: Any
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    validation_details: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class SimulationResult:
    """Complete result of the simulation solving process."""

    problem_description: str
    agent_used: str
    engine_used: str
    attempts: List[AttemptResult] = field(default_factory=list)
    success: bool = False
    total_execution_time: float = 0.0
    final_output: Optional[Any] = None

    def add_attempt(self, attempt: AttemptResult) -> None:
        """Add an attempt result to the collection."""
        self.attempts.append(attempt)
        if attempt.status == AttemptStatus.SUCCESS:
            self.success = True
            self.final_output = attempt.output

    @staticmethod
    def _stringify_output(output: Any) -> str:
        """Convert structured output into a readable string form."""
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        return json.dumps(output, indent=2, default=str)

    def get_attempt_count(self) -> int:
        """Get the number of attempts made."""
        return len(self.attempts)

    def get_last_attempt(self) -> Optional[AttemptResult]:
        """Get the most recent attempt."""
        return self.attempts[-1] if self.attempts else None

    def to_summary(self) -> str:
        """Generate a human-readable summary of the results."""
        lines = [
            "=" * 60,
            "MD SIMULATION RESULT SUMMARY",
            "=" * 60,
            f"Problem: {self.problem_description[:100]}...",
            f"Agent: {self.agent_used}",
            f"Engine: {self.engine_used}",
            f"Success: {self.success}",
            f"Total Attempts: {self.get_attempt_count()}",
            f"Total Execution Time: {self.total_execution_time:.2f}s",
            "",
            "Attempt Details:",
        ]

        for attempt in self.attempts:
            lines.extend([
                f"\n  Attempt #{attempt.attempt_number}:",
                f"    Status: {attempt.status.value}",
                f"    Score: {attempt.score:.3f}",
                f"    Time: {attempt.execution_time:.2f}s" if attempt.execution_time else "    Time: N/A",
                f"    Error: {attempt.error_message}" if attempt.error_message else "",
            ])

        if self.final_output:
            final_output = self._stringify_output(self.final_output)
            lines.extend([
                "",
                "Final Output:",
                "-" * 60,
                final_output[:500] + ("..." if len(final_output) > 500 else ""),
            ])

        lines.append("=" * 60)
        return "\n".join(lines)

