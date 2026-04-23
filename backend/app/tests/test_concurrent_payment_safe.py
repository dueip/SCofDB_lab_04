"""
Тест для демонстрации РЕШЕНИЯ проблемы race condition.

Этот тест должен ПРОХОДИТЬ, подтверждая, что при использовании
pay_order_safe() заказ оплачивается только один раз.
"""

import asyncio
import pytest
from sqlalchemy import text
import uuid
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.application.payment_service import PaymentService
from app.domain.exceptions import OrderAlreadyPaidError


# TODO: Настроить подключение к тестовой БД
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/marketplace"


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

@pytest.fixture
async def first_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание тестового заказа
    user_id= uuid.uuid4()
    user_query = text("""
        INSERT INTO users (id, email, name, created_at)
        VALUES (:id, 'meow_1@meow.meow', 'Meow User 1', NOW())
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

@pytest.fixture
async def second_order(db_session):
    """
    Создать тестовый заказ со статусом 'created'.
    
    TODO: Реализовать фикстуру (см. test_concurrent_payment_unsafe.py)
    """
    # TODO: Реализовать создание тестового заказа
    user_id= uuid.uuid4()
    user_query = text("""
        INSERT INTO users (id, email, name, created_at)
        VALUES (:id, 'meow2@meow.meow', 'Meow User2', NOW())
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
async def test_concurrent_payment_safe_prevents_race_condition(db_session, test_order):
    """
    Тест демонстрирует решение проблемы race condition с помощью pay_order_safe().
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: Тест ПРОХОДИТ, подтверждая, что заказ был оплачен только один раз.
    Это показывает, что метод pay_order_safe() защищен от конкурентных запросов.
    
    TODO: Реализовать тест следующим образом:
    
    1. Создать два экземпляра PaymentService с РАЗНЫМИ сессиями
       (это имитирует два независимых HTTP-запроса)
       
    2. Запустить два параллельных вызова pay_order_safe():
       
       async def payment_attempt_1():
           service1 = PaymentService(session1)
           return await service1.pay_order_safe(order_id)
           
       async def payment_attempt_2():
           service2 = PaymentService(session2)
           return await service2.pay_order_safe(order_id)
           
       results = await asyncio.gather(
           payment_attempt_1(),
           payment_attempt_2(),
           return_exceptions=True
       )
       
    3. Проверить результаты:
       - Одна попытка должна УСПЕШНО завершиться
       - Вторая попытка должна выбросить OrderAlreadyPaidError ИЛИ вернуть ошибку
       
       success_count = sum(1 for r in results if not isinstance(r, Exception))
       error_count = sum(1 for r in results if isinstance(r, Exception))
       
       assert success_count == 1, "Ожидалась одна успешная оплата"
       assert error_count == 1, "Ожидалась одна неудачная попытка"
       
    4. Проверить историю оплат:
       
       service = PaymentService(session)
       history = await service.get_payment_history(order_id)
       
       # ОЖИДАЕМ ОДНУ ЗАПИСЬ 'paid' - проблема решена!
       assert len(history) == 1, "Ожидалась 1 запись об оплате (БЕЗ RACE CONDITION!)"
       
    5. Вывести информацию об успешном решении:
       
       print(f"✅ RACE CONDITION PREVENTED!")
       print(f"Order {order_id} was paid only ONCE:")
       print(f"  - {history[0]['changed_at']}: status = {history[0]['status']}")
       print(f"Second attempt was rejected: {results[1]}")
    """
    # TODO: Реализовать тест, демонстрирующий решение race condition
    order_id = test_order
    engine = create_async_engine(DATABASE_URL)

    async def payment_attempt_1():
        async with AsyncSession(engine) as session1:
            service1 = PaymentService(session1)
            return await service1.pay_order_safe(order_id)

    async def payment_attempt_2():
        async with AsyncSession(engine) as session2:
            service2 = PaymentService(session2)
            return await service2.pay_order_safe(order_id)

    results = await asyncio.gather(
        payment_attempt_1(),
        payment_attempt_2(),
        return_exceptions=True
    )
    await asyncio.sleep(0.2)
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    error_count = sum(1 for r in results if isinstance(r, Exception))

    assert success_count == 1, f"Expected 1 successful payment, got {success_count}"
    assert error_count == 1, f"Expected 1 failed payment, got {error_count}"

    service = PaymentService(db_session)
    history = await service.get_payment_history(order_id)
    assert len(history) == 1, f"Expected 1 payment record, found {len(history)}"

    print(f"\n✅ RACE CONDITION PREVENTED!")
    print(f"Order {order_id} was paid only ONCE:")
    for rec in history:
        print(f"  - {rec['changed_at']}: status = {rec['status']}")
    print(f"Second attempt was rejected: {results[1]}")

    await engine.dispose()

@pytest.mark.asyncio
async def test_concurrent_payment_safe_with_explicit_timing(db_session, test_order):
    """
    Дополнительный тест: проверить работу блокировок с явной задержкой.
    
    TODO: Реализовать тест с добавлением задержки в первой транзакции:
    
    1. Первая транзакция:
       - Начать транзакцию
       - Заблокировать заказ (FOR UPDATE)
       - Добавить задержку (asyncio.sleep(1))
       - Оплатить
       - Commit
       
    2. Вторая транзакция (запустить через 0.1 секунды после первой):
       - Начать транзакцию
       - Попытаться заблокировать заказ (FOR UPDATE)
       - ДОЛЖНА ЖДАТЬ освобождения блокировки от первой транзакции
       - После освобождения - увидеть обновленный статус 'paid'
       - Выбросить OrderAlreadyPaidError
       
    3. Проверить временные метки:
       - Вторая транзакция должна завершиться ПОЗЖЕ первой
       - Разница должна быть >= 1 секунды (время задержки)
       
    Это подтверждает, что FOR UPDATE действительно блокирует строку.
    """
    # TODO: Реализовать тест с проверкой блокировки
    order_id = test_order
    engine = create_async_engine(DATABASE_URL, echo=False)

    start_time = time.perf_counter()
    async def payment_attempt1():
        async with AsyncSession(engine) as session1:
            await session1.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            await session1.execute(text("SELECT status FROM orders WHERE id = :order_id FOR UPDATE"), {"order_id": order_id})
            await asyncio.sleep(1)

            await session1.execute(text("UPDATE orders SET status = 'paid' WHERE id = :order_id AND status = 'created'"), {"order_id": order_id})
            await session1.execute(text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (:id, :order_id, 'paid', NOW())"), {"id": uuid.uuid4(), "order_id": order_id})
            await session1.commit()
            return {"status": "paid", "attempt": "1"}

    async def payment_attempt2():
        await asyncio.sleep(0.1)
        async with AsyncSession(engine) as session2:
            await session2.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            await session2.execute(text("SELECT status FROM orders WHERE id = :order_id FOR UPDATE"), {"order_id": order_id})

            await session2.execute(text("UPDATE orders SET status = 'paid' WHERE id = :order_id AND status = 'created'"), {"order_id": order_id})
            await session2.execute(text("INSERT INTO order_status_history (id, order_id, status, changed_at) VALUES (:id, :order_id, 'paid', NOW())"), {"id": uuid.uuid4(), "order_id": order_id})
            await session2.commit()
            return {"status": "paid", "attempt": "2"}

    results = await asyncio.gather(
        payment_attempt1(),
        payment_attempt2(),
        return_exceptions=True
    )
    await engine.dispose()

    end_time = time.perf_counter()
    elapsed = end_time - start_time

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}"

    assert elapsed >= 1.0, f"Expected blocking delay >= 1.0s, got {elapsed:.2f}s"

    await db_session.rollback()
    service = PaymentService(db_session)
    history = await service.get_payment_history(order_id)
    assert len(history) == 1

    print(f"Total elapsed time: {elapsed:.2f}s")
    print(f"Order {order_id} has onlye been paid once.")

    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_payment_safe_multiple_orders(db_session, first_order, second_order):
    """
    Дополнительный тест: проверить, что блокировки не мешают разным заказам.
    
    TODO: Реализовать тест:
    1. Создать ДВА разных заказа
    2. Оплатить их ПАРАЛЛЕЛЬНО с помощью pay_order_safe()
    3. Проверить, что ОБА успешно оплачены
    
    Это показывает, что FOR UPDATE блокирует только конкретную строку,
    а не всю таблицу, что важно для производительности.
    """
    # TODO: Реализовать тест с несколькими заказами
    # I wish python had macros and I could actually write these things way faster. Too bad! 
    engine = create_async_engine(DATABASE_URL)
    async def payment_attemp1():
        async with AsyncSession(engine) as session1:
            service = PaymentService(session1)
            return await service.pay_order_safe(first_order)
    
    async def payment_attemp2():
        async with AsyncSession(engine) as session2:
            service = PaymentService(session2)
            return await service.pay_order_safe(second_order)
        
    results = await asyncio.gather(payment_attemp1(), payment_attemp2(), return_exceptions=True)

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    await engine.dispose()

    assert len(successes) == 2, f"Expected 1 success, got {len(successes)}"
    assert len(failures) == 0, f"Expected 1 failure, got {len(failures)}"


if __name__ == "__main__":
    """
    Запуск теста:
    
    cd backend
    export PYTHONPATH=$(pwd)
    pytest app/tests/test_concurrent_payment_safe.py -v -s
    
    ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
    ✅ test_concurrent_payment_safe_prevents_race_condition PASSED
    
    Вывод должен показывать:
    ✅ RACE CONDITION PREVENTED!
    Order XXX was paid only ONCE:
      - 2024-XX-XX: status = paid
    Second attempt was rejected: OrderAlreadyPaidError(...)
    """
    pytest.main([__file__, "-v", "-s"])
