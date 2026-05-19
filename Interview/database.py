import json
from datetime import datetime
from pathlib import Path

DB_FILE = Path(__file__).parent / "interview_history.json"

def init_db():
    """初始化 JSON 文件（如果不存在则创建空列表）"""
    if not DB_FILE.exists():
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def save_interview(user_id, session_id, position, overall_score, scores, report):
    """保存或更新一次面试记录"""
    init_db()
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        records = json.load(f)

    # 查找是否已存在相同 session_id
    updated = False
    for rec in records:
        if rec['session_id'] == session_id:
            rec.update({
                'user_id': user_id,
                'position': position,
                'date': datetime.now().isoformat(),
                'overall_score': overall_score,
                'scores': scores,          # 直接保存字典，前端直接使用
                'report': report
            })
            updated = True
            break
    if not updated:
        records.append({
            'user_id': user_id,
            'session_id': session_id,
            'position': position,
            'date': datetime.now().isoformat(),
            'overall_score': overall_score,
            'scores': scores,
            'report': report
        })

    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def get_user_history(user_id):
    """获取某个用户的所有面试历史（按日期升序）"""
    init_db()
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        records = json.load(f)
    user_records = [r for r in records if r['user_id'] == user_id]
    # 按日期排序
    user_records.sort(key=lambda x: x['date'])
    # 返回前端需要的字段（剔除 report 等大字段）
    return [{
        'date': r['date'],
        'position': r['position'],
        'overall_score': r['overall_score'],
        'scores': r['scores']
    } for r in user_records]

def get_report_by_session_id(session_id):
    """根据 session_id 获取完整的报告"""
    init_db()
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        records = json.load(f)
    for rec in records:
        if rec['session_id'] == session_id:
            return rec.get('report')
    return None