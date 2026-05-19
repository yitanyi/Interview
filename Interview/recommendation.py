import json
from pathlib import Path

# 学习资源库文件（可根据需要创建）
RESOURCE_FILE = Path(__file__).parent / "learning_resources.json"

def load_resources():
    if not RESOURCE_FILE.exists():
        # 创建一个默认资源文件
        default = {
            "Java后端开发工程师": {
                "技术知识点": [
                    {"name": "JVM内存模型", "url": "https://example.com/jvm", "type": "文章"}
                ],
                "沟通技巧": [
                    {"name": "STAR原则回答行为面试题", "url": "https://example.com/star"}
                ]
            },
            "Web前端开发工程师": {
                "技术知识点": [
                    {"name": "浏览器渲染原理", "url": "https://example.com/rendering"}
                ]
            },
            "Python算法工程师": {
                "技术知识点": [
                    {"name": "机器学习正则化", "url": "https://example.com/regularization"}
                ]
            }
        }
        with open(RESOURCE_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(RESOURCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def recommend_resources(position, weaknesses):
    """
    weaknesses: list of 薄弱维度名称，如 ['技术正确性', '沟通表达']
    """
    resources = load_resources()
    pos_res = resources.get(position, {})
    recommendations = []

    # 维度到资源类型的映射规则
    mapping = {
    '技术正确性': ['技术知识点'],          # 原为 ['技术知识点', '常见面试题']
    '知识深度': ['技术知识点'],            # 原为 ['技术知识点', '进阶文章']
    '逻辑严谨性': ['技术知识点'],          # 原为 ['逻辑思维', '系统设计']
    '岗位匹配度': ['技术知识点'],          # 原为 ['岗位匹配', '技能清单']
    '沟通表达': ['沟通技巧']    
    }

    for weak in weaknesses:
        for target_type in mapping.get(weak, []):
            recs = pos_res.get(target_type, [])
            for rec in recs:
                rec_copy = rec.copy()
                rec_copy['reason'] = f'针对“{weak}”薄弱项推荐'
                recommendations.append(rec_copy)

    # 去重（基于name）
    seen = set()
    unique_recs = []
    for r in recommendations:
        if r['name'] not in seen:
            seen.add(r['name'])
            unique_recs.append(r)

    return unique_recs[:5]  # 最多返回5条