"""
Base agent interface following SOLID principles.

Following OCP: Open for extension (subclassing), closed for modification.
Following LSP: All subclasses must be substitutable for BaseAgent.
Following DIP: Depend on abstraction (BaseAgent), not concrete implementations.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
import logging


logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Types of AI agents available."""
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    GEMINI = "gemini"
    OPENHANDS = "openhands"


class BaseAgent(ABC):
    """
    Abstract base class for AI agents.
    
    Following SRP: Single responsibility is to execute AI agent commands.
    Following ISP: Minimal interface with only necessary methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def get_agent_type(self) -> AgentType:
        """
        Get the type of this agent.
        
        Returns:
            AgentType: The agent type
        """
        pass
    
    @abstractmethod
    def execute(self, prompt: str, working_dir: str, timeout: int, engine: str) -> str:
        """
        Execute the agent with the given prompt.
        
        Args:
            prompt: The problem description/prompt
            working_dir: working directory for execution
            timeout: timeout in seconds (default: 300 seconds / 5 minutes)
            engine:  engine name (e.g., "lammps", "gromacs") to tailor the agent's response
        Returns:
            str: The agent's output
            
        Raises:
            AgentExecutionError: If execution fails
        """
        pass
    
    @abstractmethod
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
        pass
    
    def get_name(self) -> str:
        """Get a human-readable name for this agent."""
        return self.get_agent_type().value.replace("_", " ").title()
