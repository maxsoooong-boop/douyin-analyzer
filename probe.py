# -*- coding: utf-8 -*-
"""一次性探测脚本：dump f2 真实作品字段结构。
用法: py probe.py <主页URL> [cookie]
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f2.apps.douyin.handler import DouyinHandler
from f2.apps.douyin.utils import SecUserIdFetcher
import config


async def main():
    home_url = sys.argv[1]
    cookie = sys.argv[2] if len(sys.argv) > 2 else ""
    kwargs = {
        "headers": {"User-Agent": config.HEADERS_UA, "Referer": config.REFERER, "Cookie": cookie},
        "proxies": {"http://": None, "https://": None},
        "timeout": config.REQUEST_TIMEOUT,
        "cookie": cookie,
    }
    sec_uid = await SecUserIdFetcher.get_sec_user_id(home_url)
    print("SEC_USER_ID =", sec_uid)
    handler = DouyinHandler(kwargs)
    async for page in handler.fetch_user_post_videos(sec_uid, 0, 0, page_counts=5, max_counts=5):
        # 打印 page 对象类型和可用方法
        print("=== PAGE TYPE:", type(page))
        raw = None
        for attr in ("_to_raw", "to_dict", "_to_dict", "model_dump", "dict"):
            fn = getattr(page, attr, None)
            if callable(fn):
                try:
                    raw = fn()
                    print("used attr:", attr)
                    break
                except Exception as e:
                    print(attr, "failed:", e)
        if raw is None:
            raw = getattr(page, "__dict__", page)
        out = os.path.join(config.BASE_DIR, "_probe_out.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2, default=str)
        print("dumped ->", out)
        # 打印顶层结构
        if isinstance(raw, dict):
            print("TOP KEYS:", list(raw.keys()))
            for k, v in raw.items():
                if isinstance(v, list):
                    print(f"  {k}: list len={len(v)}")
                    if v and isinstance(v[0], dict):
                        print(f"    item[0] keys:", list(v[0].keys()))
        break  # 只看第一页


if __name__ == "__main__":
    asyncio.run(main())
