# -*- coding: utf-8 -*-
"""用FunASR重新转写指定账号。"""
import os
import sys
import pandas as pd
from funasr import AutoModel

folder_name = sys.argv[1]
base_dir = r"C:\Users\49388\Doubao\chats\2026-10-17\new-chat\douyin-analyzer\outputs"
folder_path = os.path.join(base_dir, folder_name)

print("加载FunASR模型...")
model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
)
print("模型加载完成！")

xlsx_files = [f for f in os.listdir(folder_path) if f.endswith(".xlsx") and not f.startswith("~$")]
xlsx_path = os.path.join(folder_path, xlsx_files[0])
videos_dir = os.path.join(folder_path, "videos")

df = pd.read_excel(xlsx_path)
total = len(df)
print(f"共 {total} 个视频，开始转写...")

for i, row in df.iterrows():
    if pd.isna(row["编号"]):
        continue
    idx = int(row["编号"])
    fname = f"{idx:03d}.mp4"
    fpath = os.path.join(videos_dir, fname)
    if not os.path.exists(fpath):
        print(f"  [{idx}/{total}] 文件不存在，跳过")
        continue

    print(f"  [{idx}/{total}] 转写中...")
    try:
        res = model.generate(input=fpath, batch_size_s=300)
        text = res[0]["text"].strip()
        df.at[i, "口播文案"] = text
        print(f"       完成，{len(text)} 字: {text[:50]}...")
    except Exception as e:
        print(f"       失败: {e}")

df.to_excel(xlsx_path, index=False)
print(f"\nExcel已更新: {xlsx_path}")
print("完成！")
