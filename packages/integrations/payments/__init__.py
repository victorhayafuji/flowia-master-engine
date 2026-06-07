"""Payment integration (stub).

Future-ready scaffold mirroring packages/integrations/webhook. No provider is
active: the feature flag organizations.settings.integrations.payments.enabled is
False by default and the resolver returns a NoOpPaymentProvider. This lets the
product talk about "integra com seu PDV" without any real execution or scope creep.
"""
from packages.integrations.payments.base import (
    PaymentCharge,
    PaymentProvider,
    PaymentResult,
    PaymentsNotConfiguredError,
)
from packages.integrations.payments.stub import NoOpPaymentProvider
from packages.integrations.payments.tenant_resolver import get_payment_provider, get_payments_config

__all__ = [
    "PaymentCharge",
    "PaymentProvider",
    "PaymentResult",
    "PaymentsNotConfiguredError",
    "NoOpPaymentProvider",
    "get_payment_provider",
    "get_payments_config",
]
