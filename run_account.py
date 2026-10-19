# -*- coding: utf-8 -*-
"""通用账号跑数脚本：传入主页URL和输出目录名，跑完整流程。"""
import json
import os
import sys
import time
import zipfile
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests

import config
from asr import transcribe


def scrape_videos(target_url):
    """用Playwright爬取所有视频元数据，返回(视频列表, 用户昵称)。"""
    all_awemes = []
    nickname = "未知用户"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        def handle_response(response):
            nonlocal nickname
            if "aweme/v1/web/aweme/post" in response.url:
                try:
                    data = response.json()
                    if "aweme_list" in data and data["aweme_list"]:
                        all_awemes.extend(data["aweme_list"])
                        print(f"  拦截到 {len(data['aweme_list'])} 个，累计 {len(all_awemes)}")
                except:
                    pass
            # 从用户信息API提取昵称
            if "web/aweme/post" not in response.url and "user/info" in response.url:
                try:
                    data = response.json()
                    user = data.get("user", {})
                    if user.get("nickname"):
                        nickname = user["nickname"]
                        print(f"  用户昵称: {nickname}")
                except:
                    pass
        page.on("response", handle_response)

        print(f"1. 打开主页: {target_url[:60]}...")
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # 从页面标题兜底提取昵称
        if nickname == "未知用户":
            try:
                title = page.title()
                # 标题格式一般是 "昵称 - 抖音"
                if "- 抖音" in title:
                    nickname = title.replace("- 抖音", "").strip()
                    print(f"  从标题提取昵称: {nickname}")
            except:
                pass

        print("2. 滚动加载...")
        last_count = 0
        same_rounds = 0
        for i in range(40):
            page.mouse.wheel(0, 2000)
            time.sleep(2)
            if len(all_awemes) == last_count:
                same_rounds += 1
                if same_rounds >= 4:
                    break
            else:
                same_rounds = 0
                last_count = len(all_awemes)

        browser.close()

    # 去重
    seen = set()
    unique = []
    for a in all_awemes:
        aid = a.get("aweme_id")
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(a)

    print(f"爬取完成，共 {len(unique)} 个视频，昵称: {nickname}")
    return unique, nickname


def parse_video(raw):
    aweme_id = raw.get("aweme_id", "")
    desc = raw.get("desc", "")
    create_ts = raw.get("create_time", 0)
    stats = raw.get("statistics", {})

    video = raw.get("video", {})
    video_url = ""
    bit_rate = video.get("bit_rate", [])
    for br in bit_rate:
        pa = br.get("play_addr", {})
        urls = pa.get("url_list", [])
        if urls:
            video_url = urls[0]
            break
    if not video_url:
        pa = video.get("play_addr", {})
        urls = pa.get("url_list", [])
        if urls:
            video_url = urls[0]

    return {
        "aweme_id": aweme_id,
        "desc": desc,
        "create_time": create_ts,
        "play_count": stats.get("play_count", 0),
        "digg_count": stats.get("digg_count", 0),
        "comment_count": stats.get("comment_count", 0),
        "share_count": stats.get("share_count", 0),
        "collect_count": stats.get("collect_count", 0),
        "video_url": f"https://www.douyin.com/video/{aweme_id}",
        "download_url": video_url,
    }


def download_video(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.douyin.com/",
    }
    r = requests.get(url, headers=headers, stream=True, timeout=60)
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return os.path.getsize(save_path)


def main():
    if len(sys.argv) < 2:
        print("用法: python run_account.py <主页URL>")
        sys.exit(1)

    target_url = sys.argv[1]

    # 1. 爬取
    raw_videos, nickname = scrape_videos(target_url)
    parsed = [parse_video(v) for v in raw_videos]

    # 清理昵称作为文件夹名（去掉非法字符）
    safe_name = "".join([c for c in nickname if c not in r'\/:*?"<>|']).strip()
    if not safe_name:
        safe_name = "未知用户"
    out_name = safe_name

    # 建目录
    base_dir = os.path.join(config.OUTPUT_DIR, out_name)
    dl_dir = os.path.join(base_dir, "videos")
    os.makedirs(dl_dir, exist_ok=True)

    # 2. 下载全部视频
    print(f"\n3. 下载全部 {len(parsed)} 个视频...")
    for i, v in enumerate(parsed, 1):
        fname = f"{i:03d}.mp4"
        fpath = os.path.join(dl_dir, fname)
        if os.path.exists(fpath) and os.path.getsize(fpath) > 10000:
            print(f"  [{i}/{len(parsed)}] 已存在，跳过")
            v["local_file"] = fname
            continue
        # 重试3次
        for retry in range(3):
            try:
                print(f"  [{i}/{len(parsed)}] 下载: {v['desc'][:30]}...")
                size = download_video(v["download_url"], fpath)
                print(f"       完成，{size//1024} KB")
                v["local_file"] = fname
                break
            except Exception as e:
                print(f"       第{retry+1}次失败: {e}")
                if retry == 2:
                    v["local_file"] = ""

    # 3. 全部转写
    print(f"\n4. 语音转写口播...")
    for i, v in enumerate(parsed, 1):
        if not v.get("local_file"):
            v["transcript"] = ""
            continue
        fpath = os.path.join(dl_dir, v["local_file"])
        try:
            print(f"  [{i}/{len(parsed)}] 转写中...")
            text = transcribe(fpath)
            v["transcript"] = text
            print(f"       完成，{len(text)} 字")
        except Exception as e:
            print(f"       失败: {e}")
            v["transcript"] = ""

    # 4. 生成Excel
    print("\n5. 生成Excel...")
    rows = []
    for i, v in enumerate(parsed, 1):
        ct = v.get("create_time", 0)
        ct_str = datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M") if ct else ""
        rows.append({
            "编号": i,
            "发布文案": v.get("desc", ""),
            "口播文案": v.get("transcript", ""),
            "发布时间": ct_str,
            "播放量": v.get("play_count", 0),
            "点赞量": v.get("digg_count", 0),
            "评论量": v.get("comment_count", 0),
            "转发量": v.get("share_count", 0),
            "视频链接": v.get("video_url", ""),
        })

    import pandas as pd
    excel_path = os.path.join(base_dir, f"{out_name}_分析结果.xlsx")
    pd.DataFrame(rows).to_excel(excel_path, index=False)
    print(f"Excel: {excel_path}")

    # 5. 打包视频
    print("\n6. 打包视频...")
    zip_path = os.path.join(base_dir, f"{out_name}_视频合集.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, v in enumerate(parsed, 1):
            fname = f"{i:03d}.mp4"
            fpath = os.path.join(dl_dir, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
    print(f"视频包: {zip_path}")

    print(f"\n=== {out_name} 全部完成 ===")


if __name__ == "__main__":
    main()
