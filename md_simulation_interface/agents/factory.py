"""
Factory for creating agents.

Following OCP: Easy to add new agent types without modifying existing code.
Following DIP: Returns BaseAgent abstraction, not concrete types.
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent, AgentType
from .claude_agent import ClaudeCodeAgent
from .codex_agent import CodexAgent
from .gemini_agent import GeminiAgent
from .openhands_agent import OpenHandsAgent
from ..exceptions import ConfigurationError


class AgentFactory:
    """
    Factory class for creating AI agents.
    
    Following SRP: Only responsible for agent creation.
    Following OCP: Can be extended with new agent types.
    """
    
    _agent_registry: Dict[AgentType, type] = {
        AgentType.CLAUDE_CODE: ClaudeCodeAgent,
        AgentType.CODEX: CodexAgent,
        AgentType.GEMINI: GeminiAgent,
        AgentType.OPENHANDS: OpenHandsAgent,
    }
    
    @classmethod
    def create_agent(
        cls, 
        agent_type: AgentType | str, 
        config: Optional[Dict[str, Any]] = None
    ) -> BaseAgent:
        """
        Create an agent of the specified type.
        
        Args:
            agent_type: Type of agent to create
            config: Optional configuration for the agent
            
        Returns:
            BaseAgent: Configured agent instance
            
        Raises:
            ConfigurationError: If agent type is invalid
        """
        # Convert string to enum if needed
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type.lower())
            except ValueError:
                raise ConfigurationError(
                    f"Invalid agent type: {agent_type}. "
                    f"Valid types: {[t.value for t in AgentType]}"
                )
        
        # Get the agent class
        agent_class = cls._agent_registry.get(agent_type)
        if not agent_class:
            raise ConfigurationError(
                f"No agent implementation for type: {agent_type.value}"
            )
        
        # Create and return the agent
        agent = agent_class(config=config)
        return agent
    
    @classmethod
    def register_agent(cls, agent_type: AgentType, agent_class: type) -> None:
        """
        Register a new agent type.
        
        This allows extending the factory with custom agents.
        
        Args:
            agent_type: The agent type identifier
            agent_class: The agent class to register
        """
        if not issubclass(agent_class, BaseAgent):
            raise ValueError(
                f"Agent class must be a subclass of BaseAgent, got {agent_class}"
            )
        cls._agent_registry[agent_type] = agent_class
    
    @classmethod
    def get_available_agents(cls) -> list[AgentType]:
        """Get list of available agent types."""
        return list(cls._agent_registry.keys())
