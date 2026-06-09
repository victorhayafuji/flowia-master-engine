"""Scheduling domain services — availability + appointments."""
from packages.scheduling.services.appointments import SchedulingAppointmentsMixin
from packages.scheduling.services.availability import SchedulingAvailabilityMixin

__all__ = [
    "SchedulingAppointmentsMixin",
    "SchedulingAvailabilityMixin",
]
