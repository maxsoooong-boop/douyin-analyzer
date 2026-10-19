# -*- coding: utf-8 -*-
"""FastAPI 主入口：接收主页链接，跑 爬取->下载->转写->导出Excel 全流程。"""
import asyncio
import os
import uuid
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import scraper
import downloader
import excel_writer
from login_manager import login_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("main")

app = FastAPI(title="抖音主页视频批量分析工具")

TASKS: Dict[str, Dict[str, Any]] = {}


@app.post("/api/login/start")
async def start_login():
    """弹出 Chrome 窗口让用户扫码登录抖音。"""
    login_manager.start_login()
    return {"ok": True, "msg": "登录窗口已弹出，请在弹出的 Chrome 窗口里扫码登录"}


@app.get("/api/login/status")
async def login_status():
    """查询登录状态。"""
    s = login_manager.get_status()
    return {"ok": True, **s}


class AnalyzeReq(BaseModel):
    url: str
    cookie: str = ""
    max_videos: Optional[int] = None


def _new_task(url: str) -> str:
    tid = uuid.uuid4().hex[:12]
    TASKS[tid] = {
        "status": "pending",       # pending / crawling / downloading / transcribing / done / failed
        "message": "排队中",
        "done": 0,
        "total": 0,
        "current": "",
        "error": "",
        "excel": "",
        "url": url,
    }
    return tid


async def run_pipeline(tid: str, url: str, cookie: str, max_videos: Optional[int]):
    t = TASKS[tid]
    loop = asyncio.get_event_loop()
    try:
        # 如果用户没手动填 Cookie，自动用刚才扫码登录的 Cookie
        if not cookie:
            auto_cookie = login_manager.get_cookie()
            if auto_cookie:
                cookie = auto_cookie
                logger.info("自动使用扫码登录的 Cookie")
            else:
                logger.warning("未提供 Cookie，也没有登录态，可能会 403")

        # 1. 爬取
        t["status"] = "crawling"
        t["message"] = "正在爬取主页作品列表…"

        def on_crawl_done(done, _):
            t["done"] = done
            t["total"] = done
            t["message"] = f"已发现 {done} 个作品"

        entries = await scraper.fetch_all_videos(url, cookie=cookie, max_counts=max_videos, on_progress=on_crawl_done)
        t["total"] = len(entries)
        t["done"] = 0
        if not entries:
            raise RuntimeError("未爬到任何作品，请检查链接/Cookie，或该账号作品为私密/仅好友可见")

        rows = []
        # 2. 下载 + 转写（逐个串行，避免被风控）
        for i, entry in enumerate(entries, start=1):
            t["status"] = "downloading"
            t["current"] = f"第 {i}/{t['total']} 个"
            t["message"] = f"正在下载第 {i}/{t['total']} 个视频…"
            t["done"] = i - 1

            row = {
                "index": i,
                "desc": entry.get("desc", ""),
                "create_time": entry.get("create_time"),
                "play_count": entry.get("play_count"),
                "digg_count": entry.get("digg_count"),
                "comment_count": entry.get("comment_count"),
                "share_count": entry.get("share_count"),
                "video_url": entry.get("video_url", ""),
                "transcript": "",
                "error": "",
            }

            video_path = None
            try:
                video_path = await downloader.download_video(entry, i, cookie=cookie)
            except Exception as e:
                row["error"] = f"下载失败: {e}"
                rows.append(row)
                continue

            # 3. 转写（CPU 较慢，放线程池）
            t["status"] = "transcribing"
            t["message"] = f"正在转写第 {i}/{t['total']} 个视频（这一步较慢，请耐心等待）…"
            try:
                transcript = await loop.run_in_executor(None, asr_transcribe, video_path)
                row["transcript"] = transcript
            except Exception as e:
                row["error"] = f"转写失败: {e}"

            rows.append(row)

        t["done"] = t["total"]

        # 4. 导出 Excel
        t["status"] = "exporting"
        t["message"] = "正在导出 Excel…"
        out_name = f"douyin_analysis_{tid}.xlsx"
        out_path = os.path.join(config.OUTPUT_DIR, out_name)
        excel_writer.write_excel(rows, out_path)

        t["status"] = "done"
        t["message"] = f"完成！共处理 {len(rows)} 个视频"
        t["excel"] = out_path
    except Exception as e:
        logger.exception("pipeline failed")
        t["status"] = "failed"
        t["error"] = str(e)
        t["message"] = f"失败: {e}"


def asr_transcribe(video_path: str) -> str:
    from asr import transcribe
    return transcribe(video_path)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(config.BASE_DIR, "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/analyze")
async def analyze(req: AnalyzeReq):
    if not req.url.strip():
        return {"ok": False, "msg": "请填写主页链接"}
    tid = _new_task(req.url.strip())
    asyncio.create_task(run_pipeline(tid, req.url.strip(), req.cookie or "", req.max_videos))
    return {"ok": True, "task_id": tid}


@app.get("/api/status/{tid}")
async def status(tid: str):
    t = TASKS.get(tid)
    if not t:
        return {"ok": False, "msg": "task not found"}
    return {
        "ok": True,
        "status": t["status"],
        "message": t["message"],
        "done": t["done"],
        "total": t["total"],
        "current": t["current"],
        "error": t["error"],
        "has_excel": bool(t["excel"]),
    }


@app.get("/api/result/{tid}")
async def result(tid: str):
    t = TASKS.get(tid)
    if not t or not t["excel"] or not os.path.exists(t["excel"]):
        return {"ok": False, "msg": "结果尚未生成"}
    return FileResponse(
        t["excel"],
        filename=os.path.basename(t["excel"]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
