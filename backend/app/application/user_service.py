"""Сервис для работы с пользователями."""

import uuid
from typing import Optional, List

from app.domain.user import User
from app.domain.exceptions import EmailAlreadyExistsError, UserNotFoundError
from app.infrastructure.repositories import UserRepository

class UserService:
    """Сервис для операций с пользователями."""

    repo: UserRepository

    def __init__(self, repo: UserRepository):
        self.repo = repo

    # TODO: Реализовать register(email, name) -> User
    # 1. Проверить что email не занят
    # 2. Создать User
    # 3. Сохранить через repo.save()
    async def register(self, email: str, name: str = "") -> User:
        if await self.repo.find_by_email(email) is not None:
            raise EmailAlreadyExistsError(email)
        new_user: User = User(name=name, email=email)
        await self.repo.save(new_user)
        return new_user


    # TODO: Реализовать get_by_id(user_id) -> User
    async def get_by_id(self, user_id: uuid.UUID) -> User:
        found_user: Optional[User] = await self.repo.find_by_id(user_id)
        if found_user is None:
            raise UserNotFoundError(user_id)
        return found_user

    # TODO: Реализовать get_by_email(email) -> Optional[User]
    async def get_by_email(self, email: str) -> Optional[User]:
        return await self.repo.find_by_email(email)

    # TODO: Реализовать list_users() -> List[User]
    async def list_users(self) -> List[User]:
        return await self.repo.find_all()
