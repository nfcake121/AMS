"""Wrapper around resolve_sofa for building resolved IR."""

# TODO: import resolve_sofa when implementation is available.

def resolve_request_to_ir(sofa_request):
    """Resolve a SofaRequest into an intermediate representation."""
    # TODO: call resolve_sofa and return resolved IR.
    return {
        "request": sofa_request,
        "resolved": None,
    }


def resolve_sofa_request(sofa_request):
    """Backward-compatible wrapper for resolving SofaRequest."""
    # TODO: remove when callers migrate to resolve_request_to_ir.
    return resolve_request_to_ir(sofa_request)
