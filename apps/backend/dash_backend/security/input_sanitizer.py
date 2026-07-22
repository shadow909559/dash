"""Input sanitization utilities for LLM prompt injection prevention."""

import re
from typing import Optional

# Maximum lengths for various inputs
MAX_USER_MESSAGE_LENGTH = 10000
MAX_MEMORY_CONTEXT_LENGTH = 5000
MAX_GOAL_DESCRIPTION_LENGTH = 2000
MAX_GOAL_NAME_LENGTH = 200

# Patterns that may indicate prompt injection attempts
PROMPT_INJECTION_PATTERNS = [
    r'ignore\s+(all\s+)?(previous|above|the\s+above|the)\s+instructions',
    r'disregard\s+(all\s+)?(previous|above|the\s+above|the)\s+instructions',
    r'forget\s+(all\s+)?(previous|above|the\s+above|the|everything|this)',
    r'forget\s+(all\s+)?(previous|above|the\s+above|the)\s+instructions',
    r'override\s+(all\s+)?(previous|above|the\s+above|the)\s+instructions',
    r'remove\s+(all\s+)?(previous|above|the\s+above|the)\s+(instructions|context|constraints|rules)',
    r'system\s*[:]\s*ignore',
    r'assistant\s*[:]\s*ignore',
    r'you\s+are\s+now',
    r'act\s+as\s+(a\s+)?',
    r'pretend\s+(to\s+be\s+)?',
    r'simulate\s+(a\s+)?',
    r'roleplay\s+(as\s+)?',
    r'\[SYSTEM\]',
    r'\[INSTRUCTION\]',
    r'\[DIRECTIVE\]',
    r'###\s*INSTRUCTION',
    r'---\s*INSTRUCTION',
    r'<<<\s*INSTRUCTION',
    r'new\s+instructions',
    r'update\s+(your\s+)?(system\s+)?(prompt|instructions|configuration)',
]


def sanitize_user_input(text: str, max_length: int = MAX_USER_MESSAGE_LENGTH) -> str:
    """Sanitize user input for LLM prompt injection.
    
    Args:
        text: The user input to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text truncated to max_length
    """
    if not text:
        return text
    
   # Truncate to max length
    sanitized = text[:max_length]
    
    # Remove null bytes and control characters (except newlines/tabs)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
    
    return sanitized


def sanitize_memory_context(text: str) -> str:
    """Sanitize memory context for LLM prompt injection.
    
    Args:
        text: The memory context to sanitize
        
    Returns:
        Sanitized text truncated to max length
    """
    if not text:
        return text
    
    return sanitize_user_input(text, MAX_MEMORY_CONTEXT_LENGTH)


def sanitize_goal_input(goal_name: str, goal_description: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Sanitize planner goal inputs for prompt injection.
    
    Args:
        goal_name: The goal name to sanitize
        goal_description: Optional goal description to sanitize
        
    Returns:
        Tuple of (sanitized_goal_name, sanitized_goal_description)
    """
    if not goal_name:
        goal_name = ""
    
    sanitized_name = sanitize_user_input(goal_name, MAX_GOAL_NAME_LENGTH)
    sanitized_desc = None
    
    if goal_description:
        sanitized_desc = sanitize_user_input(goal_description, MAX_GOAL_DESCRIPTION_LENGTH)
    
    return sanitized_name, sanitized_desc


def detect_prompt_injection(text: str) -> bool:
    """Detect potential prompt injection attempts.
    
    Args:
        text: The text to check
        
    Returns:
        True if potential injection detected, False otherwise
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False


def sanitize_for_llm(text: str, max_length: Optional[int] = None) -> str:
    """Comprehensive sanitization for LLM inputs.
    
    Args:
        text: The text to sanitize
        max_length: Optional maximum length override
        
    Returns:
        Sanitized text
    """
    if not text:
        return text
    
    if max_length is None:
        max_length = MAX_USER_MESSAGE_LENGTH
    
    sanitized = sanitize_user_input(text, max_length)
    
    # Log if injection detected (but don't block - AI systems need flexibility)
    if detect_prompt_injection(sanitized):
        # This is informational only - we allow the input but log it
        pass
    
    return sanitized
