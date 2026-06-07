"""Contract for payment providers. Implementations are deferred (Fase 2)."""
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from packages.auth_core.exceptions import BusinessLogicError


class PaymentsNotConfiguredError(BusinessLogicError):
    """Raised when a payment action is attempted while the integration is disabled."""


@dataclass
class PaymentCharge:
    """A request to charge for an appointment."""
    appointment_id: str | None
    amount_cents: int
    currency: str = "BRL"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentResult:
    """The outcome of a provider operation."""
    status: str  # pending | synced | failed | refunded
    external_id: str | None = None
    provider: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PaymentProvider(Protocol):
    """Provider interface a future adapter (Stripe, Mercado Pago, PDV) must satisfy."""

    name: str
    enabled: bool

    def create_charge(self, charge: PaymentCharge) -> PaymentResult: ...

    def sync_status(self, external_id: str) -> PaymentResult: ...

    def refund(self, external_id: str) -> PaymentResult: ...
