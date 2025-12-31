#!/usr/bin/env python

"""
Coder - The main AI coding assistant class.

This module provides the Coder class which coordinates AI-powered code editing.
All implementation is in CoderBase for better organization.
"""

from .coder_base import CoderBase, UnknownEditFormat, MissingAPIKeyError, FinishReasonLength


class Coder(CoderBase):
    """AI-powered coding assistant.
    
    Coordinates between the user, LLM, and code files to provide intelligent
    code editing assistance. Inherits all implementation from CoderBase.
    
    The separation into CoderBase allows for:
    - Better code organization with ~2000 lines moved to coder_base.py
    - Easier testing and maintenance
    - Cleaner separation of interface vs implementation
    
    All functionality is inherited from CoderBase - see coder_base.py for
    the actual implementation of all methods.
    """
    pass


# Re-export for backward compatibility
__all__ = ['Coder', 'UnknownEditFormat', 'MissingAPIKeyError', 'FinishReasonLength']
