"""Experimental benchmark helpers for role-based correction prompts."""

from .protocols import (
    PROTOCOL_ID,
    PROTOCOL_VERSION,
    RolePromptRequest,
    build_role_corrected_text_request,
    validate_role_corrected_text_response,
)

__all__ = [
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "RolePromptRequest",
    "build_role_corrected_text_request",
    "validate_role_corrected_text_response",
]

