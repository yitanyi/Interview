# -*- coding: utf-8 -*-
"""
简历拷打面试官 - Interview
基于 RAG 技术的模拟面试对话系统
支持 DeepSeek 和 Google Gemini API
"""
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import hashlib
from collections import OrderedDict
from typing import Optional

from langchain.prompts import PromptTemplate
import uuid
import json
import sys
import configparser
from pathlib import Path
from position_manager import PositionManager
from knowledge_loader import load_knowledge_base
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

from langchain.chains.llm import LLMChain
from langchain_core.messages import HumanMessage, AIMessage


# Cache vectorstores to avoid re-embedding the same knowledge base / resume repeatedly.
# This is the main lever to speed up "面试官已就绪".
_VECTORSTORE_CACHE: "OrderedDict[str, Chroma]" = OrderedDict()


def _docs_fingerprint(docs) -> str:
    """
    Best-effort fingerprint for a list of Documents.
    Uses (source path + mtime) when available; falls back to lengths.
    """
    sources = []
    for d in docs or []:
        try:
            src = (getattr(d, "metadata", {}) or {}).get("source")
            if src:
                p = Path(str(src))
                if p.exists():
                    sources.append(f"{p.resolve()}@{p.stat().st_mtime_ns}")
                else:
                    sources.append(str(src))
        except Exception:
            continue

    if sources:
        raw = "\n".join(sorted(set(sources))).encode("utf-8", errors="ignore")
    else:
        raw = f"len={len(docs or [])}".encode("utf-8", errors="ignore")

    return hashlib.sha1(raw).hexdigest()


def _get_or_create_vectorstore(docs, embeddings, namespace: str, max_items: int) -> Optional[Chroma]:
    if not docs:
        return None
    fp = _docs_fingerprint(docs)
    key = f"{namespace}:{fp}"

    hit = _VECTORSTORE_CACHE.get(key)
    if hit is not None:
        _VECTORSTORE_CACHE.move_to_end(key)
        return hit

    # Deterministic collection name so debugging is easier; the cache key keeps it unique.
    collection_name = f"{namespace}_{fp[:12]}"
    vs = Chroma.from_documents(documents=docs, embedding=embeddings, collection_name=collection_name)

    _VECTORSTORE_CACHE[key] = vs
    _VECTORSTORE_CACHE.move_to_end(key)
    while len(_VECTORSTORE_CACHE) > max_items:
        _VECTORSTORE_CACHE.popitem(last=False)
    return vs


class _MergedRetriever:
    """Merge results from multiple retrievers; keep it simple for speed."""

    def __init__(self, retrievers, k: int = 3):
        self.retrievers = [r for r in (retrievers or []) if r is not None]
        self.k = k

    def get_relevant_documents(self, query: str):
        docs = []
        seen = set()
        for r in self.retrievers:
            try:
                for d in r.get_relevant_documents(query):
                    key = (getattr(d, "page_content", ""), json.dumps(getattr(d, "metadata", {}) or {}, ensure_ascii=False, sort_keys=True))
                    if key in seen:
                        continue
                    seen.add(key)
                    docs.append(d)
            except Exception:
                continue
        return docs[: self.k]

    async def aget_relevant_documents(self, query: str):
        # Fallback to sync path; used only if an async chain is introduced later.
        return self.get_relevant_documents(query)


class FastInterviewChain:
    """
    A faster alternative to ConversationalRetrievalChain:
    - 1 LLM call per turn (no question rephrasing/condense step)
    - compatible with the existing `.invoke({...}) -> {'answer': ...}` usage
    """

    def __init__(self, llm, retriever, answer_prompt: PromptTemplate):
        self.llm = llm
        self.retriever = retriever
        self.answer_prompt = answer_prompt
        self.chat_history = []  # [HumanMessage, AIMessage, ...]

    def invoke(self, inputs: dict):
        question = (inputs.get("question") or "").strip()
        last_question = inputs.get("last_question") or ""
        last_answer = inputs.get("last_answer") or ""

        # Retrieval query: include the last Q/A to help grounding without an extra LLM call.
        query = question
        if last_question or last_answer:
            query = f"{last_question}\n{last_answer}\n{question}".strip()

        docs = self.retriever.get_relevant_documents(query) if self.retriever else []
        context = "\n\n".join([getattr(d, "page_content", "") for d in docs]).strip()

        prompt_text = self.answer_prompt.format(
            context=context,
            chat_history=_format_chat_history(self.chat_history),
            question=question,
            last_question=last_question,
            last_answer=last_answer
        )

        result = self.llm.invoke(prompt_text)
        answer = getattr(result, "content", None) or str(result)

        # Update memory for the next turn.
        self.chat_history.append(HumanMessage(content=question))
        self.chat_history.append(AIMessage(content=answer))
        return {"answer": answer}

def _format_chat_history(chat_history):
    """将消息列表转换为字符串，格式如 'Human: xxx\nAI: xxx'"""
    formatted = []
    for msg in chat_history:
        prefix = "Human" if msg.type == "human" else "AI"
        formatted.append(f"{prefix}: {msg.content}")
    return "\n".join(formatted)

def load_config():
    """加载配置文件"""
    config = configparser.ConfigParser()
    config_path = Path(__file__).parent / "config.ini"
    
    if not config_path.exists():
        print("错误：找不到 config.ini 配置文件！")
        return None
    
    config.read(config_path, encoding='utf-8')
    return config


def normalize_interview_style(style: Optional[str]) -> str:
    """
    统一/兼容面试风格 key。

    新风格：
    - judge        审判型
    - random       随缘型
    - professional 专业型
    - guide        引导型
    - student      校园友好型
    """
    if not style:
        return "judge"

    s = str(style).strip().lower()
    alias = {
        
      
        # 常见别名
        "judgement": "judge",
        "judgment": "judge",
        "judge": "judge",
        "random": "random",
        "casual": "random",
        "guide": "guide",
        "student": "student",
        "professional": "professional",
    }
    return alias.get(s, "judge")


def print_banner(style: str = "judge"):
    """打印欢迎横幅"""
    style = normalize_interview_style(style)
    style_info = {
        'judge': '我是审判型面试官：我会像法官一样抓证据、抓细节、抓逻辑。',
        'random': '我是随缘型面试官：节奏放松，但会顺着你的回答自然追问。',
        'professional': '我是专业型面试官：结构化评估、标准流程、重点明确。',
        'guide': '我是引导型面试官：我会循序渐进地帮你把思路讲清楚。',
        'student': '我是校园友好型面试官：问题更基础、鼓励更多，帮你逐步建立自信。'
    }
    
    print("\n" + "=" * 50)
    print("   简历拷打面试官 - Interview")
    print("=" * 50)
    print(f"   {style_info.get(style, style_info['judge'])}")
    print("=" * 50 + "\n")


def get_llm(config):
    """根据配置创建 LLM"""
    provider = config.get('DEFAULT', 'provider').lower()
    
    if provider == 'deepseek':
        from langchain_openai import ChatOpenAI
        api_key = config.get('deepseek', 'api_key')
        base_url = config.get('deepseek', 'base_url')
        model = config.get('deepseek', 'model')
        
        if api_key == 'your-deepseek-api-key':
            print("错误：请在 config.ini 中配置 DeepSeek API Key！")
            print("申请地址：https://platform.deepseek.com/api_keys")
            return None
        
        print(f"使用 DeepSeek API，模型：{model}")
        return ChatOpenAI(
            model_name=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=0.7
        )
    
    elif provider == 'google':
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = config.get('google', 'api_key')
        model = config.get('google', 'model')
        
        if api_key == 'your-google-api-key':
            print("错误：请在 config.ini 中配置 Google API Key！")
            print("申请地址：https://aistudio.google.com/apikey")
            return None
        
        print(f"使用 Google Gemini API，模型：{model}")
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7,
            convert_system_message_to_human=True
        )
    
    else:
        print(f"错误：不支持的 API 提供商 '{provider}'")
        print("请在 config.ini 中设置 provider = deepseek 或 google")
        return None


def get_resume_path():
    """获取简历文件路径"""
    print("请输入简历 PDF 文件路径（可直接拖拽文件到此窗口）：")
    path = input("> ").strip().strip('"').strip("'")
    
    if not path:
        print("未输入文件路径")
        return None
    
    path = Path(path)
    if not path.exists():
        print(f"文件不存在：{path}")
        return None
    
    if path.suffix.lower() != ".pdf":
        print("请提供 PDF 格式的简历文件")
        return None
    
    return path


def load_resume(pdf_path: Path):
    """加载并处理简历"""
    print(f"\n正在加载简历：{pdf_path.name}")
    
    loader = PyPDFLoader(str(pdf_path))
    documents = loader.load()
    
    if not documents:
        print("无法读取简历内容")
        return None
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "；", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    
    print(f"简历已加载，共 {len(chunks)} 个文本块")
    return chunks


def _tag_documents(docs, tag: str):
    """Prefix each document's page_content with a stable tag like [RESUME] / [KB]."""
    if not docs:
        return []
    prefix = f"[{tag}]"
    for doc in docs:
        try:
            content = getattr(doc, "page_content", "") or ""
            if not content.lstrip().startswith(prefix):
                doc.page_content = f"{prefix}\n{content}"
        except Exception:
            continue
    return docs


def get_interview_style_prompt(style: str, position_info: dict = None, has_resume: bool = True) -> str:
    """
    根据面试风格返回对应的系统提示词
    :param style: 'judge', 'random', 'professional', 'guide', 'student'
    :param position_info: 岗位信息字典，包含 name, tech_stack, question_bank 等
    :return: 格式化后的提示模板
    """
    style = normalize_interview_style(style)
    # 岗位信息字符串
    position_str = f"你正在面试一个应聘【{position_info['name']}】岗位的候选人。该岗位要求的技术栈包括：{', '.join(position_info['tech_stack'])}。"
    question_bank_hint = "以下是一个题库（仅作备用）。请优先围绕候选人刚刚的回答与简历细节进行追问；只有在信息不足或需要切换话题时，才从题库中选择问题。题库：\n{question_bank}\n"

    # 公共约束：禁止虚构简历内容
    common_constraint = """
重要：
0) 你刚问过的问题不需要重复输出；如果候选人还没回答或回答不完整，改成澄清/扩展问题，而不是重新抛出上一题本身。
1) 你的提问必须严格基于简历内容。只有当某项技术或项目明确出现在简历中时，才能说“我从你的简历中看到...”。如果简历中未提及，请直接询问候选人是否有相关经验，不要说“简历中提到”。
2) 每一轮提问前，先从候选人上一条回答中抓住一个具体点（技术细节/数据/取舍/踩坑/结果）再追问；若信息不足，先问澄清问题，不要突然跳题。
3) 禁止脑补候选人说过的话：除非原文出现在“对话历史/候选人回答”里，否则不要使用“我看到你提到了/你刚才说了/你表示”等表述；如需引用，使用引号逐字引用候选人的原句。
4) 如果候选人回答很短或表示“不会/不知道/不清楚/忘了”，不要继续按原问题硬追。请按顺序：
   a) 先确认：是否真的做过该经历/是否愿意改为讲大概思路；
   b) 给 2-3 个可选方向或提示（例如：数据处理/特征/模型/训练/评估）让对方选择；
   c) 将问题降级为 1 个更具体、更容易回答的小问题（只问一个）。
"""

    resume_kb_guard = (
        "\n补充约束（资料标记）：\n"
        "- 资料片段里以 [RESUME] 开头的才是候选人简历；以 [KB] 开头的是岗位/通用知识库，不代表候选人做过或说过。\n"
        "- 严禁把 [KB] 当作候选人经历来提问或复述；不得出现“看到你的简历里…”“你提到…”等表述，除非引用的是 [RESUME] 或对话历史原文。\n"
        + ("- 候选人未提供简历：本轮不要要求“简历细节”，改为基于对话历史与岗位要求提问；先问候选人最相关的一段项目/经历，再逐步深挖细节。\n" if not has_resume else "")
    )

    styles = {
        'judge': position_str + question_bank_hint + common_constraint + resume_kb_guard + """你是一位“审判型”技术面试官：你像法官一样严谨审视证据与因果链，擅长交叉质询，专抓细节、边界与取舍。你的任务是根据候选人的简历内容和岗位要求，进行高强度但依然专业、尊重的技术面试。

面试风格：
1. 你必须“抓证据”：只基于简历与候选人原话提问，抓住他刚说的某个点继续追问
2. 你会“追因果”：每个问题都要逼近“为什么这么做/权衡是什么/失败场景是什么/如何验证”
3. 你会“挖边界”：问清楚规模、约束、SLA、数据量、延迟、成本、可观测性、回滚与兜底
4. 回答模糊时，先让候选人给出一个可检验的结论，再要求补证据（日志/指标/实验/对比）
5. 可以简短肯定，但不放过关键空白点；语气锋利但不人身攻击

资料片段（[RESUME]=简历，[KB]=知识库）：
{context}

对话历史：
{chat_history}

候选人回答：{question}

请根据简历内容和对话历史，继续面试。如果是面试刚开始，请先用一句话表明“我会像审判一样严谨”，然后直接基于简历提出第一个问题。**请每次只提出一个问题，保持简洁，不要一次性问多个问题或输出过长内容。**""",

        'random': position_str + question_bank_hint + common_constraint + resume_kb_guard + """你是一位“随缘型”技术面试官：你不刻意施压，更多顺着候选人的表达自然延展话题；但你依然会对关键技术点追问到能落地的程度。你的任务是根据候选人的简历内容，进行轻松但有效的技术面试。

面试风格：
1. 先让候选人“选赛道”：从最有把握的项目/技术点开始聊，再逐步下钻
2. 问题更像聊天式探究：多用“你当时怎么想的/你会怎么取舍/你会怎么验证”这种开放式提问
3. 遇到回答很空时，给 2-3 个方向让候选人挑一个继续（例如：性能/稳定性/成本/可观测性）
4. 不用强共情话术，也不装熟；保持轻松、自然、尊重
5. 关键节点仍要落地：至少追问到“方案 + 代价 + 验证方式”

资料片段（[RESUME]=简历，[KB]=知识库）：
{context}

对话历史：
{chat_history}

候选人回答：{question}

请根据简历内容和对话历史，继续面试。如果是面试刚开始，请用一句话说明“我们随便聊聊，但我会顺着细节追问”，然后开始第一个问题。**请每次只提出一个问题，保持简洁，不要一次性问多个问题或输出过长内容。**""",

        'professional': position_str + question_bank_hint + common_constraint + resume_kb_guard + """你是一位“专业型”技术面试官：你遵循标准面试流程，结构化评估候选人的能力，问题清晰、节奏稳定、结论导向。你的任务是根据候选人的简历内容和岗位要求，进行高质量、可量化的技术面试。

面试风格：
1. 以“岗位胜任力”为目标提问：先确认职责范围，再评估关键能力（设计/编码/性能/稳定性/排障/协作）
2. 提问结构：背景澄清 → 方案/实现 → 权衡取舍 → 结果与指标 → 复盘与改进
3. 对回答做轻量总结，然后提出下一个更聚焦的问题（不要长篇输出）
4. 发现风险点时，优先问“如何验证/如何监控/如何回滚/如何兜底”
5. 语气正式、专业、简洁，不玩梗、不情绪化

资料片段（[RESUME]=简历，[KB]=知识库）：
{context}

对话历史：
{chat_history}

候选人回答：{question}

请根据简历内容和对话历史，继续面试。如果是面试刚开始，请先用一句话说明“我会按标准流程评估”，然后直接提出第一个问题。**请每次只提出一个问题，保持简洁，不要一次性问多个问题或输出过长内容。**""",

        'guide': position_str + question_bank_hint + common_constraint + resume_kb_guard + """你是一位冷静理智、内心宽和的引导型面试官。你的任务是根据候选人的简历内容，通过巧妙的引导帮助候选人展现最佳状态。

面试风格：
1. 保持冷静、理智、审慎的专业态度，给人以可靠和值得信赖的感觉
2. 善于通过循序渐进的问题引导候选人深入思考，比如"我们先从整体架构聊起，然后再深入细节，你觉得如何？"
3. 当候选人回答不够清晰时，不是直接质疑，而是提供思路提示，比如"你可以从技术选型、实现难点、优化方案这几个角度来谈谈"
4. 用开放式问题激发候选人的思考，给予充分的表达空间
5. 内心宽和，对候选人的不足保持理解和包容，但会温和地指出改进方向
6. 善于总结和提炼候选人的观点，帮助其理清思路

资料片段（[RESUME]=简历，[KB]=知识库）：
{context}

对话历史：
{chat_history}

候选人回答：{question}

请根据简历内容和对话历史，继续面试。如果是面试刚开始，请先沉稳地介绍自己，然后以引导的方式开启对话。**请每次只提出一个问题，保持简洁，不要一次性问多个问题或输出过长内容。**""",
        'student': position_str + question_bank_hint + common_constraint + resume_kb_guard + """你是一位面向大学生的温柔型面试官。你的任务是基于候选人现阶段的学习和实践，温柔地引导他展示基础能力与学习潜力，避免让他面对过多高门槛工程化问题。

面试风格：
1. 选择题库中偏 Easy/Medium、与数据结构、算法基础、面向对象、HTTP/数据库、简单项目或课程任务相关的题，避免分布式、大规模性能/可用性/运维等工程化问题。
2. 每个问题最多问 1-2 层，先问思路再问具体做法。如果候选人卡住，鼓励他先复述自己理解的部分，再提供提示或示例帮助他沿着基础概念推导自己的答案。
3. 更多关注候选人的课程、实习或小型项目经历，可以问“这个项目的挑战是什么”、“你在里面负责哪部分”、“学到了哪些工具或方法”来了解他的学习方式。
4. 语言语气友善、鼓励，可以说“慢慢说”“你可以把实现拆成几步讲清楚”，避免让他感到被质问；碰到专业术语时，适当解释下意思。
5. 只需关注问题的思路和因果，不要深入难懂的工程实施细节；如果不得不涉及高级概念，提醒“只要谈原理即可”并帮他回到基础层面。
6. 适当邀请候选人做小结或提出问题，比如“你认为还有什么可以优化的地方？”，观察是否有反思和延展能力。

资料片段（[RESUME]=简历，[KB]=知识库）：
{context}

对话历史：
{chat_history}

候选人回答：{question}

请根据简历和对话，再提出一个温柔、容易回答的问题或引导语。面试刚开始时，可先用一句“你好，我是...，今天我们先聊聊你的学校项目/课程经历”开启对话。**每次只提一个问题，保持简洁，不要一次性问多个问题或写出过长的内容。**"""
    }

    follow_up_hint = """
上一次面试官的问题：{last_question}
候选人的上一条回答：{last_answer}
请基于上述信息继续提问，不要重复“{last_question}”，优先追问候选人刚才的回答细节，只提出一个新的问题即可。
"""

    for k in styles:
        styles[k] = styles[k] + follow_up_hint

    return styles.get(style, styles['judge'])


def create_interview_chain(resume_chunks, knowledge_chunks, llm, config, position_info):
    print("正在初始化面试官大脑...")

    # Tag docs so the model can distinguish resume vs knowledge base.
    resume_chunks = _tag_documents(resume_chunks or [], "RESUME")
    knowledge_chunks = _tag_documents(knowledge_chunks or [], "KB")

    # Embeddings are expensive to load; cache the embedding model across sessions.
    global _EMBEDDINGS_CACHE
    try:
        _EMBEDDINGS_CACHE
    except NameError:
        _EMBEDDINGS_CACHE = {}

    embedding_type = config.get('embedding', 'type', fallback='local')
    embedding_model = config.get('embedding', 'model', fallback='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    cache_key = (embedding_type, embedding_model)

    if cache_key in _EMBEDDINGS_CACHE:
        embeddings = _EMBEDDINGS_CACHE[cache_key]
    else:
        if embedding_type == 'deepseek':
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(
                model=embedding_model or 'text-embedding-3-small',
                openai_api_key=config.get('deepseek', 'api_key'),
                openai_api_base=config.get('deepseek', 'base_url')
            )
        else:
            from langchain_huggingface import HuggingFaceEmbeddings
            # Allow overriding device (cpu/cuda) if the environment supports it.
            emb_device = os.getenv("EMBEDDINGS_DEVICE", "cpu").strip() or "cpu"
            embeddings = HuggingFaceEmbeddings(
                model_name=embedding_model,
                model_kwargs={'device': emb_device}
            )
        _EMBEDDINGS_CACHE[cache_key] = embeddings

    # Vectorstores (cached): avoid re-embedding the same KB/resume on every new session.
    cache_max = int(os.getenv("VECTORSTORE_CACHE_MAX", "8"))
    kb_vs = _get_or_create_vectorstore(knowledge_chunks, embeddings, namespace="kb", max_items=cache_max)
    resume_vs = _get_or_create_vectorstore(resume_chunks, embeddings, namespace="resume", max_items=cache_max)

    retrievers = []
    k = int(os.getenv("RETRIEVER_K", "3"))
    if resume_vs is not None:
        retrievers.append(resume_vs.as_retriever(search_kwargs={"k": k}))
    if kb_vs is not None:
        retrievers.append(kb_vs.as_retriever(search_kwargs={"k": k}))

    retriever = retrievers[0] if len(retrievers) == 1 else _MergedRetriever(retrievers, k=k)

    use_fast = os.getenv("USE_FAST_CHAIN", "1").strip().lower() not in ("0", "false", "no", "off")

    # Legacy chain needs LangChain memory; the fast chain keeps its own lightweight history.
    memory = None
    if not use_fast:
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="question",
            output_key="answer"
        )

    # 获取面试风格和提示模板
    interview_style = normalize_interview_style(config.get('DEFAULT', 'interview_style', fallback='judge'))
    system_template = get_interview_style_prompt(interview_style, position_info, has_resume=bool(resume_chunks))

    # 主回答 prompt
    answer_prompt = PromptTemplate(
        template=system_template,
        input_variables=["context", "chat_history", "question", "position", "tech_stack", "question_bank", "last_question", "last_answer"]
    )

    # ---------- 问题压缩 prompt ----------
    condense_question_prompt = PromptTemplate.from_template(
        "根据以下对话和后续问题，将后续问题改写为一个独立的问题。\n"
        "对话历史：\n{chat_history}\n"
        "后续问题：{question}\n"
        "独立问题："
    )

    answer_prompt = answer_prompt.partial(
        position=position_info['name'],
        tech_stack=", ".join(position_info['tech_stack']),
        question_bank=json.dumps(position_info['question_bank'], ensure_ascii=False, indent=2)
    )

    if use_fast:
        chain = FastInterviewChain(llm=llm, retriever=retriever, answer_prompt=answer_prompt)
    else:
        # Legacy chain: higher quality in some cases but usually slower (extra LLM call per turn).
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            return_source_documents=False,
            combine_docs_chain_kwargs={"prompt": answer_prompt},
            get_chat_history=_format_chat_history,                # ✅ 将列表转为字符串
            condense_question_prompt=condense_question_prompt     # ✅ 使用 prompt 而不是自定义 chain
        )

    print("面试官已就绪！\n")
    return chain


def run_interview(chain):
    """运行面试对话"""
    print("-" * 50)
    print("提示：输入 'quit' 或 'exit' 结束面试")
    print("-" * 50 + "\n")
    
    response = chain.invoke({"question": "请开始面试"})
    print(f"[面试官]：{response['answer']}\n")
    
    while True:
        user_input = input("[你]：").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ["quit", "exit", "退出", "结束"]:
            print("\n[面试官]：好的，今天的面试就到这里。感谢你的时间，我们会尽快给你反馈。再见！")
            break
        
        try:
            response = chain.invoke({"question": user_input})
            print(f"\n[面试官]：{response['answer']}\n")
        except Exception as e:
            print(f"\n出错了：{e}\n")


def main():
    """主函数"""
    # 加载配置
    config = load_config()
    if not config:
        return
    
    # 获取面试官风格
    interview_style = normalize_interview_style(config.get('DEFAULT', 'interview_style', fallback='judge'))
    
    # 打印横幅
    print_banner(interview_style)
    
    # 获取简历路径
    resume_path = get_resume_path()
    if not resume_path:
        return
    
    # 加载简历
    chunks = load_resume(resume_path)
    if not chunks:
        return
    
    # 创建 LLM
    llm = get_llm(config)
    if not llm:
        return
    
    from position_manager import PositionManager
    from knowledge_loader import load_knowledge_base

    # 获取默认岗位（可从配置文件读取，或让用户选择）
    position_name = "Java后端开发工程师"  # 或从 config 读取
    position_manager = PositionManager()
    position_info = position_manager.get_position(position_name)
    if not position_info:
        print(f"错误：找不到岗位 '{position_name}' 的信息，请检查 positions/ 目录下的 JSON 文件。")
        return

    # 加载岗位知识库
    kb_paths = position_manager.get_knowledge_base_paths(position_name)
    knowledge_chunks = load_knowledge_base(kb_paths)

    # 创建面试链
    try:
        chain = create_interview_chain(
            resume_chunks=chunks,
            knowledge_chunks=knowledge_chunks,
            llm=llm,
            config=config,
            position_info=position_info
        )
    except Exception as e:
        print(f"初始化失败：{e}")
        return
    
    # 开始面试
    run_interview(chain)
    
    print("\n" + "=" * 50)
    print("   感谢使用简历拷打面试官！祝你面试顺利！")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
