"""Scheduling service facade — availability, appointments and blocks."""
from packages.auth_core.database import db
from packages.scheduling.services.appointments import SchedulingAppointmentsMixin
from packages.scheduling.services.availability import SchedulingAvailabilityMixin


class SchedulingService(SchedulingAvailabilityMixin, SchedulingAppointmentsMixin):
    def __init__(self):
        self.db = db
