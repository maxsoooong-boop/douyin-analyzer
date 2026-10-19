# -*- coding: utf-8 -*-
"""重新转写所有视频，更新Excel里的口播文案。"""
import os
import pandas as pd
from asr import transcribe
import config

excel_path = os.path.join(config.OUTPUT_DIR, "抖音分析结果.xlsx")
df = pd.read_excel(excel_path)
print(f"共 {len(df)} 行，开始转写...")

for i, row in df.iterrows():
    if pd.isna(row["编号"]):
        continue
    idx = int(row["编号"])
    fname = f"{idx:03d}.mp4"
    fpath = os.path.join(config.DOWNLOAD_DIR, fname)
    if not os.path.exists(fpath):
        print(f"[{idx}] 文件不存在，跳过")
        continue
    print(f"[{idx}/{len(df)}] 转写中: {row['发布文案'][:30]}...")
    try:
        text = transcribe(fpath)
        df.at[i, "口播文案"] = text
        print(f"       完成，{len(text)} 字")
    except Exception as e:
        print(f"       失败: {e}")

new_path = excel_path.replace(".xlsx", "_含口播.xlsx")
df.to_excel(new_path, index=False)
print(f"\n更新完成！已保存到: {new_path}")
