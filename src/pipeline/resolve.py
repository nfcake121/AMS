"""Wrapper around resolve_sofa for building resolved IR."""

from src.schema import SofaRequest, resolve_sofa


def resolve_request_to_ir(sofa_request: SofaRequest) -> dict:
    """Resolve a SofaRequest into an intermediate representation."""
    resolved = resolve_sofa(sofa_request)
    return resolved.model_dump()


def resolve_sofa_request(sofa_request: SofaRequest) -> dict:
    """Backward-compatible wrapper for resolving SofaRequest."""
    return resolve_request_to_ir(sofa_request)
