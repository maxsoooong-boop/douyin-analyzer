# -*- coding: utf-8 -*-
"""faster-whisper 本地离线语音识别，输出完整逐字稿。"""
import os
import subprocess
import numpy as np
import threading
import logging

import config

logger = logging.getLogger("asr")

_model = None
_lock = threading.Lock()


def _load_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("loading whisper model: %s (compute_type=%s)", config.ASR_MODEL_NAME, config.ASR_COMPUTE_TYPE)
        _model = WhisperModel(config.ASR_MODEL_NAME, device="cpu", compute_type=config.ASR_COMPUTE_TYPE)
    return _model


def _load_audio_as_numpy(video_path: str) -> np.ndarray:
    """用 ffmpeg 直接把音频解码成 16kHz 单声道 float32 numpy 数组，绕过 pyav。"""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    audio = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def transcribe(video_path: str) -> str:
    """对视频文件做中文语音识别，返回完整逐字稿文本。失败抛异常。"""
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)

    # 用 ffmpeg 解码音频成 numpy 数组，直接传给 whisper，绕过 pyav 兼容问题
    audio = _load_audio_as_numpy(video_path)
    with _lock:
        model = _load_model()
    segments, info = model.transcribe(
        audio,
        language=config.ASR_LANGUAGE,
        vad_filter=True,
        beam_size=1,
    )
    parts = []
    for seg in segments:
        parts.append(seg.text.strip())
    return "".join(parts).strip()
