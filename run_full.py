# -*- coding: utf-8 -*-
"""完整跑一遍：爬取 → 下载视频 → ASR转写 → 生成Excel。"""
import json
import os
import time
import asyncio
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests

import config
import excel_writer
from asr import transcribe

TARGET_URL = "https://www.douyin.com/user/MS4wLjABAAAAu09iJGJ3vYEdzL2lMJuz8UNDuedVCOCQ35E98POwRJw?from_tab_name=main"

def scrape_videos():
    """用Playwright爬取所有视频元数据。"""
    all_awemes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        def handle_response(response):
            if "aweme/v1/web/aweme/post" in response.url:
                try:
                    data = response.json()
                    if "aweme_list" in data and data["aweme_list"]:
                        all_awemes.extend(data["aweme_list"])
                        print(f"  拦截到 {len(data['aweme_list'])} 个视频，累计 {len(all_awemes)}")
                except:
                    pass
        page.on("response", handle_response)

        print("1. 打开用户主页...")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        print("2. 滚动加载更多视频...")
        last_count = 0
        same_count_rounds = 0
        for i in range(30):  # 最多滚动30次
            page.mouse.wheel(0, 2000)
            time.sleep(2)
            if len(all_awemes) == last_count:
                same_count_rounds += 1
                if same_count_rounds >= 3:
                    break
            else:
                same_count_rounds = 0
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

    print(f"\n爬取完成，共 {len(unique)} 个视频")
    return unique


def parse_video(raw):
    """解析单条视频原始数据。"""
    aweme_id = raw.get("aweme_id", "")
    desc = raw.get("desc", "")
    create_ts = raw.get("create_time", 0)
    stats = raw.get("statistics", {})
    play_count = stats.get("play_count", 0)
    digg_count = stats.get("digg_count", 0)
    comment_count = stats.get("comment_count", 0)
    share_count = stats.get("share_count", 0)
    collect_count = stats.get("collect_count", 0)

    # 无水印视频地址
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
        "play_count": play_count,
        "digg_count": digg_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "collect_count": collect_count,
        "video_url": f"https://www.douyin.com/video/{aweme_id}",
        "download_url": video_url,
    }


def download_video(url, save_path):
    """下载视频到本地。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.douyin.com/",
    }
    r = requests.get(url, headers=headers, stream=True, timeout=30)
    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return os.path.getsize(save_path)


def main():
    # 1. 爬取
    raw_videos = scrape_videos()
    parsed = [parse_video(v) for v in raw_videos]

    # 2. 下载全部视频
    os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    download_count = len(parsed)  # 全部下载
    print(f"\n3. 下载前 {download_count} 个视频...")
    for i, v in enumerate(parsed[:download_count], 1):
        fname = f"{i:03d}.mp4"
        fpath = os.path.join(config.DOWNLOAD_DIR, fname)
        if os.path.exists(fpath) and os.path.getsize(fpath) > 10000:
            print(f"  [{i}/{download_count}] 已存在，跳过")
            v["local_file"] = fname
            continue
        try:
            print(f"  [{i}/{download_count}] 下载: {v['desc'][:30]}...")
            size = download_video(v["download_url"], fpath)
            print(f"       完成，{size//1024} KB")
            v["local_file"] = fname
        except Exception as e:
            print(f"       失败: {e}")
            v["local_file"] = ""

    # 3. ASR转写（前5个，快速）
    print(f"\n4. 语音转写口播...")
    for i, v in enumerate(parsed[:download_count], 1):
        if not v.get("local_file"):
            v["transcript"] = ""
            continue
        fpath = os.path.join(config.DOWNLOAD_DIR, v["local_file"])
        try:
            print(f"  [{i}/{download_count}] 转写中...")
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

    excel_path = os.path.join(config.OUTPUT_DIR, "抖音分析结果.xlsx")
    excel_writer.write_excel(rows, excel_path)
    print(f"\nExcel 已保存到: {excel_path}")

    # 5. 打包所有视频成zip
    print("\n6. 打包视频文件...")
    import zipfile
    zip_path = os.path.join(config.OUTPUT_DIR, "抖音视频合集.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, v in enumerate(parsed, 1):
            fname = f"{i:03d}.mp4"
            fpath = os.path.join(config.DOWNLOAD_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
                print(f"  打包: {fname}")
    print(f"\n打包完成: {zip_path}")
    print(f"\n=== 全部完成 ===")
    print(f"总视频数: {len(rows)}")
    print(f"已下载: {download_count} 个")
    print(f"Excel: {excel_path}")
    print(f"视频包: {zip_path}")


if __name__ == "__main__":
    main()
