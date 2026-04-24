# Отчёт по лабораторной работе №4
## Идемпотентность платежных запросов в FastAPI

**Студент:** _[Воеводин Егор Олегович]_  
**Группа:** _[БПМ-22-ПО-3]_  
**Дата:** _[23.04.26]_

## 1. Постановка сценария
Данный сценарий сходится со сценарием 2 лабораторной работы

1) Пользователь открывает страницу с оплатой
2) Он нажимае на кнопочку и отправляет запрос, однако, по какой-то причине, у него пропадает связь и пользователь не получает ответа от сервера
3) Он, естественно, отправляет заказ повторно
5) Если на бд не настроена блокировка на повторную оплату, то пользователь и два раза оплатит. А может и три. А может и больше, зависит от того как его сеть поведет :(

## 2. Реализация таблицы idempotency_keys
```
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key VARCHAR(255) NOT NULL,
    request_method VARCHAR(16) NOT NULL,
    request_path TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'processing',
    status_code INTEGER,
    response_body JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    CONSTRAINT idempotency_status_check CHECK (status IN ('processing', 'completed', 'failed')),
    CONSTRAINT key_endpoint_unique_check UNIQUE (idempotency_key, request_method, request_path)
);
```
- idempotency_key -- уникальный ключа запроса
- request_method -- метод запроса
- request_path -- путь до апи
- request_hash -- хеш тела запроса
- status -- в каком статусе сейчас обраотка задачи находится
- status_code -- код статуса для маппинга
Ограничения:
- idempotency_status_check -- подтверждает, что status - это енумка.
-  key_endpoint_unique_check -- проверяет, что три поля обязательно уникальны

## 3. Реализация middleware

Минимум:
1. Чтение `Idempotency-Key`.
2. Проверка существующей записи.
3. Обработка кейса \"тот же key + другой payload\".
4. Сохранение результата первого запроса.
5. Возврат кэшированного ответа при повторе.

## 4. Демонстрация без защиты
_TODO: Приведите результаты сценария без идемпотентности._
- Запустили тест `docker compose exec -T backend pytest app/tests/test_retry_without_idempotency.py -v -s`
- Получили лог о том, что `❌ ПРОБЛЕМА: Двойная оплата!`

## 5. Демонстрация с Idempotency-Key
- Запустили тест с помощтю `docker compose exec -T backend pytest app/tests/test_retry_with_idempotency_key.py -v -s`
- Первый ответ `{"success": true, "message": "Retry demo payment succeeded (unsafe)",
 "order_id": "196f1d38-14dc-4a50-82a3-d92848e5f2ec", "status": "paid"}`
- Повторный ответ `{"success": true, "message": "Retry demo payment succeeded (unsafe)",
 "order_id": "196f1d38-14dc-4a50-82a3-d92848e5f2ec", "status": "paid"}`
- Признак кеширования `[cached since 0.02235s ago]` -- SQLAlchemy не делало больше никаких транзакций после получения повторного запроса


## 6. Негативный сценарий
В тестах есть `assert resp2.status_code == 409, (
            f"Expected 409 Conflict for different payload, got {resp2.status_code}: {resp2.text}"
        )`. Т.к. все тесты проходят верно, то resp2.status code точно равен 409

## 7. Сравнение с решением из ЛР2 (FOR UPDATE)
_TODO: Сравните подходы по сути и по UX._
1) Idempotency Key -- Существует для обеспечения кеширования, а также защиты сервера от повторных запросов. При повторе запроса возвращается кешированный ответ. Гарания обеспечивается на уровне API
2) FOR UPDATE -- Существует для защиты от race condition'ов. При повторе запроса вопрос будет ждать освобождения блокировки первого запроса. Выполняется на уровне БД. 
Оба механизма стоит использовать вместе, они не являются взаимоисключающими, а комплиментарными. Как проверка на ввод со стороны API все равно должна проводиться на БД из-за критичности.
## 8. Выводы
1) Idempotency Key представляет собой очень удобный механизм для обеспечения безопасности работы с критическими запросами
2) Благодаря кешированию данных и у сервера оказывается меньше оверхеда, и у пользователя
