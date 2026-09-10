"""GROMACS simulation validator."""

import os
import re
from typing import Optional, Dict, Any
from .base_validator import BaseValidator, ValidationResult
from ..models.problem import MDEngine


class GROMACSValidator(BaseValidator):
    """
    Validator for GROMACS simulations.
    
    Following LSP: Can be used anywhere BaseValidator is expected.
    Following SRP: Only validates GROMACS outputs.
    """
    
    # Common GROMACS output files and patterns
    COMMON_OUTPUT_FILES = ["md.log", "confout.gro", "traj.trr", "ener.edr"]
    SUCCESS_PATTERNS = [
        r"Finished mdrun",
        r"Performance:",
        r"Writing final coordinates",
        r"gcq#",  # GROMACS Cool Quote - appears at successful end
    ]
    ERROR_PATTERNS = [
        r"Fatal error:",
        r"Error in user input:",
        r"ERROR:",
        r"Segmentation fault",
    ]
    
    def get_engine(self) -> MDEngine:
        """Return the engine type."""
        return MDEngine.GROMACS
    
    def validate(
        self, 
        output: Any, 
        working_dir: Optional[str] = None,
        ground_truth: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Validate GROMACS simulation output.
        
        Args:
            output: The agent's output
            working_dir: Working directory
            ground_truth: Ground truth values for validation
            
        Returns:
            ValidationResult: Validation result
        """
        if output is None or not isinstance(output, Dict) :
            return ValidationResult(
                is_valid=False,
                message="No output produced by agent",
                details={},
                warnings=["Agent did not produce any output"]
            )

        warnings = []
        details = {}
        
        # Validate against ground truth if provided.
        # The agent is expected to have produced a JSON block with physical
        # quantity names as keys and unitless numeric values as values.
        ground_truth_passed = None
        ground_truth_details = {}
        is_valid = True
        score = 0.0

        if ground_truth:
            ground_truth_passed, ground_truth_details = self._validate_ground_truth(
                output=output,
                ground_truth=ground_truth,
                tolerance=self.config.get("ground_truth_tolerance", 0.05)
            )

            score = self._calculate_score(ground_truth_details)

            if "_parse_error" in ground_truth_details:
                # Agent did not produce a parseable JSON result block
                is_valid = False
                warnings.append(
                    f"Ground truth validation failed: {ground_truth_details['_parse_error']}"
                )
            elif not ground_truth_passed:
                # JSON was parsed but one or more values are outside tolerance
                is_valid = False
                warnings.append("Ground truth validation failed: values outside tolerance")

        if is_valid:
            if ground_truth_passed:
                message = "GROMACS simulation successful and ground truth values match"
            else:
                message = "GROMACS simulation appears successful"
        else:
            if ground_truth is not None and ground_truth_details.get("_parse_error"):
                message = "GROMACS simulation ran but agent did not produce a valid JSON result"
            elif ground_truth is not None and not ground_truth_passed:
                message = "GROMACS simulation ran but calculated values do not match ground truth"
            else:
                message = "Could not confirm GROMACS simulation success"
                warnings.append("No clear success indicators found")
        
        return ValidationResult(
            is_valid=is_valid,
            message=message,
            details=details,
            warnings=warnings,
            ground_truth_passed=ground_truth_passed,
            ground_truth_details=ground_truth_details,
            score=score
        )
