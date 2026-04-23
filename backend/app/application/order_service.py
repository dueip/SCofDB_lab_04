"""Сервис для работы с заказами."""

import uuid
from decimal import Decimal
from typing import List, Optional

from app.domain.order import Order, OrderItem, OrderStatus
from app.domain.user import User
from app.domain.exceptions import OrderNotFoundError, UserNotFoundError
from app.infrastructure.repositories import UserRepository, OrderRepository

class OrderService:
    """Сервис для операций с заказами."""

    order_repo: OrderRepository
    user_repo: UserRepository
    def __init__(self, order_repo, user_repo):
        self.order_repo = order_repo
        self.user_repo = user_repo

    # TODO: Реализовать create_order(user_id) -> Order
    async def create_order(self, user_id: uuid.UUID) -> Order:
        found_user: Optional[User] = await self.user_repo.find_by_id(user_id)
        if found_user is None:
            raise UserNotFoundError(user_id)

        new_order: Order = Order(user_id)

        await self.order_repo.save(new_order)
        return new_order

    # TODO: Реализовать get_order(order_id) -> Order
    async def get_order(self, order_id: uuid.UUID) -> Order:
        found_order = await self.order_repo.find_by_id(order_id)
        if (found_order is None):
            raise OrderNotFoundError(order_id)

        return found_order

    # TODO: Реализовать add_item(order_id, product_name, price, quantity) -> OrderItem
    async def add_item(
        self,
        order_id: uuid.UUID,
        product_name: str,
        price: Decimal,
        quantity: int,
    ) -> OrderItem:
        found_order: Order = await self.get_order(order_id)
        created_item: OrderItem = found_order.add_item(product_name, price, quantity)
        await self.order_repo.save(found_order)
        return created_item 

    # TODO: Реализовать pay_order(order_id) -> Order
    # КРИТИЧНО: гарантировать что нельзя оплатить дважды!
    async def pay_order(self, order_id: uuid.UUID) -> Order:
        found_order: Order = await self.get_order(order_id)
        found_order.pay()
        await self.order_repo.save(found_order)
        return found_order


    # TODO: Реализовать cancel_order(order_id) -> Order
    async def cancel_order(self, order_id: uuid.UUID) -> Order:
        found_order: Order = await self.get_order(order_id)
        found_order.cancel()
        await self.order_repo.save(found_order)
        return found_order

    # TODO: Реализовать ship_order(order_id) -> Order
    async def ship_order(self, order_id: uuid.UUID) -> Order:
        found_order: Order = await self.get_order(order_id)
        found_order.ship()
        await self.order_repo.save(found_order)
        return found_order

    # TODO: Реализовать complete_order(order_id) -> Order
    async def complete_order(self, order_id: uuid.UUID) -> Order:
        found_order: Order = await self.get_order(order_id)
        found_order.complete()
        await self.order_repo.save(found_order)
        return found_order

    # TODO: Реализовать list_orders(user_id: Optional) -> List[Order]
    async def list_orders(self, user_id: Optional[uuid.UUID] = None) -> List[Order]:
        print("user_id:", user_id)
        if user_id is None:
            return await self.order_repo.find_all()
        found_user: Optional[User] = await self.user_repo.find_by_id(user_id)
        if found_user is None:
            raise UserNotFoundError(user_id)
        return await self.order_repo.find_by_user(user_id)       

    # TODO: Реализовать get_order_history(order_id) -> List[OrderStatusChange]
    async def get_order_history(self, order_id: uuid.UUID) -> List:
        order = await self.get_order(order_id)
        return order.status_history
