# Interview：基于简历的 AI 模拟面试（RAG + 多风格面试官）

Interview 是一个基于 RAG（检索增强生成）的模拟面试系统：你可以上传简历（PDF/图片），让 AI 围绕你的项目经历与岗位要求进行连续追问；也支持不上传简历，直接从岗位要求 + 你的回答出发提问。  
适合用于：面试准备、项目深挖训练、表达与结构化回答练习、岗位专项刷题。

---

## 功能概览
- **简历定向追问**：优先围绕简历细节/你刚刚的回答追问，避免泛泛提问
- **岗位化题库 + 知识库**：按岗位组织题库与知识库，信息不足时自动补位
- **多风格面试官**：审判型 / 随缘型 / 专业型 / 引导型 / 校园友好型
- **Web 前端 + REST API**：直接用 H5 页面练习，也可自行对接任意前端
- **多模型支持**：DeepSeek / Google Gemini（按 `config.ini` 配置）
- **多模态**：语音+文字输入，语音合成
---

## 项目结构（重点）

> 仓库根目录下的核心代码在 `Interview/` 目录中；根目录通常只放许可证、忽略文件等。

```
.
├── Interview/                          # 主项目目录（后端 + H5 前端）
│   ├── api_server.py                   # Flask API Server（提供 /api/* 接口）
│   ├── main.py                         # 命令行入口（本地交互式面试）
│   ├── requirements.txt                # Python 依赖
│   ├── config.ini.template             # 配置模板（可提交到 GitHub）
│   ├── config.ini                      # 本地配置（包含 key，已被 .gitignore 忽略）
│   ├── run.bat                         # Windows 一键运行命令行版本（可选）
│   ├── start_api_server.bat            # Windows 一键启动 API（可选）
│   ├── test_api.py                     # 简单的 API/模型连通性测试（可选）
│   ├── pages/                          # H5 页面（直接用浏览器打开）
│   │   ├── ai-interview.html            # AI 面试主页面（选岗位/风格、对话、生成报告）
│   │   ├── question-bank.html           # 题库页面
│   │   ├── question-practice.html       # 题集练习页面
│   │   └── recent-report.html           # 最近报告/反馈页面
│   ├── index.html                      # H5 总览入口页
│   ├── login.html                      # H5 登录页（如启用）
│   ├── assets/                         # 静态资源（图片/图标等）
│   │   ├── images/
│   │   └── logo/
│   ├── positions/                      # 岗位配置（决定题库/知识库入口等）
│   │   ├── Java.json
│   │   ├── Python.json
│   │   └── Web.json
│   ├── knowledge_base/                 # 知识库文档（RAG 检索素材）
│   │   ├── *.md
│   │   └── knowledge_base/             # 可能存在的二级整理目录
│   ├── evaluation.py                   # 评估/打分逻辑（面试结束生成反馈）
│   ├── recommendation.py               # 资源推荐（结合 learning_resources.json）
│   ├── learning_resources.json          # 学习资源清单（用于推荐）
│   ├── database.py                     # 本地历史/会话存储（如启用）
│   ├── position_manager.py             # 岗位加载与题库/知识库路由
│   ├── knowledge_loader.py             # 知识库加载（md 等）
│   ├── ocr_utils.py                    # OCR（图片简历识别，按你的配置启用）
│   ├── audio_utils.py                  # 音频/语音相关工具（可选能力）
│   └── speech_analyzer.py              # 表达/语音分析（可选能力）
├── .gitignore                          # 仓库级忽略规则（已忽略 config.ini、*.db、temp/ 等）
└── LICENSE                             # MIT License
```

---

## 快速开始

### 1）安装依赖
```bash
cd Interview
pip install -r requirements.txt
```

### 2）配置 API Key
复制模板：
```bash
cp config.ini.template config.ini
```

编辑 `config.ini`，至少完成：
- `[DEFAULT] provider = deepseek / google`
- 对应 provider 的 `api_key`

### 3）启动方式

**方式 A：API + H5 前端（推荐）**
```bash
python api_server.py
```
然后用浏览器打开：
- `Interview/index.html`
- `Interview/pages/ai-interview.html`

**方式 B：命令行版本**
```bash
python main.py
```

---

## 面试官风格（interview_style）

在 `config.ini` 或 `/api/interview/start` 的 `interview_style` 参数里可使用：
- `judge`：审判型（高强度追问：证据/边界/取舍/验证）
- `random`：随缘型（节奏更松，顺着回答自然追问，但仍会落地）
- `professional`：专业型（标准流程、结构化评估、结论导向）
- `guide`：引导型（循序渐进、适当提示，帮助讲清思路）
- `student`：校园友好型（更基础、更鼓励，适合在校同学）



---

## API 简表
- `GET  /api/health`：健康检查
- `POST /api/upload-resume`：上传简历（PDF/图片）
- `POST /api/interview/start`：开始面试（resume_id 可选、position 必填、interview_style 可选）
- `POST /api/interview/message`：发送候选人回答
- `POST /api/interview/end`：结束会话并生成报告

`/api/interview/start` 请求示例：
```json
{
  "resume_id": "可选",
  "position": "Java后端开发工程师",
  "interview_style": "professional"
}
```

---

## 安全提示（务必）
- **不要提交 `config.ini`**：里面包含 API Key，项目已在 `.gitignore` 中忽略
- 本地运行产生的 `temp/`、`*.db`、历史记录文件属于运行数据：建议忽略或清理后再提交

