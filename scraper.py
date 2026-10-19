# -*- coding: utf-8 -*-
"""用 f2 爬取抖音主页已发布作品，并做健壮的字段解析。

注意：f2 不同版本返回的 dict 字段名会变，本模块对关键字段做多路径兜底，
并把每个作品的原始 dict 落盘到 outputs/_raw_dump.jsonl 便于排查。
"""
import asyncio
import json
import os
import logging
from typing import AsyncIterator, Dict, Any, List, Optional

from f2.apps.douyin.handler import DouyinHandler
from f2.apps.douyin.utils import SecUserIdFetcher

import config

logger = logging.getLogger("scraper")


def _auto_fetch_cookie_from_browser() -> str:
    """自动从系统 Chrome / Edge 浏览器读取 douyin.com 的登录 Cookie。

    用户只需在系统浏览器里登录过抖音一次，后续无需手动复制 Cookie。
    """
    try:
        import browser_cookie3
    except ImportError:
        logger.warning("browser_cookie3 未安装，无法自动读取浏览器 Cookie")
        return ""

    # 按优先级尝试 Chrome → Edge → Firefox
    for browser_name, loader in [
        ("chrome", browser_cookie3.chrome),
        ("edge", browser_cookie3.edge),
        ("firefox", browser_cookie3.firefox),
    ]:
        try:
            cj = loader(domain_name="douyin.com")
            parts = []
            for c in cj:
                if "douyin.com" in c.domain:
                    parts.append(f"{c.name}={c.value}")
            if parts:
                cookie_str = "; ".join(parts)
                logger.info("自动从 %s 读取到抖音 Cookie（%d 个字段）", browser_name, len(parts))
                return cookie_str
        except Exception as e:
            logger.debug("从 %s 读取 Cookie 失败：%s", browser_name, e)
            continue

    logger.warning("未从任何浏览器中读取到抖音 Cookie，请先在系统 Chrome 里登录抖音网页版")
    return ""


def _pick(d: Dict, *keys, default=None):
    """从 dict 里按候选 key 顺序取第一个存在的值。"""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _first_url(url_list) -> Optional[str]:
    if isinstance(url_list, list) and url_list:
        return url_list[0]
    if isinstance(url_list, str):
        return url_list
    return None


def parse_aweme(raw: Dict[str, Any]) -> Dict[str, Any]:
    """把 f2 返回的单条作品原始 dict 解析成统一结构。"""
    # 作品 ID
    aweme_id = _pick(raw, "aweme_id", "awemeId", "group_id", "gid")

    # 文案
    desc = _pick(raw, "desc", "description", default="") or ""

    # 发布时间（unix 秒）
    create_time = _pick(raw, "create_time", "createTime", "create_ts", "createTimeHms")
    if create_time is None:
        # 有些版本放在 video 或 author 里
        create_time = _pick(raw, "create_time_raw")

    # 统计数字：通常在 statistics / stats_cnt / status 子对象
    stats = _pick(raw, "statistics", "stats", "stats_cnt", "status", default={}) or {}
    play_count = _pick(stats, "play_count", "playCount", "playcnt", default=0)
    digg_count = _pick(stats, "digg_count", "diggCount", "diggcnt", "like_count", default=0)
    comment_count = _pick(stats, "comment_count", "commentCount", "comment_count_str", default=0)
    share_count = _pick(stats, "share_count", "shareCount", "sharecnt", "forward_count", default=0)

    # 视频无水印播放地址（f2 0.0.1.7 实测：video.bit_rate[0].play_addr.url_list）
    video = _pick(raw, "video", "aweme_video_info", default={}) or {}
    play_url = ""
    # 1) bit_rate[0].play_addr.url_list（HD 无水印，f2 当前版本主路径）
    bit_rate = video.get("bit_rate") or []
    if isinstance(bit_rate, list):
        for br in bit_rate:
            if not isinstance(br, dict):
                continue
            pa = br.get("play_addr") or {}
            u = _first_url(pa.get("url_list") or pa.get("urlList") or [])
            if u:
                play_url = u
                break
    # 2) video.play_addr.url_list（老版本/兜底）
    if not play_url:
        play_addr = _pick(video, "play_addr", "playAddr", default={}) or {}
        play_url = _first_url(_pick(play_addr, "url_list", "urlList", default=[]))
        if not play_url:
            play_url = _pick(play_addr, "url", default="") or ""
    # 3) video 下直接 url_list
    if not play_url:
        play_url = _first_url(_pick(video, "url_list", "urlList", default=[])) or ""

    download_addr = _pick(video, "download_addr", "downloadAddr", default={}) or {}
    download_url = _first_url(_pick(download_addr, "url_list", "urlList", default=[])) or ""
    if not download_url:
        download_url = _pick(download_addr, "url", default="") or ""

    return {
        "aweme_id": str(aweme_id) if aweme_id else "",
        "desc": desc,
        "create_time": create_time,
        "play_count": play_count or 0,
        "digg_count": digg_count or 0,
        "comment_count": comment_count or 0,
        "share_count": share_count or 0,
        "play_url": play_url or "",
        "download_url": download_url or "",
        "video_url": f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "",
        "_raw": raw,
    }


async def resolve_sec_user_id(home_url: str, cookie: str = "") -> str:
    # 如果用户没手动填 Cookie，自动从系统浏览器里读取
    if not cookie:
        cookie = _auto_fetch_cookie_from_browser()
        if cookie:
            logger.info("已自动注入浏览器 Cookie")
    else:
        logger.info("使用用户手动提供的 Cookie")

    kwargs = {
        "headers": {
            "User-Agent": config.HEADERS_UA,
            "Referer": config.REFERER,
            "Cookie": cookie,
        },
        "proxies": {"http://": None, "https://": None},
        "timeout": config.REQUEST_TIMEOUT,
        "cookie": cookie,
    }
    sec_user_id = await SecUserIdFetcher.get_sec_user_id(home_url)
    if not sec_user_id:
        raise RuntimeError("未能从主页链接解析出 sec_user_id，请检查链接是否正确、是否需要 Cookie")
    return sec_user_id, kwargs


async def fetch_all_videos(
    home_url: str,
    cookie: str = "",
    max_counts: Optional[int] = None,
    on_progress=None,
) -> List[Dict[str, Any]]:
    """拉取主页全部已发布作品，返回解析后的 list。

    on_progress(done, total_hint) 用于回传进度。
    """
    sec_user_id, kwargs = await resolve_sec_user_id(home_url, cookie)
    logger.info("sec_user_id=%s", sec_user_id)

    handler = DouyinHandler(kwargs)
    results: List[Dict[str, Any]] = []
    dump_path = os.path.join(config.OUTPUT_DIR, "_raw_dump.jsonl")

    async for page in handler.fetch_user_post_videos(sec_user_id, 0, 0, page_counts=config.PAGE_SIZE, max_counts=max_counts):
        # f2 不同版本：page 可能是 AwemePost 封装对象，也可能是 dict
        raw = None
        for attr in ("_to_raw", "to_dict", "_to_dict"):
            fn = getattr(page, attr, None)
            if callable(fn):
                try:
                    raw = fn()
                    break
                except Exception:
                    raw = None
        if raw is None:
            raw = page if isinstance(page, dict) else getattr(page, "__dict__", {})

        # raw 通常是 {aweme_list: [...]} 或直接是 list
        aweme_list = raw
        if isinstance(raw, dict):
            aweme_list = (
                _pick(raw, "aweme_list", "awemeList", "post_list", "data", "list", default=None)
            )
            if aweme_list is None and "aweme_detail" in raw:
                aweme_list = [raw["aweme_detail"]]
        if isinstance(aweme_list, dict):
            # 再嵌套一层
            aweme_list = _pick(aweme_list, "aweme_list", "list", default=[])

        if not isinstance(aweme_list, list):
            aweme_list = []

        for item in aweme_list:
            if not isinstance(item, dict):
                continue
            parsed = parse_aweme(item)
            if parsed["aweme_id"]:
                results.append(parsed)
                # 落盘原始数据用于排查
                try:
                    with open(dump_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                if on_progress:
                    on_progress(len(results), None)
                if max_counts and len(results) >= max_counts:
                    break
        if max_counts and len(results) >= max_counts:
            break

    return results
