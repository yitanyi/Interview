import librosa
import numpy as np
import re
from typing import Dict

import librosa
import numpy as np
import logging
from typing import Dict

# 配置日志（可在主模块中配置，这里简单使用 print 作为备选）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_speech(audio_path: str, transcribed_text: str = "") -> Dict:
    """
    对音频文件进行语音特征分析
    """
    result = {
        "speaking_rate": 0,
        "pause_frequency": 0,
        "avg_volume": 0,
        "volume_std": 0,
        "avg_pitch": 0,
        "pitch_std": 0,
        "confidence": 0
    }
    try:
        y, sr = librosa.load(audio_path, sr=16000)
    except Exception as e:
        logger.error(f"音频加载失败 {audio_path}: {e}")
        result["error"] = str(e)
        return result

    total_duration = librosa.get_duration(y=y, sr=sr)

    # 1. 语音活动检测
    try:
        intervals = librosa.effects.split(y, top_db=30)
    except Exception as e:
        logger.error(f"语音活动检测失败: {e}")
        intervals = []

    if len(intervals) == 0:
        # 无有效语音，返回默认值
        logger.warning("未检测到有效语音段")
        return result

    speech_duration = sum((end - start) / sr for start, end in intervals)
    pause_count = len(intervals) - 1 if len(intervals) > 1 else 0
    pause_frequency = pause_count / total_duration if total_duration > 0 else 0

    # 2. 语速：确保 transcribed_text 是字符串
    if not isinstance(transcribed_text, str):
        logger.warning(f"transcribed_text 类型异常: {type(transcribed_text)}，使用空字符串")
        transcribed_text = ""
    word_count = len(transcribed_text)
    speaking_rate = word_count / speech_duration if speech_duration > 0 else 0

    # 3. 音量特征
    rms = librosa.feature.rms(y=y)[0]
    avg_volume = float(np.mean(rms)) if rms.size > 0 else 0
    volume_std = float(np.std(rms)) if rms.size > 0 else 0

    # 4. 基频特征
    try:
        f0, voiced_flag, _ = librosa.pyin(y, fmin=80, fmax=400, sr=sr)
        # 确保 f0 是数组
        if f0 is not None and hasattr(f0, '__len__') and len(f0) > 0:
            voiced_f0 = f0[~np.isnan(f0)]
            if len(voiced_f0) > 0:
                avg_pitch = float(np.mean(voiced_f0))
                pitch_std = float(np.std(voiced_f0))
            else:
                avg_pitch = 0
                pitch_std = 0
        else:
            avg_pitch = 0
            pitch_std = 0
    except Exception as e:
        logger.error(f"基频提取失败: {e}")
        avg_pitch = 0
        pitch_std = 0

    # 5. 自信度评分（确保数值非负）
    confidence = (
        0.4 * min(avg_volume / 0.1, 1.0) +
        0.3 * min(speaking_rate / 3.0, 1.0) +
        0.2 * (1.0 - min(pause_frequency, 1.0)) +
        0.1 * min(avg_pitch / 200.0, 1.0)
    )
    confidence = max(0.0, min(1.0, confidence))

    result.update({
        "speaking_rate": round(speaking_rate, 2),
        "pause_frequency": round(pause_frequency, 2),
        "avg_volume": round(avg_volume, 4),
        "volume_std": round(volume_std, 4),
        "avg_pitch": round(avg_pitch, 2),
        "pitch_std": round(pitch_std, 2),
        "confidence": round(confidence, 2)
    })
    return result