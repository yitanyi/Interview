"""
OCR 工具：百度智能云通用文字识别（高精度版）
"""
import base64
import json
import configparser
import time
import os
from pathlib import Path
from typing import Optional
import requests

def load_baidu_config():
    """从 config.ini 读取百度 OCR 配置"""
    config = configparser.ConfigParser()
    config_path = Path(__file__).parent / "config.ini"
    if not config_path.exists():
        raise Exception("config.ini 不存在")
    config.read(config_path, encoding='utf-8')
    try:
        api_key = config.get('baidu_ocr', 'api_key')
        secret_key = config.get('baidu_ocr', 'secret_key')
        token_cache = config.get('baidu_ocr', 'token_cache', fallback='./baidu_ocr_token.json')
        return api_key, secret_key, token_cache
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        raise Exception(f"请在 config.ini 中配置 [baidu_ocr] 部分: {e}")


def get_baidu_token(api_key: str, secret_key: str, token_cache_path: str) -> str:
    """
    获取百度 OCR access_token，支持本地缓存（有效期30天）
    """
    cache_file = Path(token_cache_path)
    
    # 检查缓存是否存在且未过期（提前1天刷新）
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                if cache.get('expires_at', 0) > time.time() + 86400:  # 提前1天刷新
                    return cache['access_token']
        except:
            pass
    
    # 重新获取 token
    auth_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
    
    try:
        response = requests.post(auth_url, timeout=10)
        result = response.json()
        
        if 'access_token' not in result:
            error_msg = result.get('error_description', '未知错误')
            raise Exception(f"获取百度 token 失败: {error_msg}")
        
        access_token = result['access_token']
        expires_in = result.get('expires_in', 2592000)  # 默认30天
        
        # 缓存 token
        cache_data = {
            'access_token': access_token,
            'expires_at': time.time() + expires_in,
            'created_at': time.time()
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"请求百度 token 服务失败: {e}")


def recognize_image(image_path: str, extra_params: dict = None) -> str:
    """
    调用百度智能云通用文字识别（高精度版）识别图片中的文字
    
    Args:
        image_path: 图片文件路径
        extra_params: 可选参数，如 detect_direction（是否检测朝向）等
    
    Returns:
        识别出的文本字符串（按行用 \n 连接）
    """
    api_key, secret_key, token_cache = load_baidu_config()
    access_token = get_baidu_token(api_key, secret_key, token_cache)
    
    # 百度高精度版 API 地址
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={access_token}"
    
    # 读取图片并转 base64（百度要求去掉头部前缀）
    with open(image_path, 'rb') as f:
        img_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    # 检查图片大小（百度限制：base64编码后不超过4M）
    if len(img_base64) > 4 * 1024 * 1024:
        raise Exception("图片过大，百度 OCR 要求 base64 编码后不超过 4MB，请压缩图片")
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    
    payload = {
        'image': img_base64,
        'detect_direction': 'true',  # 自动检测旋转角度并纠正
        'probability': 'false',      # 不需要置信度（节省流量）
    }
    
    # 合并额外参数
    if extra_params:
        payload.update(extra_params)
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        result = response.json()
        
        # 错误处理
        if 'error_code' in result:
            error_code = result['error_code']
            error_msg = result.get('error_msg', '未知错误')
            
            # token 过期自动重试一次
            if error_code in [110, 111]:  # 110:token失效, 111:token过期
                os.remove(token_cache)  # 删除缓存
                access_token = get_baidu_token(api_key, secret_key, token_cache)  # 重新获取
                url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={access_token}"
                response = requests.post(url, data=payload, headers=headers, timeout=30)
                result = response.json()
                
                if 'error_code' in result:
                    raise Exception(f"百度 OCR 错误 [{result['error_code']}]: {result.get('error_msg')}")
            else:
                raise Exception(f"百度 OCR 错误 [{error_code}]: {error_msg}")
        
        # 解析结果
        words_result = result.get('words_result', [])
        if not words_result:
            return ""
        
        # 提取文字（按行）
        lines = [item.get('words', '').strip() for item in words_result if item.get('words')]
        return '\n'.join(lines)
        
    except requests.exceptions.Timeout:
        raise Exception("百度 OCR 请求超时（30秒），请检查网络或稍后重试")
    except requests.exceptions.RequestException as e:
        raise Exception(f"百度 OCR 网络请求失败: {e}")
