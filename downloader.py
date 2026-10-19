# -*- coding: utf-8 -*-
"""无水印视频下载。优先用解析出的播放 URL 自行下载，失败回退到 download_addr。"""
import asyncio
import os
import logging
import aiohttp

import config

logger = logging.getLogger("downloader")


async def download_one(url: str, dest_path: str, cookie: str = "") -> bool:
    """下载单个视频到 dest_path。成功返回 True。"""
    if not url:
        return False
    headers = {
        "User-Agent": config.HEADERS_UA,
        "Referer": config.REFERER,
    }
    if cookie:
        headers["Cookie"] = cookie
    try:
        timeout = aiohttp.ClientTimeout(total=config.DOWNLOAD_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning("download http %s for %s", resp.status, url[:80])
                    return False
                tmp = dest_path + ".tmp"
                with open(tmp, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1 << 16):
                        if chunk:
                            f.write(chunk)
                # 校验文件大小，抖音视频至少几十 KB
                if os.path.getsize(tmp) < 10240:
                    os.remove(tmp)
                    return False
                os.replace(tmp, dest_path)
                return True
    except Exception as e:
        logger.warning("download failed: %s", e)
        if os.path.exists(dest_path + ".tmp"):
            try:
                os.remove(dest_path + ".tmp")
            except OSError:
                pass
        return False


async def download_video(entry: dict, index: int, cookie: str = "") -> str:
    """entry 是 scraper 解析后的 dict。下载为 0NN.mp4，返回文件路径或抛异常。"""
    fname = f"{index:03d}.mp4"
    dest = os.path.join(config.DOWNLOAD_DIR, fname)
    if os.path.exists(dest) and os.path.getsize(dest) > 10240:
        return dest

    # 先试播放地址，再试下载地址
    for url in (entry.get("play_url"), entry.get("download_url")):
        if not url:
            continue
        ok = await download_one(url, dest, cookie)
        if ok:
            return dest
    raise RuntimeError("所有候选下载地址均失败")
