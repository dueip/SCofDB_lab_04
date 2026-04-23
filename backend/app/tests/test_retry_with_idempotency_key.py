"""
LAB 04: Проверка идемпотентного повтора запроса.

Цель:
При повторном запросе с тем же Idempotency-Key вернуть
кэшированный результат без повторного списания.
"""

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
async def test_retry_with_same_key_returns_cached_response(db_session, test_order):
    """
    TODO: Реализовать тест.

    Рекомендуемые шаги:
    1) Создать заказ в статусе created.
    2) Сделать первый POST /api/payments/retry-demo (mode='unsafe')
       с заголовком Idempotency-Key: fixed-key-123.
    3) Повторить тот же POST с тем же ключом и тем же payload.
    4) Проверить:
       - второй ответ пришёл из кэша (через признак, который вы добавите,
         например header X-Idempotency-Replayed=true),
       - в order_status_history только одно событие paid,
       - в idempotency_keys есть запись completed с response_body/status_code.
    """
    idempotency_key = "fixed-key-123"
    order_id = str(test_order)
    payload = {"order_id": order_id, "mode": "unsafe"}
    headers = {"Idempotency-Key": idempotency_key}

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp1 = await client.post("/api/payments/retry-demo", json=payload, headers=headers)
        assert resp1.status_code == 200, f"First call failed: {resp1.text}"
        original_body = resp1.json()

        resp2 = await client.post("/api/payments/retry-demo", json=payload, headers=headers)
        assert resp2.status_code == 200, "Second call should succeed"
        assert resp2.headers.get("X-Idempotency-Replayed") == "true", \
            "Повторный ответ должен содержать X-Idempotency-Replayed: true"
        assert resp2.json() == original_body, "Кэшированный ответ должен быть идентичен оригинальному"

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM order_status_history WHERE order_id = :oid AND status = 'paid'"),
        {"oid": test_order},
    )
    paid_count = result.scalar()
    assert paid_count == 1, f"Должна быть ровно одна запись 'paid', получено {paid_count}"

    result = await db_session.execute(
        text(
            "SELECT status, response_body, status_code FROM idempotency_keys "
            "WHERE idempotency_key = :key AND request_method = 'POST' "
            "AND request_path = '/api/payments/retry-demo'"
        ),
        {"key": idempotency_key},
    )
    row = result.fetchone()
    assert row is not None, "Запись об идемпотентном ключе должна существовать"
    status, response_body, status_code = row
    assert status == "completed", f"Статус должен быть 'completed', а не '{status}'"
    assert status_code == 200
    saved_body = json.loads(response_body) if isinstance(response_body, str) else response_body
    assert saved_body == original_body, "Сохранённое тело ответа не совпадает"

    await db_session.execute(
        text("DELETE FROM idempotency_keys WHERE idempotency_key = :key"),
        {"key": idempotency_key},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_same_key_different_payload_returns_conflict(db_session, test_order):
    """
    TODO: Реализовать негативный тест.

    Один и тот же Idempotency-Key нельзя использовать с другим payload.
    Ожидается 409 Conflict (или эквивалентная бизнес-ошибка).
    """
    user_id2 = uuid.uuid4()
    order_id2 = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO users (id, email, name, created_at) VALUES (:id, 'conflict@test.com', 'Conflict User', NOW())"),
        {"id": user_id2},
    )
    await db_session.execute(
        text(
            "INSERT INTO orders (id, user_id, created_at, status, total_amount) "
            "VALUES (:id, :user_id, NOW(), 'created', 500)"
        ),
        {"id": order_id2, "user_id": user_id2},
    )
    await db_session.execute(
        text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (:id, :order_id, 'created', NOW())"),
        {"id": uuid.uuid4(), "order_id": order_id2},
    )
    await db_session.commit()

    idempotency_key = "conflict-key-789"
    headers = {"Idempotency-Key": idempotency_key}

    async with AsyncClient(app=app, base_url="http://test") as client:
        payload1 = {"order_id": str(test_order), "mode": "unsafe"}
        resp1 = await client.post("/api/payments/retry-demo", json=payload1, headers=headers)
        assert resp1.status_code == 200, f"First call failed: {resp1.text}"

        payload2 = {"order_id": str(order_id2), "mode": "unsafe"}
        resp2 = await client.post("/api/payments/retry-demo", json=payload2, headers=headers)
        assert resp2.status_code == 409, (
            f"Expected 409 Conflict for different payload, got {resp2.status_code}: {resp2.text}"
        )
        error_data = resp2.json()
        assert "Idempotency-Key conflict" in error_data.get("error", ""), "response has to something"

    await db_session.execute(
        text("DELETE FROM idempotency_keys WHERE idempotency_key = :key"),
        {"key": idempotency_key},
    )
    await db_session.execute(
        text("DELETE FROM order_status_history WHERE order_id = :oid"), {"oid": order_id2}
    )
    await db_session.execute(
        text("DELETE FROM orders WHERE id = :oid"), {"oid": order_id2}
    )
    await db_session.execute(
        text("DELETE FROM users WHERE id = :uid"), {"uid": user_id2}
    )
    await db_session.commit()