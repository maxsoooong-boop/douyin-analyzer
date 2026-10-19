# -*- coding: utf-8 -*-
"""直接用 Playwright 浏览器爬取，绕过 f2 的签名问题。"""
import json
import time
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.douyin.com/user/MS4wLjABAAAAu09iJGJ3vYEdzL2lMJuz8UNDuedVCOCQ35E98POwRJw?from_tab_name=main"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = context.new_page()

    # 先拦截网络请求，看抖音自己发的API长什么样
    api_responses = []
    def handle_response(response):
        if "aweme/post" in response.url or "aweme/v1/web/aweme/post" in response.url:
            try:
                data = response.json()
                api_responses.append(data)
                print(f"[拦截到API] {response.url[:80]}...")
            except:
                pass
    page.on("response", handle_response)

    print("正在打开用户主页...")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)

    # 看看页面标题
    print("页面标题:", page.title())

    # 滚动页面加载更多视频
    print("滚动加载视频...")
    for i in range(3):
        page.mouse.wheel(0, 1000)
        time.sleep(2)

    # 等一下让API返回
    time.sleep(3)

    print(f"\n共拦截到 {len(api_responses)} 个作品列表API响应")
    if api_responses:
        # 合并所有视频
        all_awemes = []
        for resp in api_responses:
            if "aweme_list" in resp:
                all_awemes.extend(resp["aweme_list"])
        print(f"总共拿到 {len(all_awemes)} 个视频")
        if all_awemes:
            # 打印第一个视频的字段
            first = all_awemes[0]
            print("\n第一个视频字段:")
            print("  描述:", first.get("desc", "")[:50])
            print("  统计:", json.dumps(first.get("statistics", {}), ensure_ascii=False, indent=2)[:300])
            # 保存原始数据
            with open("test_raw.json", "w", encoding="utf-8") as f:
                json.dump(all_awemes, f, ensure_ascii=False, indent=2)
            print("\n原始数据已保存到 test_raw.json")

    browser.close()
