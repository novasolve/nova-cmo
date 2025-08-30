#!/usr/bin/env python3
"""
Interactive ICP Wizard Package
Conversational AI for Ideal Customer Profile Discovery
"""

from .core.icp_wizard import ICPWizard, ICPConfiguration
from .core.memory_system import ConversationMemory
from .cli import run_icp_wizard

__version__ = "1.0.0"
__author__ = "Lead Intelligence Team"
__description__ = "Conversational AI for Ideal Customer Profile Discovery"

__all__ = [
    "ICPWizard",
    "ICPConfiguration",
    "ConversationMemory",
    "run_icp_wizard"
]