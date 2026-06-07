"""No-op payment provider used while the integration is disabled."""
from packages.integrations.payments.base import (
    PaymentCharge,
    PaymentResult,
    PaymentsNotConfiguredError,
)

_DISABLED_MESSAGE = (
    "Integração de pagamentos desativada para esta organização. "
    "Ative em organizations.settings.integrations.payments quando disponível."
)


class NoOpPaymentProvider:
    """Always-disabled provider. Every action raises PaymentsNotConfiguredError."""

    name = "noop"
    enabled = False

    def create_charge(self, charge: PaymentCharge) -> PaymentResult:
        raise PaymentsNotConfiguredError(_DISABLED_MESSAGE)

    def sync_status(self, external_id: str) -> PaymentResult:
        raise PaymentsNotConfiguredError(_DISABLED_MESSAGE)

    def refund(self, external_id: str) -> PaymentResult:
        raise PaymentsNotConfiguredError(_DISABLED_MESSAGE)
