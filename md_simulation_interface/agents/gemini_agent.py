"""Gemini CLI agent implementation."""

from typing import Optional
from .base_agent import BaseAgent, AgentType
import subprocess


class GeminiAgent(BaseAgent):
    """
    Agent that uses Gemini CLI to solve MD simulation problems.
    
    Following LSP: Can be used anywhere BaseAgent is expected.
    Following SRP: Only responsible for Gemini CLI interaction.
    """
    
    DEFAULT_CLI_COMMAND = "gemini"
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize Gemini agent.
        
        Args:
            config: Optional configuration with 'cli_path' key
        """
        super().__init__(config)
        self.cli_command = self.config.get("cli_path", self.DEFAULT_CLI_COMMAND)
    
    def get_agent_type(self) -> AgentType:
        """Return the agent type."""
        return AgentType.GEMINI
    
    def execute(self, prompt: str, working_dir: str, timeout: int, engine: str) -> str:
        """
        Execute Gemini CLI with the given prompt.
        
        Args:
            prompt: The problem description
            working_dir: Working directory for execution
            timeout: Timeout in seconds (default: 300 seconds / 5 minutes)
            engine: The engine name (e.g., "lammps", "gromacs") to tailor the agent's response
            
        Returns:
            str: Agent's response
            
        Raises:
            AgentExecutionError: If execution fails
        """
        import os
        from pathlib import Path

        try: 
            # Set working directory (use current dir if not specified)
            if working_dir is None:
                working_dir = os.getcwd()
            
            # Ensure working directory exists
            os.makedirs(working_dir, exist_ok=True)
            
            # Setup paths
            working_path = Path(working_dir)
            log_file = working_path / "trajectory_log.jsonl"        
            
            # Build the command - note: we handle redirection in Python, not in shell
            command_args = [
                "node",
                os.path.expanduser("~/anaconda3/envs/gemini_env/bin/gemini"),
                "-m",
                "gemini-2.5-pro",
                "-p",
                prompt,  # The OS handles this safely as one solid block of text
                "--yolo",
                "--output-format",
                "stream-json"
            ]

            stdout, stderr, returncode = self.run_command(
                command_args,
                working_dir=working_dir,
                log_file=log_file,
                timeout=timeout
            )
            
            if returncode == 124:
                # Exit code 124 is from `timeout` command - process was killed due to timeout
                self.logger.warning(f"Gemini CLI execution timed out after {timeout} seconds")
                return stdout or ""

            if returncode < 0:
                # Negative return code means killed by signal (e.g., -9 = SIGKILL, -15 = SIGTERM)
                signal_num = -returncode
                signal_names = {9: "SIGKILL", 15: "SIGTERM", 2: "SIGINT"}
                signal_name = signal_names.get(signal_num, f"Signal {signal_num}")
                self.logger.warning(f"Gemini CLI was killed by {signal_name} (code {returncode})")
                return stdout or ""

            if returncode != 0:
                # Any other non-zero exit code - return gracefully for validation to handle
                self.logger.warning(f"Gemini CLI exited with code {returncode}")
                return stdout or ""

            self.logger.info("Gemini CLI executed successfully")
            return stdout

        except Exception as e:
            # Any exception during execution - log and return gracefully
            self.logger.warning(f"Gemini CLI execution encountered an error: {str(e)}")
            return ""
        
    def run_command(
        self, 
        command: list, 
        working_dir: str,
        log_file: str,
        timeout: int
    ) -> tuple[str, str, int]:
        """
        Run a shell command and return output.
        
        Args:
            command: Command and arguments as list
            working_dir: Working directory for command
            log_file: Log file path to save conversation and output
            timeout: Timeout in seconds

        Returns:
            tuple: (stdout, stderr, return_code)
        """
        try:
            
            with open(log_file, "w") as log_file:
                result = subprocess.run(
                    command,
                    cwd=working_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout or 900
                )
            
            return result.stdout, result.stderr, result.returncode
        
        except subprocess.TimeoutExpired as e:
            self.logger.warning(f"Command timed out after {timeout} seconds")
            return None, f"TimeoutExpired: command exceeded {timeout} seconds", 1
        except Exception as e:
            self.logger.exception(f"Command execution failed: {str(e)}")
            raise
