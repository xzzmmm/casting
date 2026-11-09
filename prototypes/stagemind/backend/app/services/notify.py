"""提醒通知服务：排练日期变更时通知全体（飞书群机器人 webhook）。"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.config import settings
from app.models import Rehearsal

logger = logging.getLogger(__name__)


def send_date_change_notice(
    rehearsal: Rehearsal, old_date: datetime, new_date: datetime
) -> None:
    """排练日期变更时向配置的飞书群机器人发送提醒。

    未配置 STAGEMIND_WEBHOOK_URL 或发送失败时只记录日志，不中断主流程。
    """
    webhook = settings.reminder_webhook_url
    if not webhook:
        logger.info(
            "排练日期变更未发送提醒（未配置 STAGEMIND_WEBHOOK_URL）："
            "%s 第 %s 次 %s -> %s",
            rehearsal.play,
            rehearsal.rehearsal_no,
            old_date.strftime("%Y-%m-%d"),
            new_date.strftime("%Y-%m-%d"),
        )
        return

    message = (
        f"【StageMind】《{rehearsal.play}》第 {rehearsal.rehearsal_no} 次排练"
        f"日期由 {old_date.strftime('%Y-%m-%d')} 改为 {new_date.strftime('%Y-%m-%d')}，"
        "请相关人员留意并调整安排。"
    )
    payload = {"msg_type": "text", "content": {"text": message}}
    try:
        response = httpx.post(webhook, json=payload, timeout=10.0)
        response.raise_for_status()
        logger.info("日期变更提醒已发送：%s", message)
    except httpx.HTTPError as exc:
        logger.warning("日期变更提醒发送失败：%s", exc)
