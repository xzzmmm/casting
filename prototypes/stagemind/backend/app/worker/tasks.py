"""后台任务入口：当前为进程内线程，后续可替换为 ARQ / Celery。"""

from __future__ import annotations

import threading

from app.services.pipeline import process_rehearsal


def enqueue(rehearsal_id: int) -> None:
    """把排练处理任务放入后台执行，接口保持稳定以支持后续换队列。"""
    thread = threading.Thread(
        target=process_rehearsal, args=(rehearsal_id,), daemon=True
    )
    thread.start()
