# -*- coding: utf-8 -*-
"""用test_raw.json重新生成正确的Excel，并转写口播。"""
import json
import os
from datetime import datetime
import pandas as pd
from asr import transcribe
import config

# 读原始数据
with open("test_raw.json", "r", encoding="utf-8") as f:
    raw_videos = json.load(f)

# 提取昵称
nickname = raw_videos[0].get("author", {}).get("nickname", "港澳旅游攻略")
safe_name = "".join([c for c in nickname if c not in r'\/:*?"<>|']).strip()
print(f"账号昵称: {safe_name}")

print(f"共 {len(raw_videos)} 个视频，开始处理...")

rows = []
for i, v in enumerate(raw_videos, 1):
    desc = v.get("desc", "")
    ct = v.get("create_time", 0)
    ct_str = datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M") if ct else ""
    stats = v.get("statistics", {})
    aweme_id = v.get("aweme_id", "")

    rows.append({
        "编号": i,
        "发布文案": desc,
        "口播文案": "",
        "发布时间": ct_str,
        "播放量": stats.get("play_count", 0),
        "点赞量": stats.get("digg_count", 0),
        "评论量": stats.get("comment_count", 0),
        "转发量": stats.get("share_count", 0),
        "视频链接": f"https://www.douyin.com/video/{aweme_id}",
    })

# 先存一个基础Excel
out_dir = os.path.join(config.OUTPUT_DIR, safe_name)
os.makedirs(out_dir, exist_ok=True)
excel_path = os.path.join(out_dir, f"{safe_name}_分析结果.xlsx")

# 逐个转写
for i, v in enumerate(raw_videos, 1):
    fname = f"{i:03d}.mp4"
    fpath = os.path.join(config.DOWNLOAD_DIR, fname)
    if not os.path.exists(fpath):
        print(f"[{i}/{len(raw_videos)}] 文件不存在，跳过")
        continue
    print(f"[{i}/{len(raw_videos)}] 转写中: {rows[i-1]['发布文案'][:30]}...")
    try:
        text = transcribe(fpath)
        rows[i-1]["口播文案"] = text
        print(f"       完成，{len(text)} 字")
    except Exception as e:
        print(f"       失败: {e}")

# 保存Excel
df = pd.DataFrame(rows)
df.to_excel(excel_path, index=False)
print(f"\nExcel 已保存: {excel_path}")

# 打包视频
import zipfile
zip_path = os.path.join(out_dir, f"{safe_name}_视频合集.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for i in range(1, len(raw_videos)+1):
        fname = f"{i:03d}.mp4"
        fpath = os.path.join(config.DOWNLOAD_DIR, fname)
        if os.path.exists(fpath):
            zf.write(fpath, arcname=fname)
print(f"视频包已保存: {zip_path}")
print("\n=== 1号账号完成 ===")
