# -*- coding: utf-8 -*-
"""
Interview API Server
提供 RESTful API 接口支持移动端应用
"""
from flask import make_response  # 新增
import io
import base64
import asyncio
import tempfile
import os
import edge_tts
import re
from collections import OrderedDict
from threading import Lock

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import json
import uuid
from position_manager import PositionManager
from knowledge_loader import load_knowledge_base
from evaluation import create_evaluation_chain, evaluate_answer
from audio_utils import transcribe_audio
from recommendation import recommend_resources
import database
import os
import sys
import configparser
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
import ocr_utils  # 新增导入
import ocr_utils
print("ocr_utils 模块中的属性：", dir(ocr_utils))
from ocr_utils import recognize_image
from speech_analyzer import analyze_speech
import edge_tts
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from main import load_config, get_llm, load_resume, create_interview_chain, get_interview_style_prompt, normalize_interview_style

import os
from pathlib import Path

# 获取 api_server.py 所在的绝对目录（示例：D:\Interview\Interview）
BASE_DIR = Path(__file__).parent.resolve()
print(f"[DEBUG] 基础目录: {BASE_DIR}")
# Flask 应用
app = Flask(__name__)

# 全局配置
api_config = {
    'port': 5000,
    'cors_enabled': True,
    'cors_origins': '*'
}

# 全局存储
resume_store: Dict[str, any] = {}  # resume_id -> resume data
session_store: Dict[str, any] = {}  # session_id -> session data
# 全局岗位管理器
# 使用绝对路径初始化 PositionManager
position_manager = PositionManager(positions_dir=str(BASE_DIR / "positions"))

print(f"[DEBUG] 岗位目录: {position_manager.positions_dir}")
print(f"[DEBUG] 目录是否存在: {position_manager.positions_dir.exists()}")
print(f"[DEBUG] JSON文件: {list(position_manager.positions_dir.glob('*.json'))}")
print(f"[DEBUG] 已加载岗位: {list(position_manager.positions.keys())}")
# 初始化数据库（如果使用）
database.init_db()
# 创建临时目录
TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)


@app.route('/api/tts', methods=['POST'])
def tts():
    """
    Separate TTS endpoint so the frontend can request audio asynchronously.
    This avoids blocking the main /interview/* responses on TTS generation.
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Missing text", "message": "请提供 text"}), 400

    audio_list = text_to_speech_base64_list_cached(text)
    audio = audio_list[0] if len(audio_list) == 1 else ""
    return jsonify({"success": True, "audio": audio, "audio_list": audio_list}), 200

VOICE_MAP = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",
    "yunxi": "zh-CN-YunxiNeural",
    "yunjian": "zh-CN-YunjianNeural",
    "xiaoyi": "zh-CN-XiaoyiNeural",
    "yunxia": "zh-CN-YunxiaNeural",
    "yunfeng": "zh-CN-YunfengNeural",
    "default": "zh-CN-XiaoxiaoNeural"
}


def resolve_voice_name(voice_key: Optional[str]) -> str:
    """Map a friendly voice key to an actual Edge TTS voice ID."""
    if not voice_key:
        return VOICE_MAP["default"]
    cleaned = voice_key.strip()
    return VOICE_MAP.get(cleaned, cleaned)


def load_tts_config():
    config = configparser.ConfigParser(interpolation=None)
    config_path = Path(__file__).parent / "config.ini"
    defaults = {
        "voice": "xiaoxiao",
        "rate": "+0%"
    }
    if not config_path.exists():
        return defaults
    config.read(config_path, encoding='utf-8')
    if not config.has_section("tts"):
        return defaults
    for key in defaults:
        if config.has_option("tts", key):
            defaults[key] = config.get("tts", key)
    return defaults


def normalize_rate(rate: Optional[str]) -> str:
    """Edge TTS requires rate like '+0%' or '-10%' (not '0%')."""
    if not rate:
        return "+0%"
    cleaned = rate.strip()
    if cleaned.startswith(("+", "-")):
        return cleaned
    return f"+{cleaned}"


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _edge_tts_to_bytes(text: str, voice_name: str, rate: str) -> bytes:
    """
    Generate MP3 bytes via edge-tts.
    Use streaming to avoid filesystem I/O, which reduces latency on Windows.
    """
    communicate = edge_tts.Communicate(text, voice_name, rate=rate)
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk.get("data", b""))
    return bytes(audio)


def text_to_speech_base64(text: str) -> str:
    """
    使用 Edge TTS 将文本转换成 base64 音频，用于前端自动播放。
    """
    if not text:
        return ""
    cfg = load_tts_config()
    voice_name = resolve_voice_name(cfg.get("voice"))
    rate = normalize_rate(cfg.get("rate", "+0%"))
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return ""
    try:
        max_chars = int(os.getenv("TTS_MAX_CHARS", "240"))
        chunks = []
        if len(clean_text) <= max_chars:
            chunks = [clean_text]
        else:
            parts = re.split(r"([。！？.!?])", clean_text)
            current = ""
            for part in parts:
                if not part:
                    continue
                if len(current) + len(part) > max_chars:
                    if current:
                        chunks.append(current.strip())
                    current = part
                else:
                    current += part
            if current:
                chunks.append(current.strip())
        async def _tts_all(_chunks):
            parts = []
            for c in _chunks:
                b = await _edge_tts_to_bytes(c, voice_name, rate)
                if b:
                    parts.append(b)
            return b"".join(parts)

        # Run a single event loop for the entire text to reduce per-chunk overhead.
        audio_bytes = _run_async(_tts_all(chunks))
        if not audio_bytes:
            return ""
        return "data:audio/mpeg;base64," + base64.b64encode(audio_bytes).decode()
    except Exception as exc:
        print(f"[WARN] TTS 生成失败：{exc}")
        return ""


def _tts_inline_enabled() -> bool:
    return os.getenv("TTS_INLINE", "0").strip().lower() in ("1", "true", "yes", "on")


_TTS_CACHE: "OrderedDict[str, str]" = OrderedDict()
_TTS_CACHE_LOCK = Lock()


def _split_tts_text(clean_text: str, max_chars: int) -> list:
    if not clean_text:
        return []
    if len(clean_text) <= max_chars:
        return [clean_text]

    parts = re.split(r"([。！？.!?])", clean_text)
    chunks = []
    current = ""
    for part in parts:
        if not part:
            continue
        if len(current) + len(part) > max_chars:
            if current:
                chunks.append(current.strip())
            current = part
        else:
            current += part
    if current:
        chunks.append(current.strip())
    return chunks


def text_to_speech_base64_cached(text: str) -> str:
    """
    Small in-memory cache for TTS results to avoid recomputing common prompts.
    Cache key includes voice+rate+text.
    """
    if not text:
        return ""

    cfg = load_tts_config()
    voice_name = resolve_voice_name(cfg.get("voice"))
    rate = normalize_rate(cfg.get("rate", "+0%"))
    key = f"{voice_name}|{rate}|{text.strip()}"
    max_items = int(os.getenv("TTS_CACHE_SIZE", "64"))

    with _TTS_CACHE_LOCK:
        hit = _TTS_CACHE.get(key)
        if hit is not None:
            _TTS_CACHE.move_to_end(key)
            return hit

    audio = text_to_speech_base64(text)

    with _TTS_CACHE_LOCK:
        _TTS_CACHE[key] = audio
        _TTS_CACHE.move_to_end(key)
        while len(_TTS_CACHE) > max_items:
            _TTS_CACHE.popitem(last=False)

    return audio


_TTS_LIST_CACHE: "OrderedDict[str, list]" = OrderedDict()
_TTS_LIST_CACHE_LOCK = Lock()


def text_to_speech_base64_list(text: str) -> list:
    """
    Return a list of base64 audio data URIs (one per chunk).

    IMPORTANT: Do not concatenate MP3 byte streams; many players will stop after the first chunk.
    """
    if not text:
        return []

    cfg = load_tts_config()
    voice_name = resolve_voice_name(cfg.get("voice"))
    rate = normalize_rate(cfg.get("rate", "+0%"))
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return []

    max_chars = int(os.getenv("TTS_MAX_CHARS", "240"))
    chunks = _split_tts_text(clean_text, max_chars=max_chars)

    async def _tts_all(_chunks):
        parts = []
        for c in _chunks:
            b = await _edge_tts_to_bytes(c, voice_name, rate)
            if b:
                parts.append("data:audio/mpeg;base64," + base64.b64encode(b).decode())
        return parts

    try:
        return _run_async(_tts_all(chunks))
    except Exception as exc:
        print(f"[WARN] TTS 生成失败：{exc}")
        return []


def text_to_speech_base64_list_cached(text: str) -> list:
    if not text:
        return []

    cfg = load_tts_config()
    voice_name = resolve_voice_name(cfg.get("voice"))
    rate = normalize_rate(cfg.get("rate", "+0%"))
    key = f"{voice_name}|{rate}|{text.strip()}"
    max_items = int(os.getenv("TTS_CACHE_SIZE", "64"))

    with _TTS_LIST_CACHE_LOCK:
        hit = _TTS_LIST_CACHE.get(key)
        if hit is not None:
            _TTS_LIST_CACHE.move_to_end(key)
            return hit

    audio_list = text_to_speech_base64_list(text)

    with _TTS_LIST_CACHE_LOCK:
        _TTS_LIST_CACHE[key] = audio_list
        _TTS_LIST_CACHE.move_to_end(key)
        while len(_TTS_LIST_CACHE) > max_items:
            _TTS_LIST_CACHE.popitem(last=False)

    return audio_list


class SessionManager:
    """会话管理器"""
    
    @staticmethod
    def create_session(resume_id: str, chain: any) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session_store[session_id] = {
            'resume_id': resume_id,
            'chain': chain,
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'message_count': 0
        }
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> Optional[dict]:
        """获取会话"""
        if session_id not in session_store:
            return None
        
        # 更新最后活动时间
        session_store[session_id]['last_activity'] = datetime.now()
        return session_store[session_id]
    
    @staticmethod
    def end_session(session_id: str) -> bool:
        """结束会话"""
        if session_id not in session_store:
            return False
        
        session = session_store[session_id]
        
        # 清理资源
        if 'chain' in session:
            try:
                del session['chain']
            except:
                pass
        
        del session_store[session_id]
        return True
    
    @staticmethod
    def cleanup_expired_sessions():
        """清理过期会话（超过30分钟无活动）"""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in session_store.items():
            if (now - session['last_activity']).total_seconds() > 1800:  # 30分钟
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            SessionManager.end_session(session_id)
        
        if expired_sessions:
            print(f"已清理 {len(expired_sessions)} 个过期会话")


def load_api_config():
    """加载 API 配置"""
    global api_config
    
    # 首先加载现有配置
    config = load_config()
    if config is None:
        print("警告：无法加载 config.ini，使用默认 API 配置")
        return
    
    # 读取 API 配置（从 config.ini 的 [api] 部分）
    try:
        api_config['port'] = config.get('api', 'port', fallback='5000')
        api_config['cors_enabled'] = config.getboolean('api', 'cors_enabled', fallback=True)
        api_config['cors_origins'] = config.get('api', 'cors_origins', fallback='*')
    except configparser.NoSectionError:
        print("警告：config.ini 中没有 [api] 配置段，使用默认配置")
    except Exception as e:
        print(f"警告：读取 API 配置失败：{e}，使用默认配置")
    
    # 配置 CORS
    if api_config['cors_enabled']:
        CORS(app, resources={
            r"/api/*": {
                "origins": api_config['cors_origins'],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Session-ID"]
            }
        })
        print(f"CORS 已启用，允许来源：{api_config['cors_origins']}")


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }), 200


@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    """上传简历接口（支持 PDF 和图片）"""
    try:
        # ---------- 1. 检查请求中是否有文件 ----------
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': '请提供简历文件'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'error': 'No file selected',
                'message': '请选择文件'
            }), 400

        # ---------- 2. 验证文件类型 ----------
        filename = file.filename
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        allowed_pdf = ['pdf']
        allowed_images = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff', 'webp']  # 阿里云OCR支持的图片格式
        if ext not in (allowed_pdf + allowed_images):
            return jsonify({
                'error': 'Unsupported file format',
                'message': f'不支持的文件格式：{ext}，请上传 PDF 或常见图片（jpg/png/bmp等）'
            }), 400

        # ---------- 3. 验证文件大小（10MB限制）----------
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 10 * 1024 * 1024:
            return jsonify({
                'error': 'File too large',
                'message': '文件大小不能超过10MB'
            }), 400

        # ---------- 4. 保存文件到临时目录 ----------
        resume_id = str(uuid.uuid4())
        temp_file = TEMP_DIR / f"{resume_id}.{ext}"  # 保留原始扩展名
        file.save(str(temp_file))

        chunks = None  # 用于存储 langchain 的 Document 列表

        # ---------- 5. 根据文件类型处理 ----------
        if ext == 'pdf':
            # PDF：使用原有 load_resume 提取文本
            try:
                chunks = load_resume(temp_file)
            except Exception as e:
                print(f"PDF 加载异常：{e}")
                chunks = None

            if not chunks:  # 提取失败或内容为空
                temp_file.unlink()  # 清理临时文件
                return jsonify({
                    'error': 'Empty PDF content',
                    'message': '无法从 PDF 中提取文本内容。若您的简历为扫描件或图片，请直接上传图片文件。'
                }), 400
        else:
            # 图片：调用 OCR 识别文字
            try:
                from ocr_utils import recognize_image  # 动态导入，避免循环依赖
                recognized_text = recognize_image(str(temp_file))
                if not recognized_text or not recognized_text.strip():
                    raise Exception("OCR 识别返回空文本")
                
                # 将识别出的文本包装成 Document 对象
                from langchain.schema import Document
                doc = Document(
                    page_content=recognized_text,
                    metadata={"source": "ocr", "file_name": filename}
                )
                chunks = [doc]  # 目前不切分，后续检索时可由 retriever 处理
                print(f"OCR 识别成功，文本长度：{len(recognized_text)} 字符")
            except Exception as e:
                temp_file.unlink()
                return jsonify({
                    'error': 'OCR failed',
                    'message': f'图片文字识别失败：{str(e)}'
                }), 400

        # ---------- 6. 存储简历数据到内存 ----------
        resume_store[resume_id] = {
            'file_path': str(temp_file),
            'file_name': filename,
            'file_size': file_size,
            'chunks': chunks,
            'uploaded_at': datetime.now()
        }

        # ---------- 7. 返回成功响应 ----------
        return jsonify({
            'success': True,
            'resume_id': resume_id,
            'filename': filename,
            'file_size': file_size,
            'uploaded_at': datetime.now().isoformat()
        }), 200

    except Exception as e:
        # 全局异常捕获
        return jsonify({
            'error': 'Upload failed',
            'message': f'上传失败：{str(e)}'
        }), 500
@app.route('/api/interview/start', methods=['POST'])
def start_interview():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided', 'message': '请提供必要的参数'}), 400
        
        resume_id = data.get('resume_id')  # 可选
        position_name = data.get('position')
        interview_style = normalize_interview_style(data.get('interview_style', 'judge'))
        
        # 验证岗位
        position_info = position_manager.get_position(position_name)
        if not position_info:
            # 获取所有已加载的岗位名称
            available_positions = list(position_manager.positions.keys())
            print(f"收到无效岗位: '{position_name}'，可用岗位: {available_positions}")
            return jsonify({
                'error': 'Invalid position',
                'message': f'不支持的岗位。可用岗位: {", ".join(available_positions)}'
            }), 400
        
        # 验证面试官风格（normalize 已做旧值兼容）
        valid_styles = ['judge', 'random', 'professional', 'guide', 'student']
        if interview_style not in valid_styles:
            interview_style = 'judge'
        
        # 检查并发限制
        if len(session_store) >= 10:
            return jsonify({'error': 'Too many sessions', 'message': '服务器繁忙，请稍后再试'}), 503
        
        # 加载配置和LLM
        config = load_config()
        if config is None:
            return jsonify({'error': 'Configuration error', 'message': '配置加载失败'}), 500
        
        config.set('DEFAULT', 'interview_style', interview_style)
        llm = get_llm(config)
        if llm is None:
            return jsonify({'error': 'LLM initialization failed', 'message': '无法初始化语言模型'}), 500
        
        # 加载简历chunks（如果有）
        resume_chunks = []
        if resume_id and resume_id in resume_store:
            resume_chunks = resume_store[resume_id]['chunks']
        
        # 加载岗位知识库
        kb_paths = position_manager.get_knowledge_base_paths(position_name)
        print(f"[DEBUG] 岗位: {position_name}")
        print(f"[DEBUG] 知识库路径: {kb_paths}")
        print(f"[DEBUG] 路径是否存在: {[p.exists() for p in kb_paths]}")
        knowledge_chunks = load_knowledge_base(kb_paths)
        
        # 创建面试链
        try:
            chain = create_interview_chain(resume_chunks, knowledge_chunks, llm, config, position_info)
        except Exception as e:
            return jsonify({'error': 'Failed to create interview chain', 'message': f'初始化面试失败：{str(e)}'}), 500
        
        # 创建评估链
        eval_chain = create_evaluation_chain(llm)
        
        # 创建会话
        session_id = SessionManager.create_session(resume_id, chain)
        # 扩展会话数据
        session_store[session_id].update({
        'position': position_name,
        'position_info': position_info,
        'eval_chain': eval_chain,
        'evaluations': [],
        'qa_pairs': [],    # [{question, answer, at}] for deferred evaluation/report
        'questions': [],     # 存储用户消息（候选人的回答）
        'answers': [],       # 存储AI消息（面试官的问题）
        'user_id': data.get('user_id', 'anonymous'),
        'resume_chunks': resume_chunks  # 存储简历块
        })
        
        # 生成第一个问题
        # - 有简历：直接基于简历内容提问，避免泛泛的“自我介绍”
        # - 无简历：沿用原有开场
        try:
            resume_context = ""
            if resume_chunks:
                resume_context = "\n".join(
                    [doc.page_content for doc in resume_chunks if getattr(doc, "page_content", None)]
                ).strip()

            if resume_context:
                resume_context = resume_context[:4000]
                first_prompt = get_interview_style_prompt(interview_style, position_info, has_resume=True).format(
                    question_bank=json.dumps(position_info.get('question_bank', []), ensure_ascii=False, indent=2),
                    context=resume_context,
                    chat_history="",
                    question="面试刚开始。请直接基于简历中最相关的一段项目/经历提出第一个问题（不要让候选人泛泛自我介绍），保持专业、简短，只问一个问题。"
                )
                llm_first = llm.invoke(first_prompt)
                first_question = getattr(llm_first, "content", None) or str(llm_first)

                # 写入 chain memory，保证后续对话能引用第一问
                if hasattr(chain, "memory") and getattr(chain, "memory", None) is not None:
                    try:
                        chain.memory.chat_memory.add_ai_message(first_question)
                    except Exception:
                        pass
            else:
                first_prompt = get_interview_style_prompt(interview_style, position_info, has_resume=False).format(
                    question_bank=json.dumps(position_info.get('question_bank', []), ensure_ascii=False, indent=2),
                    context="[RESUME]\n（候选人未提供简历）",
                    chat_history="",
                    question="面试刚开始，候选人未提供简历。请先用一句话自我介绍，然后只问一个问题：请用 1-2 分钟讲你最相关的一段项目/经历（背景、你的职责、技术栈、规模、结果）。"
                )
                llm_first = llm.invoke(first_prompt)
                first_question = getattr(llm_first, "content", None) or str(llm_first)

                if hasattr(chain, "memory") and getattr(chain, "memory", None) is not None:
                    try:
                        chain.memory.chat_memory.add_ai_message(first_question)
                    except Exception:
                        pass

            # 将第一个问题存入 session['answers'] 和 last_question
            session_store[session_id]['answers'].append(first_question)
            session_store[session_id]['last_question'] = first_question  # 用于评估
        except Exception:
            first_question = '你好，我是今天的面试官。让我们开始吧，请先做个自我介绍。'
            session_store[session_id]['answers'].append(first_question)
            session_store[session_id]['last_question'] = first_question
        audio_base64 = ""
        if first_question and _tts_inline_enabled():
            audio_base64 = text_to_speech_base64_cached(first_question)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': first_question,
            'audio': audio_base64,
            'interview_style': interview_style,
            'position': position_name,
            'started_at': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Start interview failed', 'message': f'开始面试失败：{str(e)}'}), 500


@app.route('/api/interview/message', methods=['POST'])
def send_message():
    """发送消息接口"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided', 'message': '请提供必要的参数'}), 400
        
        session_id = data.get('session_id')
        message = data.get('message')
        analysis = data.get('analysis', {})       
        if not session_id:
            return jsonify({
                'error': 'Missing session_id',
                'message': '请提供会话ID'
            }), 400
        
        if not message or not message.strip():
            return jsonify({
                'error': 'Missing message',
                'message': '请提供消息内容'
            }), 400
        
        # 获取会话
        session = SessionManager.get_session(session_id)
        if session:
            session['last_audio_analysis'] = analysis   # 存储供后续评估
        if session is None:
            return jsonify({'error': 'Session not found', 'message': '会话不存在或已过期'}), 404
        
        chain = session.get('chain')
        eval_chain = session.get('eval_chain')
        if chain is None or eval_chain is None:
            return jsonify({'error': 'Interview chain not found', 'message': '面试链不存在'}), 500
        
        try:
            # 获取AI回答
            last_question = session.get('last_question', '')
            response = chain.invoke({
                "question": message,
                "chat_history": [],
                "last_question": last_question,
                "last_answer": message
            })
            answer = response.get('answer', '抱歉，我没有收到回答。')

            # Persist the turn for deferred evaluation/reporting.
            session.setdefault('qa_pairs', []).append({
                "question": last_question,
                "answer": message,
                "at": datetime.now().isoformat()
            })

            audio_base64 = ""
            if answer and _tts_inline_enabled():
                audio_base64 = text_to_speech_base64_cached(answer)
            
            eval_result = None
            if os.getenv("EVAL_EACH_TURN", "0").strip().lower() in ("1", "true", "yes", "on"):
                position_info = session['position_info']
                resume_chunks = session.get('resume_chunks', [])
                resume_context = '\n'.join([doc.page_content for doc in resume_chunks]) if resume_chunks else '无简历'
                eval_result = evaluate_answer(
                    eval_chain,
                    position=position_info['name'],
                    question=last_question,          # 面试官的问题
                    answer=message,                  # 候选人的回答
                    resume_context=resume_context,
                    tech_stack=', '.join(position_info['tech_stack'])
                )
            
            # 存储问答
            session['questions'].append(message)      # 用户消息（候选人的回答）
            session['answers'].append(answer)         # AI消息（面试官的新问题）
            if eval_result is not None:
                session['evaluations'].append(eval_result)
            session['last_question'] = answer          # 更新为下一轮的问题
            session['message_count'] += 1
            
            return jsonify({
                'success': True,
                'response': answer,
                'audio': audio_base64,
                'evaluation': eval_result,
                'session_id': session_id,
                'message_count': session['message_count'],
                'timestamp': datetime.now().isoformat()
            }), 200
            
        except Exception as e:
            return jsonify({'error': 'Failed to get response', 'message': f'获取回答失败：{str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': 'Send message failed', 'message': f'发送消息失败：{str(e)}'}), 500


def _ensure_evaluations_for_report(session: dict):
    """
    Per-turn evaluation is expensive. When EVAL_EACH_TURN is off, we defer evaluation to report generation.
    This function populates session['evaluations'] from stored qa_pairs (limited by EVAL_MAX_TURNS).
    """
    if not session:
        return
    if session.get('evaluations'):
        return

    qa_pairs = session.get('qa_pairs') or []
    if not qa_pairs:
        return

    eval_chain = session.get('eval_chain')
    position_info = session.get('position_info') or {}
    if not eval_chain or not position_info:
        return

    max_turns = int(os.getenv("EVAL_MAX_TURNS", "12"))
    qa_pairs = qa_pairs[-max_turns:]

    resume_chunks = session.get('resume_chunks', [])
    resume_context = '\n'.join([doc.page_content for doc in resume_chunks]) if resume_chunks else '无简历'
    tech_stack = ', '.join(position_info.get('tech_stack') or [])

    session['evaluations'] = []
    for pair in qa_pairs:
        q = pair.get('question') or ''
        a = pair.get('answer') or ''
        if not a.strip():
            continue
        session['evaluations'].append(evaluate_answer(
            eval_chain,
            position=position_info.get('name', 'unknown'),
            question=q,
            answer=a,
            resume_context=resume_context,
            tech_stack=tech_stack
        ))


@app.route('/api/interview/end', methods=['POST'])
def end_interview():
    """结束面试接口"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No data provided',
                'message': '请提供必要的参数'
            }), 400
        
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'error': 'Missing session_id',
                'message': '请提供会话ID'
            }), 400
        
        # 获取会话（先生成报告，再删除会话）
        session = SessionManager.get_session(session_id)
        report = None
        
        if session:
            _ensure_evaluations_for_report(session)
            # 生成最终报告并保存到数据库
            evaluations = session.get('evaluations', [])
            if evaluations:
                # 计算各维度平均分
                avg_scores = {}
                for ev in evaluations:
                    scores = ev.get('scores', {})
                    for k, v in scores.items():
                        avg_scores[k] = avg_scores.get(k, 0) + v
                for k in avg_scores:
                    avg_scores[k] = round(avg_scores[k] / len(evaluations), 2)

                # 聚合高频亮点和不足
                from collections import Counter
                all_strengths = [s for ev in evaluations for s in ev.get('strengths', [])]
                all_weaknesses = [w for ev in evaluations for w in ev.get('weaknesses', [])]
                top_strengths = [item for item, _ in Counter(all_strengths).most_common(3)]
                top_weaknesses = [item for item, _ in Counter(all_weaknesses).most_common(3)]

                # 改进建议
                improvements = list(dict.fromkeys(imp for ev in evaluations for imp in ev.get('improvements', [])))[:5]

                report = {
                    'overall_score': round(sum(avg_scores.values()) / len(avg_scores), 2) if avg_scores else 0,
                    'dimension_scores': avg_scores,
                    'top_strengths': top_strengths,
                    'top_weaknesses': top_weaknesses,
                    'improvement_suggestions': improvements
                }

                # 将报告持久化到数据库
                database.save_interview(
                    user_id=session.get('user_id', 'anonymous'),
                    session_id=session_id,
                    position=session.get('position', 'unknown'),
                    overall_score=report['overall_score'],
                    scores=avg_scores,
                    report=report
                )
        
        # 结束会话
        SessionManager.end_session(session_id)
        
        return jsonify({
            'success': True,
            'message': '面试已结束，感谢您的参与！',
            'session_id': session_id,
            'report': report,  # 返回报告数据
            'ended_at': datetime.now().isoformat()
        }), 200
            
    except Exception as e:
        return jsonify({
            'error': 'End interview failed',
            'message': f'结束面试失败：{str(e)}'
        }), 500

@app.route('/api/interview/report/<session_id>', methods=['GET'])
def get_report(session_id):
    # 优先从数据库获取（因为 end_interview 可能已经保存了）
    db_report = database.get_report_by_session_id(session_id)
    if db_report:
        return jsonify(db_report), 200

    # 如果数据库没有，尝试从内存获取（会话还未结束的情况）
    session = SessionManager.get_session(session_id)
    if session is not None:
        _ensure_evaluations_for_report(session)
        evaluations = session.get('evaluations', [])
        if not evaluations:
            return jsonify({'error': 'No evaluations yet'}), 400

        # 计算各维度平均分
        avg_scores = {}
        for ev in evaluations:
            scores = ev.get('scores', {})
            for k, v in scores.items():
                avg_scores[k] = avg_scores.get(k, 0) + v
        for k in avg_scores:
            avg_scores[k] = round(avg_scores[k] / len(evaluations), 2)

        # 聚合高频亮点和不足
        from collections import Counter
        all_strengths = [s for ev in evaluations for s in ev.get('strengths', [])]
        all_weaknesses = [w for ev in evaluations for w in ev.get('weaknesses', [])]
        top_strengths = [item for item, _ in Counter(all_strengths).most_common(3)]
        top_weaknesses = [item for item, _ in Counter(all_weaknesses).most_common(3)]

        # 改进建议
        improvements = list(dict.fromkeys(imp for ev in evaluations for imp in ev.get('improvements', [])))[:5]

        report = {
            'overall_score': round(sum(avg_scores.values()) / len(avg_scores), 2) if avg_scores else 0,
            'dimension_scores': avg_scores,
            'top_strengths': top_strengths,
            'top_weaknesses': top_weaknesses,
            'improvement_suggestions': improvements
        }

        # 将报告持久化到数据库
        database.save_interview(
            user_id=session.get('user_id', 'anonymous'),
            session_id=session_id,
            position=session.get('position', 'unknown'),
            overall_score=report['overall_score'],
            scores=avg_scores,
            report=report
        )

        return jsonify(report), 200

    # 都找不到则返回404
    return jsonify({'error': 'Report not found'}), 404
@app.route('/api/user/history', methods=['GET'])
def get_user_history():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400
    history = database.get_user_history(user_id)
    return jsonify(history), 200

@app.errorhandler(400)
def bad_request(error):
    """处理 400 错误"""
    return jsonify({
        'error': 'Bad Request',
        'message': str(error),
        'timestamp': datetime.now().isoformat()
    }), 400


@app.route('/api/upload-audio', methods=['POST'])
def upload_audio():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided', 'message': '请上传音频文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected', 'message': '请选择音频文件'}), 400

        audio_id = str(uuid.uuid4())
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'wav'
        temp_file = TEMP_DIR / f"{audio_id}.{ext}"
        file.save(str(temp_file))

        # 1. 调用转录函数
        # audio_utils.transcribe_audio 可能返回：
        # - str：仅转录文本
        # - dict：包含 {"text": "...", "analysis": {...}}
        transcription = transcribe_audio(str(temp_file))

        if isinstance(transcription, dict):
            transcribed_text = transcription.get("text", "") or ""
            analysis = transcription.get("analysis", {}) or {}
        else:
            transcribed_text = transcription
            analysis = analyze_speech(str(temp_file), transcribed_text)

        if not isinstance(transcribed_text, str):
            app.logger.error(f"transcribe_audio 返回了非字符串类型: {type(transcription)}")
            return jsonify({'error': 'Audio processing failed', 'message': '转录返回类型错误'}), 500

        # 确保 analysis 是字典（防御性编程）
        if not isinstance(analysis, dict):
            app.logger.warning(f"analyze_speech 返回了非字典类型: {type(analysis)}，使用默认值")
            analysis = {
                "speaking_rate": 0,
                "pause_frequency": 0,
                "avg_volume": 0,
                "volume_std": 0,
                "avg_pitch": 0,
                "pitch_std": 0,
                "confidence": 0
            }

        temp_file.unlink()
        return jsonify({
            'success': True,
            'text': transcribed_text,
            'analysis': analysis
        }), 200

    except Exception as e:
        app.logger.error(f"音频处理失败: {e}", exc_info=True)
        if 'temp_file' in locals() and temp_file.exists():
            temp_file.unlink()
        return jsonify({
            'error': 'Audio processing failed',
            'message': f'语音处理失败：{str(e)}'
        }), 500
    

@app.errorhandler(404)
def not_found(error):
    """处理 404 错误"""
    return jsonify({
        'error': 'Not Found',
        'message': '请求的资源不存在',
        'timestamp': datetime.now().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """处理 500 错误"""
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(error),
        'timestamp': datetime.now().isoformat()
    }), 500


def run_api_server():
    """启动 API 服务器"""
    print("\n" + "=" * 60)
    print("   Interview API Server")
    print("=" * 60)
    
    # 加载配置
    load_api_config()
    
    # 启动服务器
    print(f"\nAPI 服务器启动中...")
    print(f"监听端口：{api_config['port']}")
    print(f"健康检查：http://localhost:{api_config['port']}/api/health")
    print("\n按 Ctrl+C 停止服务器\n")
    
    app.run(
        host='0.0.0.0',
        port=int(api_config['port']),
        debug=False,
        threaded=True
    )
@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    user_id = request.args.get('user_id')
    position = request.args.get('position')
    if not user_id or not position:
        return jsonify({'error': 'Missing user_id or position'}), 400

    # 获取用户历史面试记录
    history = database.get_user_history(user_id)
    if not history:
        return jsonify([]), 200

    # 取最近一次面试的维度得分
    last = history[-1]
    scores = last.get('scores', {})  # 例如 {'technical_accuracy': 2.8, 'depth': 3.5, ...}

    # 英文 → 中文维度映射
    dimension_map = {
        'technical_accuracy': '技术正确性',
        'depth': '知识深度',
        'logic': '逻辑严谨性',
        'fit': '岗位匹配度',
        'communication': '沟通表达'
    }

    # 提取得分低于 3 分的维度（转为中文）
    weak_items = []
    for eng_dim, score in scores.items():
        if score < 3 and eng_dim in dimension_map:
            weak_items.append(dimension_map[eng_dim])

    if not weak_items:
        return jsonify([]), 200

    # 调用推荐函数（传入中文薄弱维度）
    raw_resources = recommend_resources(position, weak_items)

    # 将字段名转换为前端需要的格式
    formatted_resources = []
    for r in raw_resources:
        formatted_resources.append({
            'title': r.get('name', ''),
            'link': r.get('url', '#'),
            'type': r.get('type', '其他'),
            'reason': r.get('reason', '')
        })

    return jsonify(formatted_resources), 200

@app.route('/api/export/pdf', methods=['GET'])
def export_pdf():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    history = database.get_user_history(user_id)
    if not history:
        return jsonify({'error': 'No data to export'}), 404

    # ---------- 注册中文字体 ----------
    # 请根据实际字体路径修改，以下为 Windows 黑体示例
    font_path = "C:/Windows/Fonts/simhei.ttf"  # 或使用项目内字体，如 "./fonts/simhei.ttf"
    try:
        pdfmetrics.registerFont(TTFont('SimHei', font_path))
        chinese_font = 'SimHei'
    except:
        # 如果字体文件不存在，回退到默认字体（中文仍无法显示，但至少不报错）
        chinese_font = 'Helvetica'
        print("警告：中文字体加载失败，PDF 中文字符将无法显示。")

    # 创建支持中文的样式
    styles = getSampleStyleSheet()
    # 修改标题样式，使用中文字体
    styles['Title'].fontName = chinese_font
    # 创建用于普通段落的样式
    chinese_style = ParagraphStyle(
        'ChineseStyle',
        parent=styles['Normal'],
        fontName=chinese_font,
        fontSize=10,
        leading=14,
    )
    # ---------- 字体注册结束 ----------

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    elements = []

    # 标题（已应用中文字体）
    elements.append(Paragraph("Interview 面试历史报告", styles['Title']))
    elements.append(Spacer(1, 12))

    # 表格数据（表头为中文）
    data = [['日期', '岗位', '综合评分', '技术正确性', '知识深度', '逻辑严谨性', '岗位匹配度', '沟通表达']]
    for record in history:
        scores = record.get('scores', {})
        data.append([
            record['date'][:10],
            record['position'],
            f"{record['overall_score']:.1f}",
            f"{scores.get('technical_accuracy', 0):.1f}",
            f"{scores.get('depth', 0):.1f}",
            f"{scores.get('logic', 0):.1f}",
            f"{scores.get('fit', 0):.1f}",
            f"{scores.get('communication', 0):.1f}"
        ])

    table = Table(data, repeatRows=1)
    # 设置表格样式，所有文字使用中文字体
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), chinese_font),  # 关键：指定所有单元格使用中文字体
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('FONTSIZE', (0,1), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()

    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=interview_history_{datetime.now().strftime("%Y%m%d")}.pdf'
    return response



if __name__ == '__main__':
    run_api_server()
