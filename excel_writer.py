# -*- coding: utf-8 -*-
"""导出 Excel。列顺序固定：编号|发布文案|口播文案|发布时间|播放量|点赞量|评论量|转发量|视频链接"""
import os
import datetime
import logging
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

import config

logger = logging.getLogger("excel")

HEADERS = ["编号", "发布文案", "口播文案", "发布时间", "播放量", "点赞量", "评论量", "转发量", "视频链接"]
CST = datetime.timezone(datetime.timedelta(hours=8))


def _fmt_time(unix_ts):
    if not unix_ts:
        return ""
    try:
        ts = float(unix_ts)
        # 毫秒兜底
        if ts > 1e12:
            ts = ts / 1000.0
        dt = datetime.datetime.fromtimestamp(ts, tz=CST)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(unix_ts)


def write_excel(rows: list, output_path: str) -> str:
    """rows: list of dict，每个含 index/desc/transcript/create_time/play/digg/comment/share/url/error。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "视频分析"

    bold = Font(bold=True)
    ws.append(HEADERS)
    for c in ws[1]:
        c.font = bold
        c.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        transcript = r.get("transcript") or ""
        if r.get("error"):
            transcript = f"[失败] {r['error']}"
        ws.append([
            r.get("index", ""),
            r.get("desc", ""),
            transcript,
            _fmt_time(r.get("create_time")),
            r.get("play_count", 0) or 0,
            r.get("digg_count", 0) or 0,
            r.get("comment_count", 0) or 0,
            r.get("share_count", 0) or 0,
            r.get("video_url", ""),
        ])

    # 列宽
    widths = [6, 40, 60, 18, 10, 10, 10, 10, 36]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    wb.save(output_path)
    return output_path
