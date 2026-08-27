from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette._utils import get_route_path
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.auth.dependencies import validate_required_proxy_api_key_authorization
from app.core.clients.proxy import (
    CODEX_LB_REQUIRED_CAPABILITY_HEADER,
    CODEX_LB_USAGE_TAG_CAPABILITY,
    CODEX_LB_USAGE_TAG_ERROR_MESSAGE,
    CODEX_LB_USAGE_TAG_HEADER,
    is_valid_codex_lb_usage_tag,
)
from app.core.errors import openai_error
from app.core.exceptions import ProxyAuthError, ProxyRequiredCapabilityTransportError
from app.core.runtime_logging import log_error_response
from app.modules.proxy.images_observability import (
    IMAGE_ROUTE_STARTED_AT_STATE,
    record_images_route_observability,
)

logger = logging.getLogger(__name__)

_REQUIRED_CAPABILITY_HEADER_BYTES = CODEX_LB_REQUIRED_CAPABILITY_HEADER.lower().encode("latin-1")
_USAGE_TAG_HEADER_BYTES = CODEX_LB_USAGE_TAG_HEADER.lower().encode("latin-1")

_JSON_BODY_DENY_PATHS = frozenset(
    {
        "/backend-api/codex/responses",
        "/backend-api/codex/responses/compact",
        "/backend-api/codex/images/generations",
        "/v1/responses",
        "/v1/responses/compact",
        "/v1/chat/completions",
        "/v1/embeddings",
        "/v1/images/generations",
        "/v1/reset-credit",
        "/v1/warmup",
        "/api/codex/rate-limit-reset-credits/consume",
    }
)


def _is_pre_body_deny_path(path: str) -> bool:
    normalized = path.rstrip("/")
    return normalized in _JSON_BODY_DENY_PATHS or normalized.startswith("/v1/warmup/")


def _required_capability_values(scope: Scope) -> tuple[str, ...]:
    return tuple(
        value.decode("latin-1")
        for name, value in scope.get("headers", [])
        if name.lower() == _REQUIRED_CAPABILITY_HEADER_BYTES
    )


def _usage_tag_values(scope: Scope) -> tuple[str, ...]:
    return tuple(
        value.decode("latin-1") for name, value in scope.get("headers", []) if name.lower() == _USAGE_TAG_HEADER_BYTES
    )


class RequiredCapabilityHttpMiddleware:
    """Negotiate every capability-marked HTTP request before routing or body reads.

    Pure ASGI with cheap synchronous guards first; the ``Request`` object is
    only constructed on the cold deny path.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and (usage_tag_values := _usage_tag_values(scope))
            and (len(usage_tag_values) != 1 or not is_valid_codex_lb_usage_tag(usage_tag_values[0]))
        ):
            request = Request(scope)
            response = _invalid_usage_tag_response(request)
            await response(scope, receive, send)
            return
        if (
            scope["type"] != "http"
            or not (capability_values := _required_capability_values(scope))
            or (
                CODEX_LB_USAGE_TAG_CAPABILITY not in capability_values
                and not (scope["method"] == "POST" and _is_pre_body_deny_path(get_route_path(scope)))
            )
        ):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        try:
            await validate_required_proxy_api_key_authorization(request.headers.get("authorization"))
        except ProxyAuthError as exc:
            response = _capability_error_response(request, exc)
        else:
            if capability_values == (CODEX_LB_USAGE_TAG_CAPABILITY,):
                await self.app(scope, receive, send)
                return
            response = _capability_error_response(request, ProxyRequiredCapabilityTransportError())
        await response(scope, receive, send)


def add_required_capability_http_middleware(app: FastAPI) -> None:
    app.add_middleware(RequiredCapabilityHttpMiddleware)


def _capability_error_response(
    request: Request,
    exc: ProxyAuthError | ProxyRequiredCapabilityTransportError,
) -> JSONResponse:
    log_error_response(
        logger,
        request,
        exc.status_code,
        exc.code,
        exc.message,
        category="openai_error_response",
    )
    path = get_route_path(request.scope)
    if path.rstrip("/").endswith("/images/generations"):
        started_at = getattr(request.state, IMAGE_ROUTE_STARTED_AT_STATE, None)
        if not isinstance(started_at, float):
            started_at = time.perf_counter()
        record_images_route_observability(
            route="generations",
            model=None,
            stream=False,
            status=exc.status_code,
            outcome="auth_error" if isinstance(exc, ProxyAuthError) else "invalid_request",
            started_at=started_at,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=openai_error(exc.code, exc.message, error_type=exc.error_type),
    )


def _invalid_usage_tag_response(request: Request) -> JSONResponse:
    log_error_response(
        logger,
        request,
        400,
        "invalid_usage_tag",
        CODEX_LB_USAGE_TAG_ERROR_MESSAGE,
        category="openai_error_response",
    )
    return JSONResponse(
        status_code=400,
        content=openai_error(
            "invalid_usage_tag",
            CODEX_LB_USAGE_TAG_ERROR_MESSAGE,
            error_type="invalid_request_error",
        ),
    )
