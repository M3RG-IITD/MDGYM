"""
MD Simulation Interface
A clean, SOLID-compliant interface for solving molecular dynamics problems using AI agents.
"""

__version__ = "1.0.0"
__author__ = "MD Simulation Interface Team"

from .orchestrator import SimulationOrchestrator
from .models.problem import MDSimulationProblem
from .models.result import SimulationResult

__all__ = ["SimulationOrchestrator", "MDSimulationProblem", "SimulationResult"]
