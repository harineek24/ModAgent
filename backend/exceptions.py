class ModAgentError(Exception):
    """Base exception for all ModAgent backend errors."""


class ClassificationError(ModAgentError):
    """Raised when the classifier fails to produce a valid ClassificationResult
    after exhausting retries."""


class RouterConfigError(ModAgentError):
    """Raised when the policy table is missing entries, has duplicate rows, or
    violates a cross-field invariant (e.g. critical severity without hard-route)."""


class EscalationRequired(ModAgentError):
    """Raised by the debate/judge layer when a verdict cannot be reached and the
    case must be routed to human review."""
