"""Model representing a molecular dynamics simulation problem."""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum
from pathlib import Path


class MDEngine(Enum):
    """Supported molecular dynamics engines."""
    LAMMPS = "lammps"
    GROMACS = "gromacs"


@dataclass
class MDSimulationProblem:
    """
    Represents a molecular dynamics simulation problem.
    
    Following SRP: This class only holds data about the problem.
    """
    
    description: str
    engine: MDEngine
    problem_id: str
    input_files: Dict[str, str] = field(default_factory=dict)
    expected_outputs: Dict[str, Any] = field(default_factory=dict)
    constraints: Optional[Dict[str, Any]] = field(default_factory=dict)
    ground_truth: Optional[Dict[str, Any]] = field(default_factory=dict)
    output_description: Optional[str] = None
    timeout: int = 900  # 15 minutes default timeout
    required_metrics: Optional[list] = field(default_factory=list)
    script_dir: Optional[str] = None  # Path to pre-run simulation files (post-processing mode)

    # Auto-generated fields
    run_id: str = field(default="")
    working_directory: str = field(default="")
    base_dir: Optional[str] = field(default=None)  # Override base; e.g. working_directory/<session_id>

    def __post_init__(self):
        """Validate the problem definition and setup working directory."""
        if not self.description:
            raise ValueError("Problem description cannot be empty")

        if isinstance(self.engine, str):
            self.engine = MDEngine(self.engine.lower())

        # run_id mirrors problem_id if not explicitly provided
        if not self.run_id:
            self.run_id = self.problem_id

        # Setup working directory structure: base_dir/run_id
        if not self.working_directory:
            base = Path(self.base_dir) if self.base_dir else Path("working_directory")
            self.working_directory = str(base / self.run_id)

        # Create working directory
        os.makedirs(self.working_directory, exist_ok=True)
    
    def to_prompt(self) -> str:
        """Return the appropriate prompt based on whether a golden script dir is set."""
        if self.script_dir:
            return self.to_postprocessing_prompt()
        return self.to_simulation_prompt()

    def to_postprocessing_prompt(self) -> str:
        """
        Prompt for post-processing mode: simulation already ran, agent must
        read existing output files and compute the final answer.
        """
        working_path = Path(self.working_directory)
        file_lines = sorted(
            f"  - {f.name}" for f in working_path.iterdir() if f.is_file()
        )
        file_list = "\n".join(file_lines) if file_lines else "  (none yet)"

        parts = [
            "Molecular Dynamics Post-Processing Task:",
            f"\nProblem ID: {self.problem_id}",
            f"\nEngine: {self.engine.value.upper()}",
            f"\nDescription:\n{self.description}",
            f"\nRequired Metrics: {', '.join(self.required_metrics) if self.required_metrics else 'None'}",
            "\nThe simulation has already been completed. All output files are in the current working directory:",
            file_list,
            "\n" + "=" * 60,
            "IMPORTANT INSTRUCTIONS:",
            "=" * 60,
            "0. Do NOT re-run the LAMMPS/GROMACS simulation. Use the existing output files to calulate the required quantities.",
            "1. Pay careful attention to units. All required units are specified in the problem description, and your answer must use those exact units.",
            "2. Write the final JSON object to final_answer.json for automatic extraction.",
            "3. Report the quantities asked in the problem description in JSON format, where the key is the name of the quantity and the value is its numerical value without units.",
            "4. Pay careful attention to units. All required units are specified in the problem description, and the final answer must use those exact units.",
            "5. Your final response must be ONLY a raw JSON object — no markdown, no code fences, no backticks, no explanation, and no preamble. The response must start with { and end with }.",
            "6. These are the only instructions. There in no AGENTS.md or such files."
        ]
        return "\n".join(parts)

    def to_simulation_prompt(self) -> str:
        """
        Prompt for full simulation mode: agent must write scripts, run the
        simulation, post-process, and report the answer.
        """
        prompt_parts = [
            "Molecular Dynamics Simulation Problem (Full Simulation Mode):",
            f"\nProblem ID: {self.problem_id}",
            f"\nEngine: {self.engine.value.upper()}",
            f"\nDescription:\n{self.description}",
            f"\nRequired Metrics: {', '.join(self.required_metrics) if self.required_metrics else 'None'}"
        ]
        
        if self.constraints:
            prompt_parts.append(f"\nConstraints:\n{self._format_dict(self.constraints)}")
        
        if self.input_files:
            prompt_parts.append(f"\nInput Files Available:\n{self._format_dict(self.input_files)}")
        
        if self.expected_outputs:
            prompt_parts.append(f"\nExpected Outputs:\n{self._format_dict(self.expected_outputs)}")
        
        if self.output_description:
            prompt_parts.append(f"\nOutput Description:\n{self.output_description}")
        
        # Add instructions for code formatting
        prompt_parts.append("\n" + "=" * 60)
        prompt_parts.append("IMPORTANT INSTRUCTIONS:")
        prompt_parts.append("=" * 60)
        prompt_parts.append(f"0. You have a total time limit of {self.timeout} seconds to solve this problem. Plan and execute efficiently within this budget.")
        prompt_parts.append(f"1. Generate all necessary code, scripts, and input files for the simulation in {self.engine.value.upper()} and write them to the working directory.")
        prompt_parts.append("2. Format code blocks with the filename for automatic extraction:")
        prompt_parts.append("   ```language:filename")
        prompt_parts.append("   code here...")
        prompt_parts.append("   ```")
        prompt_parts.append("3. Example formats for LAMMPS:")
        prompt_parts.append("   - ```lammps:simulation.in")
        prompt_parts.append("   - ```python:run_simulation.py")
        prompt_parts.append("   - ```bash:run_simulation.sh")
        prompt_parts.append("   Example formats for GROMACS:")
        prompt_parts.append("   - ```gromacs:md.mdp")
        prompt_parts.append("   - ```bash:run_gromacs.sh")
        prompt_parts.append("4. Use lmp_mpi_cpu to run LAMMPS and gmx_mpi to run GROMACS.")
        prompt_parts.append(f"5. The potential name is specified in the problem description. You don't need to download the potential file from the internet; you can access the potential file from the path: /MDGym/data/required/potentials/{self.problem_id}/.")
        prompt_parts.append(f"6. You can access the structure file from the path: /MDGym/data/required/structures/{self.problem_id}/. If the structure file is not present in that directory, you can make make your own structure file based on the information provided in the problem description.")
        prompt_parts.append("7. You don't need to check the compatibility of the environment or install the MD engine; always assume that the environment is pre-configured with the necessary software and dependencies to run the simulations. Start solving the problem right away as we have a time limit to solve the problem.")
        prompt_parts.append("8. Run the code and perform any required postprocessing to obtain the final answer.")
        prompt_parts.append("9. Report the quantities asked in the problem description in JSON format, where the key is the name of the quantity and the value is its numerical value without units.")
        prompt_parts.append("10. Pay careful attention to units. All required units are specified in the problem description, and the final answer must use those exact units.")
        prompt_parts.append("11. Your final response must be ONLY a raw JSON object — no markdown, no code fences, no backticks, no explanation, and no preamble. The response must start with { and end with }.")
        prompt_parts.append("12. Write the final JSON object to final_answer.json for automatic extraction.")
        prompt_parts.append("13. These are the only instructions. There in no AGENTS.md or such files.")

        return "\n".join(prompt_parts)
    
    @staticmethod
    def _format_dict(d: Dict[str, Any]) -> str:
        """Format dictionary for prompt display."""
        return "\n".join(f"  - {k}: {v}" for k, v in d.items())
