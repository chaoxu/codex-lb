from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--capture-file", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--upstream-port", required=True, type=int)
    return parser.parse_args()


args = _arguments()
database_url = f"sqlite+aiosqlite:///{Path(args.database).resolve()}"
os.environ["CODEX_LB_DATABASE_URL"] = database_url
os.environ["CODEX_LB_UPSTREAM_BASE_URL"] = f"http://127.0.0.1:{args.upstream_port}/backend-api"
os.environ["CODEX_LB_USAGE_REFRESH_ENABLED"] = "false"
os.environ["CODEX_LB_MODEL_REGISTRY_ENABLED"] = "false"
os.environ["CODEX_LB_STICKY_SESSION_CLEANUP_ENABLED"] = "false"
os.environ["CODEX_LB_HTTP_RESPONSES_SESSION_BRIDGE_ENABLED"] = "false"
os.environ["CODEX_LB_QUOTA_PLANNER_SCHEDULER_ENABLED"] = "false"
os.environ["CODEX_LB_AUTOMATIONS_SCHEDULER_ENABLED"] = "false"

from app.core.crypto import TokenEncryptor  # noqa: E402
from app.core.utils.time import utcnow  # noqa: E402
from app.db.migrate import run_upgrade  # noqa: E402
from app.db.models import Account, AccountStatus, DashboardSettings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.api_keys.repository import ApiKeysRepository  # noqa: E402
from app.modules.api_keys.service import ApiKeyCreateData, ApiKeysService  # noqa: E402


async def _seed() -> None:
    encryptor = TokenEncryptor()
    async with SessionLocal() as session:
        settings = await session.get(DashboardSettings, 1)
        if settings is None:
            raise RuntimeError("dashboard settings were not seeded")
        settings.api_key_auth_enabled = True
        session.add(
            Account(
                id="usage-tag-e2e-account",
                email="usage-tag-e2e@example.invalid",
                plan_type="plus",
                chatgpt_account_id="usage-tag-e2e-upstream",
                access_token_encrypted=encryptor.encrypt("local-upstream-token"),
                refresh_token_encrypted=encryptor.encrypt("local-refresh-token"),
                id_token_encrypted=encryptor.encrypt("local-id-token"),
                last_refresh=utcnow(),
                status=AccountStatus.ACTIVE,
                deactivation_reason=None,
            )
        )
        await session.commit()
        created = await ApiKeysService(ApiKeysRepository(session)).create_key(
            ApiKeyCreateData(
                name="usage-tag-e2e-stable-key",
                allowed_models=None,
                expires_at=None,
            )
        )
    key_path = Path(args.key_file)
    key_path.write_text(created.key, encoding="utf-8")
    key_path.chmod(0o600)


capture_path = Path(args.capture_file)
upstream = FastAPI()


@upstream.post("/{path:path}")
async def fake_upstream(request: Request, path: str) -> StreamingResponse:
    record = {
        "path": path,
        "headers": {key.lower(): value for key, value in request.headers.items()},
    }
    with capture_path.open("a", encoding="utf-8") as output:
        output.write(f"{json.dumps(record, sort_keys=True)}\n")

    async def body():
        yield (
            'data: {"type":"response.completed","response":{"id":"resp_usage_tag_e2e",'
            '"object":"response","status":"completed","output":[{"type":"message","role":"assistant",'
            '"content":[{"type":"output_text","text":"DONE"}]}],"usage":{"input_tokens":21,'
            '"output_tokens":5,"input_tokens_details":{"cached_tokens":7},'
            '"output_tokens_details":{"reasoning_tokens":3},"total_tokens":26}}}\n\n'
        )

    return StreamingResponse(body(), media_type="text/event-stream")


def _run_upstream() -> None:
    uvicorn.run(upstream, host="127.0.0.1", port=args.upstream_port, log_level="warning")


run_upgrade(database_url, "head", bootstrap_legacy=False)
asyncio.run(_seed())
capture_path.touch(mode=0o600, exist_ok=True)
threading.Thread(target=_run_upstream, daemon=True).start()
uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
