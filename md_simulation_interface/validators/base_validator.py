"""
Base validator interface following SOLID principles.

Following ISP: Minimal interface for validation.
Following OCP: Open for extension, closed for modification.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import logging
from ..models.problem import MDEngine


@dataclass
class ValidationResult:
    """
    Result of validation.
    
    Following SRP: Only holds validation result data.
    """
    
    is_valid: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    ground_truth_passed: Optional[bool] = None
    ground_truth_details: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    
    def __str__(self) -> str:
        """String representation of validation result."""
        status = "VALID" if self.is_valid else "INVALID"
        lines = [f"Validation {status}: {self.message}"]
        
        if self.ground_truth_passed is not None:
            gt_status = "PASSED" if self.ground_truth_passed else "FAILED"
            lines.append(f"Ground Truth Validation: {gt_status}")
        
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {w}" for w in self.warnings)
        
        if self.details:
            lines.append("Details:")
            lines.extend(f"  {k}: {v}" for k, v in self.details.items())
        
        if self.ground_truth_details:
            lines.append("Ground Truth Details:")
            lines.extend(f"  {k}: {v}" for k, v in self.ground_truth_details.items())
        
        return "\n".join(lines)


class BaseValidator(ABC):
    """
    Abstract base class for MD simulation validators.
    
    Following SRP: Single responsibility is validation.
    Following LSP: All subclasses must be substitutable.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize validator.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def get_engine(self) -> MDEngine:
        """
        Get the MD engine this validator handles.
        
        Returns:
            MDEngine: The engine type
        """
        pass
    
    @abstractmethod
    def validate(
        self, 
        output: Dict[str, Any],
        working_dir: Optional[str] = None,
        ground_truth: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate the simulation output.
        
        Args:
            output: The agent's output to validate
            working_dir: Working directory where files may be located
            ground_truth: Ground truth values for validation
            
        Returns:
            ValidationResult: The validation result
        """
        pass
    
    def _check_file_exists(self, filepath: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            filepath: Path to the file
            
        Returns:
            bool: True if file exists
        """
        import os
        return os.path.exists(filepath)
    
    def _validate_ground_truth(
        self,
        output: Dict[str, Any],
        ground_truth: Dict[str, Any],
        tolerance: float = 0.01
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Validate output against ground truth values.

        The agent is expected to produce a final JSON block containing the
        calculated physical quantities as keys and their unitless numeric
        values as values, e.g.:
            ```json
            {"temperature": 300.1, "pressure": 1.013, "potential_energy": -4521.3}
            ```

        Args:
            output: The agent's output structured JSON
            ground_truth: Dictionary of expected {quantity_name: numeric_value}
            tolerance: Relative tolerance for numerical comparisons (default 1%)

        Returns:
            tuple: (passed, details_dict)
        """

        # --- Compare each ground truth key against the parsed JSON ---
        details = {}
        all_passed = True

        for key, expected_value in ground_truth.items():
            if key not in output:
                details[key] = {
                    "expected": expected_value,
                    "found": "NOT FOUND",
                    "passed": False
                }
                all_passed = False
                continue

            found_value = output[key]

            if isinstance(expected_value, (int, float)):
                try:
                    found_float = float(found_value)
                except (ValueError, TypeError):
                    details[key] = {
                        "expected": expected_value,
                        "found": found_value,
                        "passed": False,
                        "error": "value could not be converted to float"
                    }
                    all_passed = False
                    continue

                expected_float = float(expected_value)
                if expected_float != 0:
                    rel_error = abs(found_float - expected_float) / abs(expected_float)
                    passed = rel_error <= tolerance
                else:
                    rel_error = abs(found_float)
                    passed = rel_error <= tolerance

                details[key] = {
                    "expected": expected_float,
                    "found": found_float,
                    "relative_error": rel_error,
                    "passed": passed
                }
                if not passed:
                    all_passed = False
            else:
                # String comparison (case-insensitive)
                passed = str(found_value).lower() == str(expected_value).lower()
                details[key] = {
                    "expected": expected_value,
                    "found": found_value,
                    "passed": passed
                }
                if not passed:
                    all_passed = False

        return all_passed, details

    def _calculate_score(self, ground_truth_details: Dict[str, Any]) -> float:
        """
        Calculate an overall score based on ground truth validation details.
        
        This is a simple heuristic that gives partial credit for values that are close to expected.
        
        Args:
            ground_truth_details: Details from ground truth validation
        
        Returns:
            float: Overall score (0.0 to 1.0)
        """
        total = len(ground_truth_details)
        if total == 0:
            return 1.0

        passed = sum(1 for detail in ground_truth_details.values() if detail.get("passed"))
        return passed / total