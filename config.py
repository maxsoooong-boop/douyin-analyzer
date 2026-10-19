# -*- coding: utf-8 -*-
"""集中配置项。"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# ASR 模型名：可选 tiny / base / small / medium / large-v3
# 首次运行会自动从网络下载（small 约 460MB）
ASR_MODEL_NAME = os.environ.get("ASR_MODEL_NAME", "small")
ASR_COMPUTE_TYPE = "int8"
ASR_LANGUAGE = "zh"

# 下载/请求相关
HEADERS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
)
REFERER = "https://www.douyin.com/"
REQUEST_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 120

# 每页拉取数（f2 内部分页大小）
PAGE_SIZE = 20

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
