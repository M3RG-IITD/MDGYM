"""
Main orchestrator for MD simulation problem solving.

Following SRP: Coordinates agents and validators to solve problems.
Following DIP: Depends on abstractions (BaseAgent, BaseValidator).
"""

import shutil
import time
import logging
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from .models.problem import MDSimulationProblem
from .models.result import SimulationResult, AttemptResult, AttemptStatus
from .agents.base_agent import BaseAgent
from .agents.factory import AgentFactory
from .validators.base_validator import BaseValidator
from .validators.factory import ValidatorFactory
from .exceptions import AgentExecutionError


logger = logging.getLogger(__name__)


class SimulationOrchestrator:
    """
    Orchestrates the process of solving MD simulation problems.
    
    Following SRP: Single responsibility is to coordinate the solving process.
    Following DIP: Depends on abstractions (BaseAgent, BaseValidator).
    """
    
    def __init__(
        self,
        agent: BaseAgent,
        validator: BaseValidator,
    ):
        """
        Initialize the orchestrator.

        Args:
            agent: The AI agent to use for solving
            validator: The validator for checking results
        """
        self.agent = agent
        self.validator = validator
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def solve(self, problem: MDSimulationProblem) -> SimulationResult:
        """
        Solve the MD simulation problem.
        
        Args:
            problem: The problem to solve
            
        Returns:
            SimulationResult: The result of the solving process
        """
        self.logger.info(
            f"Starting to solve problem with {self.agent.get_name()} "
            f"for {problem.engine.value}"
        )

        # Initialize result
        result = SimulationResult(
            problem_description=problem.description,
            agent_used=self.agent.get_name(),
            engine_used=problem.engine.value
        )

        start_time = time.time()

        attempt_result = self._execute_attempt(problem=problem)
        result.add_attempt(attempt_result)

        if attempt_result.status == AttemptStatus.SUCCESS:
            self.logger.info("Attempt succeeded")
        else:
            self.logger.warning("Attempt did not succeed")

        result.total_execution_time = time.time() - start_time

        self._convert_trajectory_log(problem.working_directory)

        return result
    
    def _execute_attempt(
        self,
        problem: MDSimulationProblem,
    ) -> AttemptResult:
        """
        Execute a single attempt to solve the problem.

        Args:
            problem: The problem to solve

        Returns:
            AttemptResult: Result of this attempt
        """
        attempt_start = time.time()
        timestamp = datetime.now()
        
        try:
            # In post-processing mode, seed the working dir with simulation files first
            if problem.script_dir:
                self._copy_script_files(problem.script_dir, problem.working_directory)

            # Build the prompt
            prompt = self._build_prompt(problem)
            self.logger.info(f"Solving Problem:\n{prompt}")
            
            # Execute the agent with timeout
            self.logger.info(f"Timeout set to {problem.timeout} seconds")
            output = self.agent.execute(
                prompt=prompt,
                working_dir=problem.working_directory,
                timeout=problem.timeout,
                engine=problem.engine.value
            )

            # Extract the final output from the agent's response
            output = self._extract_output(problem.working_directory)
            self.logger.info(f"Extracted output:\n{output}")
            
            # Validate the output
            validation_result = self.validator.validate(
                output=output,
                working_dir=problem.working_directory,
                ground_truth=problem.ground_truth
            )

            self.logger.info(f"Validation result: is_valid={validation_result.is_valid}, message={validation_result.message}")
            self.logger.info(f"Validation details: {validation_result.ground_truth_details}")
            self.logger.info(f"score: {validation_result.score}")

            # Determine status
            if validation_result.is_valid:
                status = AttemptStatus.SUCCESS
                error_message = None
            else:
                status = AttemptStatus.FAILURE
                error_message = validation_result.message
            
            execution_time = time.time() - attempt_start
            
            return AttemptResult(
                attempt_number=1,
                status=status,
                timestamp=timestamp,
                output=output,
                error_message=error_message,
                execution_time=execution_time,
                validation_details=validation_result.details,
                score=validation_result.score
            )

        except subprocess.TimeoutExpired as e:
            self.logger.exception(f"Agent execution timed out after {problem.timeout} seconds")
            execution_time = time.time() - attempt_start

            return AttemptResult(
                attempt_number=1,
                status=AttemptStatus.FAILURE,
                timestamp=timestamp,
                output=None,
                error_message=f"Simulation timed out after {problem.timeout} seconds",
                execution_time=execution_time
            )

        except AgentExecutionError as e:
            self.logger.exception(f"Agent execution failed: {str(e)}")
            execution_time = time.time() - attempt_start

            return AttemptResult(
                attempt_number=1,
                status=AttemptStatus.FAILURE,
                timestamp=timestamp,
                output=None,
                error_message=f"Agent execution error: {str(e)}",
                execution_time=execution_time
            )

        except Exception as e:
            self.logger.exception(f"Unexpected error during attempt: {str(e)}")
            execution_time = time.time() - attempt_start

            return AttemptResult(
                attempt_number=1,
                status=AttemptStatus.FAILURE,
                timestamp=timestamp,
                output=None,
                error_message=f"Unexpected error: {str(e)}",
                execution_time=execution_time
            )
    
    @staticmethod
    def _copy_script_files(script_dir: str, working_dir: str) -> None:
        """Copy simulation files from a golden script directory into the working directory."""
        src = Path(script_dir)
        dst = Path(working_dir)
        if not src.is_dir():
            raise FileNotFoundError(f"script_dir not found: {script_dir}")
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
        logger.info(f"Copied simulation files from {script_dir} -> {working_dir}")

    def _build_prompt(self, problem: MDSimulationProblem) -> str:
        """
        Build the prompt for the agent.

        Args:
            problem: The problem to solve

        Returns:
            str: The complete prompt
        """
        return problem.to_prompt()
    
    def _convert_trajectory_log(self, working_dir: str) -> None:
        """
        Convert trajectory_log.jsonl to trajectory_log.json in the run directory.
        Handles edge cases: blank lines, markdown fences, single-JSON fallback.
        """
        jsonl_path = Path(working_dir) / "trajectory_log.jsonl"
        if not jsonl_path.exists():
            self.logger.warning(f"trajectory_log.jsonl not found in {working_dir}, skipping conversion")
            return

        json_path = jsonl_path.with_suffix(".json")
        try:
            records, skipped = self._load_jsonl(jsonl_path)
        except ValueError as e:
            self.logger.warning(f"Could not parse trajectory_log.jsonl: {e}")
            return

        with json_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
            f.write("\n")

        self.logger.info(
            f"Converted trajectory_log.jsonl -> trajectory_log.json "
            f"({len(records)} records" + (f", {skipped} non-JSON lines skipped" if skipped else "") + ")"
        )

    @staticmethod
    def _load_jsonl(jsonl_path: Path):
        """
        Parse a JSONL file into a list of records.
        Returns (records, skipped_non_json_lines).
        Handles: blank lines, markdown fences, single-JSON fallback.
        """
        records = []
        skipped = 0

        with jsonl_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("```") or stripped.lower() == "json":
                skipped += 1
                continue
            if stripped[0] not in "[{":
                skipped += 1
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_no}: {e.msg}") from e

        if records:
            return records, skipped

        # Fallback: entire file may be a single JSON value
        cleaned = "".join(
            line for line in lines
            if line.strip() and not line.strip().startswith("```") and line.strip().lower() != "json"
        ).strip()
        if not cleaned:
            return [], skipped

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"No valid JSON entries found: {e.msg}") from e

        return (parsed if isinstance(parsed, list) else [parsed]), skipped

    def _extract_output(self, working_dir: str) -> Optional[Any]:
        """
        Extract the final output from the agent's response (trajectory_log.jsonl).

        Args:
            working_dir: The working directory where agent outputs are stored

        Returns:
            Optional[Any]: The last parsed JSON value from the log
        """

        output_json = Path(working_dir) / "final_answer.json"
        if not output_json.exists():
            self.logger.warning(f"Expected output file not found: {output_json}")
            return None
        
        try:
            with open(output_json, "r", encoding="utf-8") as f:
                output = json.load(f)
            return output
        except Exception as e:
            self.logger.exception(f"Failed to read output file: {str(e)}")
            return None

class OrchestratorBuilder:
    """
    Builder for creating SimulationOrchestrator instances.
    
    Following Builder pattern for complex object construction.
    Makes it easy to create orchestrators with different configurations.
    """
    
    def __init__(self):
        """Initialize builder."""
        self._agent_type = None
        self._engine = None
        self._agent_config = {}
        self._validator_config = {}
    
    def with_agent(self, agent_type: str, config: Optional[Dict[str, Any]] = None) -> 'OrchestratorBuilder':
        """
        Set the agent type.
        
        Args:
            agent_type: Type of agent (claude_code, codex)
            config: Optional agent configuration
            
        Returns:
            self for chaining
        """
        self._agent_type = agent_type
        if config:
            self._agent_config = config
        return self
    
    def with_engine(self, engine: str, config: Optional[Dict[str, Any]] = None) -> 'OrchestratorBuilder':
        """
        Set the MD engine.
        
        Args:
            engine: Engine type (lammps, gromacs)
            config: Optional validator configuration
            
        Returns:
            self for chaining
        """
        self._engine = engine
        if config:
            self._validator_config = config
        return self
    
    def build(self) -> SimulationOrchestrator:
        """
        Build the orchestrator.
        
        Returns:
            SimulationOrchestrator: Configured orchestrator
            
        Raises:
            ValueError: If required parameters are missing
        """
        if not self._agent_type:
            raise ValueError("Agent type must be specified")
        if not self._engine:
            raise ValueError("Engine must be specified")
        
        # Create agent
        agent = AgentFactory.create_agent(
            agent_type=self._agent_type,
            config=self._agent_config
        )
        
        # Create validator
        validator = ValidatorFactory.create_validator(
            engine=self._engine,
            config=self._validator_config
        )
        
        # Create orchestrator
        return SimulationOrchestrator(
            agent=agent,
            validator=validator,
        )
