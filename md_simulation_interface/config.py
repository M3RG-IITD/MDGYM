"""Configuration management for MD Simulation Interface."""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager.
    
    Following SRP: Only responsible for configuration management.
    """
    
    DEFAULT_CONFIG = {
        "default_agent": "claude_code",
        "default_engine": "lammps",
        "timeout": 300,
        "log_level": "INFO",
        "agents": {
            "claude_code": {
                "cli_path": "claude",
                "timeout": 300
            },
            "codex": {
                "cli_path": "codex",
                "timeout": 300
            },
            "openhands": {
                "cli_path": "openhands",
                "timeout": 300
            }
        },
        "validators": {
            "lammps": {},
            "gromacs": {}
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Optional path to config file
        """
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path:
            self.load_from_file(config_path)
        else:
            # Try to load from default locations
            self._load_from_default_locations()
    
    def _load_from_default_locations(self) -> None:
        """Try to load config from default locations."""
        default_locations = [
            "md_sim_config.json",
            os.path.expanduser("~/.md_sim_config.json"),
            "/etc/md_sim_config.json"
        ]
        
        for location in default_locations:
            if os.path.exists(location):
                logger.info(f"Loading config from {location}")
                self.load_from_file(location)
                break
    
    def load_from_file(self, filepath: str) -> None:
        """
        Load configuration from a JSON file.
        
        Args:
            filepath: Path to config file
        """
        try:
            with open(filepath, 'r') as f:
                user_config = json.load(f)
            
            # Deep merge with default config
            self.config = self._deep_merge(self.config, user_config)
            logger.info(f"Configuration loaded from {filepath}")
            
        except Exception as e:
            logger.warning(f"Failed to load config from {filepath}: {e}")
    
    def save_to_file(self, filepath: str) -> None:
        """
        Save current configuration to a file.
        
        Args:
            filepath: Path to save config
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save config to {filepath}: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key (supports dot notation, e.g., 'agents.claude_code.timeout')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_agent_config(self, agent_type: str) -> Dict[str, Any]:
        """
        Get configuration for a specific agent.
        
        Args:
            agent_type: Agent type
            
        Returns:
            Agent configuration dictionary
        """
        return self.config.get("agents", {}).get(agent_type, {})
    
    def get_validator_config(self, engine: str) -> Dict[str, Any]:
        """
        Get configuration for a specific validator.
        
        Args:
            engine: Engine type
            
        Returns:
            Validator configuration dictionary
        """
        return self.config.get("validators", {}).get(engine, {})
    
    @staticmethod
    def _deep_merge(base: dict, update: dict) -> dict:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            update: Dictionary with updates
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


def setup_logging(log_level: str = "INFO") -> None:
    """
    Setup logging configuration.
    
    Args:
        log_level: Logging level
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
