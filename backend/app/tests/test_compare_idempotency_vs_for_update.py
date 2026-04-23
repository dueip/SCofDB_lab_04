"""
LAB 04: Сравнение подходов
1) FOR UPDATE (решение из lab_02)
2) Idempotency-Key + middleware (lab_04)
"""

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
async def test_compare_for_update_and_idempotency_behaviour(db_session, test_order):
    """
    TODO: Реализовать сравнительный тест/сценарий.

    Минимум сравнения:
    1) Повтор запроса с mode='for_update':
       - защита от гонки на уровне БД,
       - повтор может вернуть бизнес-ошибку \"already paid\".
    2) Повтор запроса с mode='unsafe' + Idempotency-Key:
       - второй вызов возвращает тот же кэшированный успешный ответ,
         без повторного списания.

    В конце добавьте вывод:
    - чем отличаются цели и UX двух подходов,
    - почему они не взаимоисключающие и могут использоваться вместе.
    """
    print("==== FOR UPDATE ====")
    async with AsyncClient(app=app, base_url="http://test") as client:
        order_id = str(test_order)
        payload = {"order_id": order_id, "mode": "safe"}

        resp1 = await client.post("/api/payments/pay", json=payload)
        assert resp1.status_code == 200, f"Expected 200, got {resp1.status_code}: {resp1.text}"

        # Повторная попытка должна вернуть ошибку (уже оплачен)
        resp2 = await client.post("/api/payments/pay", json=payload)
        assert resp2.status_code == 200, "Duplicate FOR UPDATE request should not succeed"
        assert "already paid" in resp2.text.lower(), (
            f"Expected 'already paid' in error, got: {resp2.text}"
        )

    print("\n==== Idempotency-Key ====")
    new_order_id = await _create_another_order(db_session)
    idempotency_key = "test-key-123"

    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {"order_id": str(new_order_id), "mode": "unsafe"}
        headers = {"Idempotency-Key": idempotency_key}

        resp1 = await client.post("/api/payments/pay", json=payload, headers=headers)
        assert resp1.status_code == 200, f"First idempotent call failed: {resp1.text}"

        resp2 = await client.post("/api/payments/pay", json=payload, headers=headers)
        assert resp2.status_code == 200, "Cached idempotent response should be 200"
        assert resp2.headers.get("X-Idempotency-Replayed") == "true", (
            "Response should contain X-Idempotency-Replayed: true"
        )
        assert resp1.json() == resp2.json(), "Cached response body must be identical"
        print(
            "Idempotency-Key: повторный запрос вернул тот же успешный ответ, "
            "повторного списания не произошло."
        )

    print("\n==== Сравнение подходов ====")
    print("FOR UPDATE:")
    print(" Защита от гонок на уровне СУБД (SELECT ... FOR UPDATE).")
    print(" Повторный идентичный запрос приводит к бизнес-ошибке (already paid).")
    print(" UX: клиент должен уметь обрабатывать ошибку и понимать, что оплата уже прошла.")
    print()
    print("Idempotency-Key + middleware:")
    print(" Кэширует результат первого успешного запроса.")
    print(" Повторный запрос с тем же ключом мгновенно возвращает тот же успешный ответ.")
    print(" UX: клиенту не нужно различать ошибки – можно безопасно повторять запрос.")
    print()
    print("Они не взаимоисключающие:")
    print(" FOR UPDATE гарантирует корректность данных в БД даже при конкурентных запросах.")
    print("  Idempotency-Key улучшает UX и снижает нагрузку, избегая повторной бизнес-логики.")
    print("  На практике используют оба: ключ идемпотентности на уровне API и пессимистичные")
    print("   блокировки внутри сервиса для абсолютной надёжности.")
