

# audio_utils.py
import os
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from faster_whisper import WhisperModel
from speech_analyzer import analyze_speech

logger = logging.getLogger(__name__)

def _to_simplified(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    try:
        from opencc import OpenCC  # 可选依赖：opencc / opencc-python-reimplemented
        return OpenCC("t2s").convert(text)
    except Exception:
        return text

def _ensure_wav_16k_mono(input_path: str) -> str:
    """
    尽量将输入音频转为 16kHz 单声道 WAV，以提升 Whisper 解码稳定性。
    若系统无 ffmpeg 或转换失败，则回退为原始路径。
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path

    suffix = Path(input_path).suffix.lower()
    if suffix == ".wav":
        return input_path

    tmp_dir = Path(tempfile.gettempdir())
    out_path = tmp_dir / f"resume_roaster_{next(tempfile._get_candidate_names())}.wav"
    cmd = [
        ffmpeg, "-y",
        "-i", input_path,
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(out_path)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return str(out_path)
    except Exception:
        return input_path

# 初始化模型（首次运行会自动下载，模型大小可选 tiny/base/small/medium/large-v2）
# GPU 用法：设置环境变量 WHISPER_DEVICE=cuda（或 cuda:0），并配合 WHISPER_COMPUTE_TYPE=float16 / int8_float16
def _load_whisper_model():
    model_size = os.getenv("WHISPER_MODEL_SIZE", "medium").strip() or "medium"

    # Prefer explicit env vars; otherwise auto-pick CUDA when available.
    env_device = os.getenv("WHISPER_DEVICE", "").strip()
    if env_device:
        device = env_device
    else:
        try:
            import ctranslate2
            device = "cuda" if getattr(ctranslate2, "get_cuda_device_count", lambda: 0)() > 0 else "cpu"
        except Exception:
            device = "cpu"

    env_compute = os.getenv("WHISPER_COMPUTE_TYPE", "").strip()
    if env_compute:
        compute_type = env_compute
    else:
        # Reasonable defaults: GPU prefers float16; CPU prefers int8.
        compute_type = "float16" if str(device).startswith("cuda") else "int8"

    try:
        return WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as e:
        # 如果 GPU/compute_type 不可用，自动回退到 CPU，避免直接不可用
        logger.warning(f"Whisper 使用 {device}/{compute_type} 加载失败，将回退到 CPU: {e}")
        return WhisperModel(model_size, device="cpu", compute_type="int8")

try:
    model = _load_whisper_model()
except Exception as e:
    logger.error(f"Whisper模型加载失败: {e}")
    model = None

def transcribe_audio(file_path: str) -> dict:
    """
    将音频文件转换为文本，并附加语音分析结果
    始终返回字典，包含 'text' 和 'analysis' 字段
    """
    # 初始化默认结果
    result = {
        "text": "",
        "analysis": {
            "speaking_rate": 0,
            "pause_frequency": 0,
            "avg_volume": 0,
            "volume_std": 0,
            "avg_pitch": 0,
            "pitch_std": 0,
            "confidence": 0
        }
    }

    if model is None:
        logger.error("Whisper模型未加载，无法进行语音识别")
        result["analysis"]["error"] = "语音识别模型未初始化"
        return result

    try:
        # 1. 语音识别
        decode_path = _ensure_wav_16k_mono(file_path)
        segments, info = model.transcribe(
            decode_path,
            beam_size=5,
            language="zh",
            vad_filter=True,
            initial_prompt="请使用简体中文输出。"
        )
        text = " ".join([segment.text for segment in segments]).strip()
        result["text"] = _to_simplified(text)
    except Exception as e:
        logger.error(f"语音识别失败: {e}")
        result["analysis"]["error"] = f"识别失败: {str(e)}"
        # 继续尝试进行语音分析（不依赖文本）

    try:
        # 2. 语音分析（即使识别失败，也尝试分析音频特征）
        analysis = analyze_speech(file_path, transcribed_text=result["text"])
        # 如果 analysis 中有 error 字段，保留它
        result["analysis"].update(analysis)
    except Exception as e:
        logger.error(f"语音分析失败: {e}")
        result["analysis"]["error"] = f"分析失败: {str(e)}"

    if not result["text"]:
        result["analysis"].setdefault("warning", "未识别到有效文本：请确保录音时长足够、麦克风输入正常，或提高 WHISPER_MODEL_SIZE（如 medium/large-v2）。")

    return result
