# -*- coding: utf-8 -*-
"""用FunASR重新转写所有视频，更新Excel。"""
import os
import pandas as pd
from funasr import AutoModel
import config

# 加载FunASR模型（paraformer-zh是中文识别最好的开源模型之一）
print("加载FunASR模型（首次会自动下载，约1GB）...")
model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
)
print("模型加载完成！")

out_dir = config.OUTPUT_DIR

# 遍历所有账号文件夹
for folder in os.listdir(out_dir):
    folder_path = os.path.join(out_dir, folder)
    if not os.path.isdir(folder_path):
        continue
    xlsx_files = [f for f in os.listdir(folder_path) if f.endswith(".xlsx") and not f.startswith("~$")]
    if not xlsx_files:
        continue
    xlsx_path = os.path.join(folder_path, xlsx_files[0])
    videos_dir = os.path.join(folder_path, "videos")
    if not os.path.exists(videos_dir):
        continue

    print(f"\n=== 处理账号: {folder} ===")
    df = pd.read_excel(xlsx_path)
    total = len(df)

    for i, row in df.iterrows():
        if pd.isna(row["编号"]):
            continue
        idx = int(row["编号"])
        fname = f"{idx:03d}.mp4"
        fpath = os.path.join(videos_dir, fname)
        if not os.path.exists(fpath):
            print(f"  [{idx}/{total}] 文件不存在，跳过")
            continue

        print(f"  [{idx}/{total}] 转写中: {str(row['发布文案'])[:30]}...")
        try:
            res = model.generate(input=fpath, batch_size_s=300)
            text = res[0]["text"].strip()
            df.at[i, "口播文案"] = text
            print(f"       完成，{len(text)} 字: {text[:50]}...")
        except Exception as e:
            print(f"       失败: {e}")

    # 保存更新后的Excel
    df.to_excel(xlsx_path, index=False)
    print(f"  Excel已更新: {xlsx_path}")

print("\n=== 全部转写完成！ ===")
