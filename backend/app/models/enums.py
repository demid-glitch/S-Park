import enum


class Role(str, enum.Enum):
    PLATFORM_ADMIN = "platform_admin"
    OWNER = "owner"
    ATTENDANT = "attendant"
    CUSTOMER = "customer"


class SpotStatus(str, enum.Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    OUT_OF_SERVICE = "out_of_service"


class TariffKind(str, enum.Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class ParkingSessionStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PaymentKind(str, enum.Enum):
    PARKING = "parking"
    EV_CHARGE = "ev_charge"
    SUBSCRIPTION = "subscription"


class PaymentMethod(str, enum.Enum):
    QPAY = "qpay"
    CASH = "cash"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class ShiftStatus(str, enum.Enum):
    OPEN = "open"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
