"""
LAB 04: Демонстрация проблемы retry без идемпотентности.

Сценарий:
1) Клиент отправил запрос на оплату.
2) До получения ответа \"сеть оборвалась\" (моделируем повтором запроса).
3) Клиент повторил запрос БЕЗ Idempotency-Key.
4) В unsafe-режиме возможна двойная оплата.
"""

import pytest
import pytest
import pytest
import asyncio
import pytest
from sqlalchemy import text
import uuid
from httpx import AsyncClient
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.main import app
from app.application.payment_service import PaymentService
from sqlalchemy.orm import sessionmaker
import json

from app.application.payment_service import PaymentService
from app.domain.exceptions import OrderAlreadyPaidError

# TODO: Настроить подключение к тестовой БД
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/marketplace"

async def _create_another_order(db_session) -> uuid.UUID:
    user_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO users (id, email, name, created_at) VALUES (:id, :email, :name, NOW())"),
        {"id": user_id, "email": "another@test.com", "name": "Another User"},
    )
    order_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO orders (id, user_id, created_at, status, total_amount) "
            "VALUES (:id, :user_id, NOW(), 'created', 1000)"
        ),
        {"id": order_id, "user_id": user_id},
    )
    await db_session.execute(
        text(
            "INSERT INTO order_status_history (id, order_id, status, changed_at) "
            "VALUES (:id, :order_id, 'created', NOW())"
        ),
        {"id": uuid.uuid4(), "order_id": order_id},
    )
    await db_session.commit()

    return order_id

@pytest.fixture
async def db_session():
    """
    Создать сессию БД для тестов.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание сессии
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session: AsyncSession = AsyncSession(engine)
    async with async_session as session:
        yield session


@pytest.fixture
async def test_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание тестового заказа
    user_id= uuid.uuid4()
    user_query = text("""
        INSERT INTO users (id, email, name, created_at)
        VALUES (:id, 'meow@meow.meow', 'Meow User', NOW())
""")
    await db_session.execute(user_query, {"id": user_id})
    order_id = uuid.uuid4()
    order_query = text("""
        INSERT INTO orders (id, user_id, created_at, status, total_amount)
        VALUES (:id, :user_id, NOW(), 'created', 1000)
""")
    await db_session.execute(order_query, {"id": order_id, "user_id": user_id})
    
    what_query = text("""
        INSERT INTO order_status_history (id, order_id, status, changed_at)
        VALUES (:id, :order_id, 'created', NOW())
    """)
    await db_session.execute(what_query, {"id": uuid.uuid4(), "order_id": order_id})

    await db_session.commit()

    yield order_id

    await db_session.execute(text("DELETE FROM order_status_history WHERE order_id = :order_id"), {"order_id": order_id})
    await db_session.execute(text("DELETE FROM orders WHERE id = :id"), {"id": order_id})
    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    await db_session.commit()


@pytest.mark.asyncio
async def test_retry_without_idempotency_can_double_pay(db_session, test_order):
    """
    TODO: Реализовать тест.

    Рекомендуемые шаги:
    1) Создать заказ в статусе created.
    2) Выполнить две параллельные попытки POST /api/payments/retry-demo
       с mode='unsafe' и БЕЗ заголовка Idempotency-Key.
    3) Проверить историю order_status_history:
       - paid-событий больше 1 (или иная метрика двойного списания).
    4) Вывести понятный отчёт в stdout:
       - сколько попыток
       - сколько paid в истории
       - почему это проблема.
    """
    engine = create_async_engine(DATABASE_URL)

    async def payment_attempt_1():
        async with AsyncSession(engine) as session1:
            service = PaymentService(session1)
            return await service.pay_order_unsafe(test_order)

    async def payment_attempt_2():
        async with AsyncSession(engine) as session2:
            service = PaymentService(session2)
            return await service.pay_order_unsafe(test_order)

    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True
    )

    async with AsyncClient(app=app, base_url="http://test") as test:
      history_response = await test.get(f"/api/payments/history/{test_order}")
    
    assert history_response.status_code == 200
    history_data = history_response.json()
    paid_count = history_data["payment_count"]

    if paid_count > 1:
        print("\n❌ ПРОБЛЕМА: Двойная оплата!")
        print("   В unsafe-режиме при повторном запросе без Idempotency-Key")
        print("   происходит двойная оплата, так как нет защиты от повторов.")
        print("   Это критическая проблема для системы оплат.")
    else:
        print("\n✅ Безопасно: только одна оплата")
        print("   В данном случае система работает корректно,")
        print("   но это может быть случайным поведением.")

    assert paid_count > 1
