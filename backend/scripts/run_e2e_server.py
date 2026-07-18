"""E2E专用Uvicorn协作式生命周期wrapper。"""

import asyncio
import os
import sys
import threading
from pathlib import Path

import uvicorn

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


async def read_shutdown_command() -> str:
    """用daemon线程读取stdin，避免阻塞asyncio及进程退出。"""
    loop = asyncio.get_running_loop()
    result = loop.create_future()

    def read_line() -> None:
        line = sys.stdin.readline()
        loop.call_soon_threadsafe(result.set_result, line.strip())

    threading.Thread(target=read_line, name="e2e-shutdown-reader", daemon=True).start()
    return await result


async def run() -> int:
    port = int(os.getenv("E2E_BACKEND_PORT", "8002"))
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    command_task = asyncio.create_task(read_shutdown_command())

    done, _ = await asyncio.wait(
        {serve_task, command_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if serve_task in done:
        command_task.cancel()
        await serve_task
        return 0

    command = await command_task
    exit_codes = {
        "shutdown": 0,
        "signal:SIGINT": 130,
        "signal:SIGTERM": 143,
    }
    if command not in exit_codes:
        server.should_exit = True
        await asyncio.wait_for(serve_task, timeout=15)
        raise RuntimeError(f"Uvicorn E2E wrapper收到无效关闭命令: {command or 'stdin_closed'}")

    server.should_exit = True
    await asyncio.wait_for(serve_task, timeout=15)
    return exit_codes[command]


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    except Exception as exc:
        print(f"[E2E Uvicorn wrapper] {exc}", file=sys.stderr)
        raise SystemExit(1)
