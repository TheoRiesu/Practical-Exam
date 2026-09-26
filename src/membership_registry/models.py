"""Domain models (mirrors prisma/schema.prisma)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MembershipType(str, Enum):
    REGULAR = "REGULAR"
    STUDENT = "STUDENT"
    SENIOR = "SENIOR"
    HONORARY = "HONORARY"
    ASSOCIATE = "ASSOCIATE"


class MemberStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"


@dataclass
class Member:
    first_name: str
    last_name: str
    email: str
    join_date: str  # ISO YYYY-MM-DD
    member_code: str = ""  # auto-assigned e.g. M-0001 if blank
    phone: str = ""
    date_of_birth: str = ""
    membership_type: str = MembershipType.REGULAR.value
    status: str = MemberStatus.ACTIVE.value
    address: str = ""
    notes: str = ""
    id: int | None = field(default=None)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def to_row(self) -> dict:
        return {
            "member_code": self.member_code,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone or None,
            "date_of_birth": self.date_of_birth or None,
            "membership_type": self.membership_type,
            "status": self.status,
            "join_date": self.join_date,
            "address": self.address or None,
            "notes": self.notes or None,
        }
