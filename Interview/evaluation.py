import json
from langchain.prompts import PromptTemplate


# 评估提示词模板
EVALUATION_TEMPLATE = """
你是一位专业的面试评估专家。请根据以下信息对候选人的回答进行多维度评分。

岗位：{position}
问题：{question}
候选人的回答：{answer}
简历内容（如有）：{resume_context}
岗位要求技术栈：{tech_stack}

请从以下维度评分（1-5分）：
1. 技术正确性：回答是否准确，是否有错误。
2. 知识深度：是否展示了深入理解，还是停留在表面。
3. 逻辑严谨性：回答结构是否清晰，论证是否合理。
4. 岗位匹配度：回答是否体现了岗位所需的核心能力。
5. 沟通表达：语言是否流畅，能否清晰传达想法。

另外，请提供：
- 亮点总结（最多2点）
- 不足分析（最多2点）
- 具体改进建议（针对不足）

请以JSON格式输出，例如：
{{
  "scores": {{
    "technical_accuracy": 4,
    "depth": 3,
    "logic": 5,
    "fit": 4,
    "communication": 4
  }},
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "improvements": ["...", "..."]
}}
"""

def create_evaluation_chain(llm):
    prompt = PromptTemplate(
        template=EVALUATION_TEMPLATE,
        input_variables=["position", "question", "answer", "resume_context", "tech_stack"]
    )
    chain =prompt | llm
    return chain

def evaluate_answer(chain, position, question, answer, resume_context, tech_stack):
    """调用评估链，返回解析后的评估结果"""
    result = chain.invoke({
        "position": position,
        "question": question,
        "answer": answer,
        "resume_context": resume_context,
        "tech_stack": tech_stack
    })
    evaluation_text = result.content  # 获取生成的文本
    # 尝试解析JSON
    try:
        # 查找JSON部分（有时LLM会输出额外文字）
        start = evaluation_text.find('{')
        end = evaluation_text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = evaluation_text[start:end]
            eval_data = json.loads(json_str)
        else:
            eval_data = {"scores": {}, "strengths": [], "weaknesses": [], "improvements": []}
    except:
        eval_data = {"scores": {}, "strengths": [], "weaknesses": [], "improvements": []}
    return eval_data