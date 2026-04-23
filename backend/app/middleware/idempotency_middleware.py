"""Idempotency middleware template for LAB 04."""

import hashlib
import json
from typing import Callable, List
from sqlalchemy import text
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import timedelta, datetime

from app.infrastructure.db import SessionLocal, get_db


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware для идемпотентности POST-запросов оплаты.

    Идея:
    - Клиент отправляет `Idempotency-Key` в header.
    - Если запрос с таким ключом уже выполнялся для того же endpoint и payload,
      middleware возвращает кэшированный ответ (без повторного списания).
    """

    def __init__(self, app, ttl_seconds: int = 24 * 60 * 60):
        super().__init__(app)
        self.ttl_seconds = ttl_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        TODO: Реализовать алгоритм.

        Рекомендуемая логика:
        1) Пропускать только целевые запросы:
           - method == POST
           - path в whitelist для платежей
        2) Читать Idempotency-Key из headers.
           Если ключа нет -> обычный call_next(request)
        3) Считать request_hash (например sha256 от body).
        4) В транзакции:
           - проверить запись в idempotency_keys
           - если completed и hash совпадает -> вернуть кэш (status_code + body)
           - если key есть, но hash другой -> вернуть 409 Conflict
           - если ключа нет -> создать запись processing
        5) Выполнить downstream request через call_next.
        6) Сохранить response в idempotency_keys со статусом completed.
        7) Вернуть response клиенту.

        Дополнительно:
        - обработайте кейс конкурентных одинаковых ключей
          (уникальный индекс + retry/select existing).
        """

        # Текущая заглушка: middleware ничего не меняет.
        # TODO: заменить на полноценную реализацию с БД.
        if request.method != "POST":
            return await call_next(request)
        
        if request.url.path not in self.get_whitelist():
            return await call_next(request)
        
        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)
        
        hash = self.build_request_hash(await request.body())
        async with SessionLocal() as session:
            try:
                result = await session.execute(
                    text("""
                    SELECT status, request_hash, status_code, response_body
                    FROM idempotency_keys
                    WHERE idempotency_key = :key
                    AND request_method = :method
                    AND request_path = :path
                    FOR UPDATE
                    """),
                    {
                        "key": key,
                        "method": request.method,
                        "path": request.url.path,
                    },
                )

                row = result.fetchone()

                if row:
                    status, stored_hash, status_code, response_body = row

                    if stored_hash != hash:
                        await session.rollback()
                        return Response(
                            content=json.dumps({"error": "Idempotency-Key conflict"}),
                            status_code=409,
                            media_type="application/json",
                        )

                    if status == "completed":
                        await session.commit()
                        return Response(
                            content=json.dumps(response_body) if response_body else "{}",
                            status_code=status_code,
                            headers={"X-Idempotency-Replayed": "true"},
                            media_type="application/json",
                        )

                    if status == "processing":
                        await session.commit()
                        return Response(
                            content=json.dumps({"error": "Is already processing"}),
                            status_code=409,
                            media_type="application/json",
                        )
                else:
                    await session.execute(
                        text("""
                        INSERT INTO idempotency_keys
                        (idempotency_key, request_method, request_path, request_hash, status, expires_at)
                        VALUES (:key, :method, :path, :hash, 'processing', :expires_at)
                        """),
                        {
                            "key": key,
                            "method": request.method,
                            "path": request.url.path,
                            "hash": hash,
                            "expires_at": datetime.now() + timedelta(seconds=self.ttl_seconds)
                        },
                    )
                    await session.commit()

            except Exception:
                await session.rollback()
                return await call_next(request)

        response = await call_next(request)

        try:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            body_json = None
            if response_body:
                try:
                    body_json = json.loads(response_body.decode())
                except:
                    body_json = {"raw": response_body.decode()}

            async with SessionLocal() as update_session:
                await update_session.execute(
                    text("""
                    UPDATE idempotency_keys
                    SET
                        status = 'completed',
                        status_code = :status_code,
                        response_body = CAST(:response_body AS jsonb)
                    WHERE idempotency_key = :key
                    AND request_method = :method
                    AND request_path = :path
                    """),
                    {
                        "status_code": response.status_code,
                        "response_body": json.dumps(body_json) if body_json else None,
                        "key": key,
                        "method": request.method,
                        "path": request.url.path,
                    },
                )
                await update_session.commit()

        except Exception:
            response_body = b""

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    


    @staticmethod
    def build_request_hash(raw_body: bytes) -> str:
        """Стабильный хэш тела запроса для проверки reuse ключа с другим payload."""
        return hashlib.sha256(raw_body).hexdigest()

    @staticmethod
    def encode_response_payload(body_obj) -> str:
        """Сериализация response body для сохранения в idempotency_keys."""
        return json.dumps(body_obj, ensure_ascii=False)
    
    @staticmethod
    def get_whitelist() -> List[str]:
        return ["/api/payments/retry-demo", "/api/payments/pay"]
