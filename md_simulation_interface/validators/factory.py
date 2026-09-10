"""
Factory for creating validators.

Following OCP: Easy to add new validator types.
Following DIP: Returns BaseValidator abstraction.
"""

from typing import Dict, Any, Optional
from .base_validator import BaseValidator
from .lammps_validator import LAMMPSValidator
from .gromacs_validator import GROMACSValidator
from ..models.problem import MDEngine
from ..exceptions import ConfigurationError


class ValidatorFactory:
    """
    Factory class for creating validators.
    
    Following SRP: Only responsible for validator creation.
    Following OCP: Can be extended with new validator types.
    """
    
    _validator_registry: Dict[MDEngine, type] = {
        MDEngine.LAMMPS: LAMMPSValidator,
        MDEngine.GROMACS: GROMACSValidator,
    }
    
    @classmethod
    def create_validator(
        cls, 
        engine: MDEngine | str, 
        config: Optional[Dict[str, Any]] = None
    ) -> BaseValidator:
        """
        Create a validator for the specified engine.
        
        Args:
            engine: MD engine type
            config: Optional configuration for the validator
            
        Returns:
            BaseValidator: Configured validator instance
            
        Raises:
            ConfigurationError: If engine type is invalid
        """
        # Convert string to enum if needed
        if isinstance(engine, str):
            try:
                engine = MDEngine(engine.lower())
            except ValueError:
                raise ConfigurationError(
                    f"Invalid engine type: {engine}. "
                    f"Valid types: {[e.value for e in MDEngine]}"
                )
        
        # Get the validator class
        validator_class = cls._validator_registry.get(engine)
        if not validator_class:
            raise ConfigurationError(
                f"No validator implementation for engine: {engine.value}"
            )
        
        # Create and return the validator
        validator = validator_class(config=config)
        return validator
    
    @classmethod
    def register_validator(cls, engine: MDEngine, validator_class: type) -> None:
        """
        Register a new validator type.
        
        This allows extending the factory with custom validators.
        
        Args:
            engine: The engine type identifier
            validator_class: The validator class to register
        """
        if not issubclass(validator_class, BaseValidator):
            raise ValueError(
                f"Validator class must be a subclass of BaseValidator, got {validator_class}"
            )
        cls._validator_registry[engine] = validator_class
    
    @classmethod
    def get_available_validators(cls) -> list[MDEngine]:
        """Get list of available validator types."""
        return list(cls._validator_registry.keys())
