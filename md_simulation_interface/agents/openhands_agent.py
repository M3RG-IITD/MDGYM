"""OpenHands headless agent implementation."""

from typing import Optional
from .base_agent import BaseAgent, AgentType
import subprocess


class OpenHandsAgent(BaseAgent):
    """
    Agent that uses OpenHands CLI in headless mode to solve MD simulation problems.

    Command pattern:
        openhands --headless --json -t "<prompt>"

    Following LSP: Can be used anywhere BaseAgent is expected.
    Following SRP: Only responsible for OpenHands CLI interaction.
    """

    DEFAULT_CLI_COMMAND = "openhands"

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize OpenHands agent.

        Args:
            config: Optional configuration with 'cli_path' and/or 'workspace_dir' keys.
        """
        super().__init__(config)
        self.cli_command = self.config.get("cli_path", self.DEFAULT_CLI_COMMAND)

    def get_agent_type(self) -> AgentType:
        """Return the agent type."""
        return AgentType.OPENHANDS

    def execute(self, prompt: str, working_dir: str, timeout: int, engine: str) -> str:
        """
        Execute OpenHands CLI in headless mode with the given prompt.

        Args:
            prompt: The problem description
            working_dir: Working directory for execution (OpenHands workspace)
            timeout: Timeout in seconds
            engine: The engine name (e.g., "lammps", "gromacs")

        Returns:
            str: Agent's response (JSON lines written to trajectory_log.jsonl)
        """
        import os
        from pathlib import Path

        try:
            if working_dir is None:
                working_dir = os.getcwd()

            os.makedirs(working_dir, exist_ok=True)

            working_path = Path(working_dir)
            log_file = working_path / "trajectory_log.jsonl"

            command_args = [
                self.cli_command,
                "--headless",
                "--json",
                "-t", prompt,
            ]

            stdout, stderr, returncode = self.run_command(
                command_args,
                working_dir=working_dir,
                log_file=log_file,
                timeout=timeout,
            )

            if returncode == 124:
                self.logger.warning(f"OpenHands execution timed out after {timeout} seconds")
                return stdout or ""

            if returncode < 0:
                signal_num = -returncode
                signal_names = {9: "SIGKILL", 15: "SIGTERM", 2: "SIGINT"}
                signal_name = signal_names.get(signal_num, f"Signal {signal_num}")
                self.logger.warning(f"OpenHands was killed by {signal_name} (code {returncode})")
                return stdout or ""

            if returncode != 0:
                self.logger.warning(f"OpenHands exited with code {returncode}")
                return stdout or ""

            self.logger.info("OpenHands executed successfully")
            return stdout

        except Exception as e:
            self.logger.warning(f"OpenHands execution encountered an error: {str(e)}")
            return ""

    def run_command(
        self,
        command: list,
        working_dir: str,
        log_file: str,
        timeout: int,
    ) -> tuple[str, str, int]:
        """
        Run a shell command and return output.

        Args:
            command: Command and arguments as list
            working_dir: Working directory for command
            log_file: Log file path to save output
            timeout: Timeout in seconds

        Returns:
            tuple: (stdout, stderr, return_code)
        """
        try:
            with open(log_file, "w") as lf:
                result = subprocess.run(
                    command,
                    cwd=working_dir,
                    stdout=lf,
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
