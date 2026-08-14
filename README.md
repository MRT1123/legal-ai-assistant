# 🏛️ 法律智能助手（Legal AI Assistant）

> 基于 **LangChain + LangGraph** 构建的多智能体法律咨询服务系统，支持 RAG 知识检索、合同审查、法律文书生成、案例分析、法律计算器五大核心功能，具备多轮对话、智能追问、引用溯源、敏感信息脱敏、多模型 Fallback 等生产级特性。

---

## ✨ 功能特性

### 核心功能

| 功能 | 说明 |
|------|------|
| 📚 **法律问答（RAG）** | 基于 2000+ 法律条文的向量检索，结合 LLM 生成精准回答 |
| 📋 **合同审查** | 4 个 AI 专家协作：格式解析 → 风险扫描 → 合规检查 → 报告生成 |
| ✍️ **文书生成** | 3 个 AI 专家协作：需求分析 → 文书起草 → 格式审核 |
| 🔍 **案例分析** | 3 个 AI 专家协作：事实梳理 → 法条检索 → 策略分析 |
| 🔢 **法律计算器** | 经济补偿金、工伤赔偿、诉讼费、利息等一键计算 |
| 🔐 **用户认证** | JWT 认证 + 邮箱验证码注册 + 忘记密码找回 |
| 🔍 **对话搜索** | 历史记录关键词检索，支持高亮和匹配统计 |
| 📚 **历史侧边栏** | 侧边栏展示历史会话，支持切换和删除 |

### 增强特性

| 特性 | 说明 |
|------|------|
| 🔄 **多轮对话** | 三层意图识别（关键词预过滤 → 历史追问检测 → LLM 兜底判断） |
| 💬 **智能追问** | 信息不足时主动追问关键事实，知识查询类直接回答 |
| 📎 **引用溯源** | 底部标签展示引用来源，弹窗查看法律条文全文 |
| 🔒 **敏感信息脱敏** | 手机号/身份证/银行卡/邮箱自动替换为占位符，LLM 侧零泄露 |
| 🔀 **多模型 Fallback** | DeepSeek 主模型 + 火山引擎豆包备用，故障自动切换 |
| 🎯 **意图识别优化** | 300+ 法律关键词覆盖全场景 + LLM 兜底避免误杀 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (HTML/JS/CSS)                  │
│              SSE 流式输出 · 深色主题 · 响应式              │
└──────────────────────────┬──────────────────────────────┘
                           │ SSE / REST API
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI 后端 (routes.py)               │
│  认证 · 会话管理 · 意图识别 · 敏感信息脱敏 · 流式输出      │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              LangGraph 主路由图 (graph.py)                │
│                                                         │
│  ┌─────────┐    ┌──────────┐    ┌───────────┐          │
│  │ Router  │───▶│  Agent   │───▶│ Generator │          │
│  │  Node   │    │   Node   │    │   Node    │          │
│  └────┬────┘    └──────────┘    └───────────┘          │
│       │                                                 │
│       ├──▶ 法律问答 (QA) — RAG 检索 + 生成              │
│       ├──▶ 合同审查 (SubGraph) — 4节点流水线             │
│       ├──▶ 文书生成 (SubGraph) — 3节点流水线             │
│       ├──▶ 案例分析 (SubGraph) — 3节点流水线             │
│       └──▶ 法律计算器 (SubGraph) — 精确计算              │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                  模型服务层 (model_service.py)            │
│         主模型 DeepSeek ◄──Fallback──► 备用 火山引擎      │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    数据层                                 │
│  ChromaDB (向量库) · SQLite (会话/用户) · 法律文档库       │
└─────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | HTML5 + CSS3 + 原生 JavaScript（SSE 流式打字机效果） |
| **后端框架** | FastAPI + Uvicorn（异步 SSE 流式响应） |
| **AI 框架** | LangChain 0.3 + LangGraph 0.2（多智能体编排） |
| **大模型** | DeepSeek API（主） / 火山引擎豆包（备） |
| **向量数据库** | ChromaDB（本地持久化，Sentence-Transformers 嵌入） |
| **嵌入模型** | sentence-transformers（all-MiniLM-L6-v2，中文优化） |
| **认证** | JWT Token + bcrypt 4.0.1 |
| **部署** | Docker + docker-compose（一键部署） |

---

## 📂 项目结构

```
legal-ai-assistant/
└── backend/
    ├── app/
    │   ├── agent/                    # LangGraph 智能体核心
    │   │   ├── graph.py              # 主路由图（意图分发）
    │   │   ├── nodes.py              # 三个核心节点（Router/Agent/Generator）
    │   │   ├── prompts.py            # 提示词模板
    │   │   ├── state.py              # 状态定义
    │   │   ├── contract_review/      # 合同审查子图
    │   │   ├── document_gen/         # 文书生成子图
    │   │   ├── case_analysis/        # 案例分析子图
    │   │   └── legal_calculator/     # 法律计算器子图
    │   ├── api/
    │   │   ├── routes.py             # API 路由（SSE 流式 + 脱敏 + 意图识别）
    │   │   └── auth_routes.py        # 认证路由（注册/登录/JWT）
    │   ├── services/
    │   │   ├── rag_service.py        # RAG 检索服务
    │   │   ├── model_service.py      # 多模型 Fallback 管理
    │   │   └── desensitize_service.py # 敏感信息脱敏
    │   ├── static/                   # 前端文件
    │   │   ├── index.html
    │   │   ├── script.js
    │   │   └── style.css
    │   └── data/
    │       ├── legal_docs/           # 法律文档原文
    │       ├── chroma_db/            # ChromaDB 向量数据
    │       └── legal_assistant.db    # SQLite 用户/会话数据
    ├── requirements.txt
    ├── .env                          # 环境变量配置
    └── main.py                       # 应用入口
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- DeepSeek API Key
- （可选）火山引擎 API Key

### 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd legal-ai-assistant/backend

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
# 创建 .env 文件
cat > .env << EOF
DEEPSEEK_API_KEY=your_deepseek_key
VOLCANO_API_KEY=your_volcano_key      # 可选
VOLCANO_MODEL=ep-xxxxx                # 可选
EOF

# 5. 启动服务
set HF_ENDPOINT=https://hf-mirror.com  # 国内镜像
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. 打开浏览器访问
# http://localhost:8000
```

---

## 🔑 核心技术亮点

### 1. LangGraph 多智能体编排

采用 StateGraph 构建主路由图，根据用户意图动态分发到 5 个功能子图。每个子图独立管理状态和节点流转，实现复杂任务的模块化编排。

```python
# 主路由：意图识别 → 子图分发
graph = StateGraph(AgentState)
graph.add_node("router", router_node)       # 意图分类
graph.add_node("agent", agent_node)         # RAG 检索
graph.add_node("generator", generator_node) # 答案生成
# 子图
graph.add_node("contract_review", contract_review_graph)
graph.add_node("document_gen", document_gen_graph)
```

### 2. 三层意图识别

```
第一层：300+ 法律关键词预过滤（零成本，毫秒级）
  ├─ 命中 → LLM 精确分类
  └─ 未命中 → 第二层：检查对话历史
       ├─ 有历史 → LLM 判断是否为法律追问
       └─ 无历史 → 第三层：LLM 兜底判断（避免误杀）
```

### 3. 敏感信息脱敏

用户输入在传给 LLM 之前，通过正则匹配自动替换为占位符，LLM 回答后再还原。确保手机号、身份证号等敏感信息不会泄露给模型服务商。

### 4. 多模型 Fallback

```python
# 主模型 DeepSeek 超时/失败 → 自动切换火山引擎豆包
async def astream_with_fallback(prompt, **kwargs):
    try:
        async for chunk in await primary_llm.astream(prompt):
            yield chunk
    except Exception:
        async for chunk in await fallback_llm.astream(prompt):
            yield chunk
```

### 5. 法律条文引用溯源

RAG 检索结果携带来源元数据，前端底部标签展示引用条文，点击弹窗查看全文，支持一键跳转。

---

## 📊 知识库

- **覆盖范围**：宪法、民法典、刑法、劳动法、合同法、公司法、消费者权益保护法等 20+ 法律领域
- **文档数量**：2000+ 法律条文
- **向量化**：sentence-transformers 嵌入，ChromaDB 本地存储
- **检索策略**：相似度 Top-K 检索 + 重排序

---

## 🔮 未来规划

- [x] Docker 容器化部署
- [ ] 法律知识图谱可视化
- [ ] 用户上传文件智能解析
- [ ] 多语言支持
- [ ] 模型微调（法律领域 SFT）

---

## 📄 License

MIT License

---

> 🎓 本项目为个人学习实践项目，基于 LangChain + LangGraph 构建，旨在探索 AI 在法律领域的应用。法律建议仅供参考，具体法律问题请咨询专业律师。
