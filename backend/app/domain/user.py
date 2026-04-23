"""Доменная сущность пользователя."""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
import re
from typing import Optional

from .exceptions import InvalidEmailError, InvalidNameError


# TODO: Реализовать класс User
# - Использовать @dataclass
# - Поля: email, name, id, created_at
# - Реализовать валидацию email в __post_init__
# - Regex: r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

@dataclass
class User:
    email: str
    name: Optional[str] = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.email or not self.email.strip() or not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", self.email) or len(self.email.strip()) >= 255:
            raise InvalidEmailError(self.email)
        self.email = self.email.strip()
        if self.name is not None and len(self.name) > 255:
            raise InvalidNameError(self.name)
