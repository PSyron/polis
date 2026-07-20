"""Local language-model abstractions and response validation."""

from polis.llm.adapter import (
    BackendRequest,
    LocalBackendTransport,
    MockHeuristicBackend,
    MockHeuristicTransport,
    create_default_local_backend,
)
from polis.llm.contracts import (
    LLM_PROMPT_VERSION,
    LLM_RESPONSE_SCHEMA_VERSION,
    LLMFindingInput,
    build_prompt,
    validate_llm_response,
)

__all__ = [
    "LLM_PROMPT_VERSION",
    "LLM_RESPONSE_SCHEMA_VERSION",
    "LLMFindingInput",
    "build_prompt",
    "validate_llm_response",
    "BackendRequest",
    "LocalBackendTransport",
    "MockHeuristicBackend",
    "MockHeuristicTransport",
    "create_default_local_backend",
]
