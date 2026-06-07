from enum import Enum


class Vertical(str, Enum):
    SALON = "salon"
    DENTAL = "dental"
    MEDICAL = "medical"

class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"

class AppointmentSource(str, Enum):
    WHATSAPP = "whatsapp"
    DASHBOARD = "dashboard"
    API = "api"
    PHONE = "phone"

class ReminderType(str, Enum):
    CONFIRMATION_24H = "confirmation_24h"
    REMINDER_2H = "reminder_2h"
    POST_SERVICE = "post_service"
    RECALL = "recall"
    SATISFACTION = "satisfaction"
    REACTIVATION = "reactivation"

class ReminderStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    PROFESSIONAL = "professional"
