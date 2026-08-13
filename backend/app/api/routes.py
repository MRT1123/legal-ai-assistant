"""
法律智能助手 API 路由
定义 HTTP 接口：
  - /chat         普通问答（一次性返回）
  - /chat/stream  流式问答（SSE 打字机效果，支持所有功能）
  - /health       健康检查
  - /history      对话历史（SQLite 持久化）
"""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import uuid
import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_openai import ChatOpenAI
from app.agent.graph import build_graph, _get_intent, _is_legal_topic, _is_legal_followup
from app.agent.nodes import router_node, agent_node, analyze_question
from app.agent.prompts import GENERATOR_PROMPT
from app.agent.contract_review.graph import build_contract_review_graph
from app.agent.document_gen.graph import build_document_gen_graph
from app.agent.case_analysis.graph import build_case_analysis_graph
from app.agent.legal_calculator.graph import build_legal_calculator_graph
from app.services.rag_service import load_sample_legal_data
from app.services.database import (
    init_db, save_message, get_history,
    get_all_sessions, delete_session, search_sessions
)
from app.services.file_parser import parse_file
from app.services.model_service import astream_with_fallback, get_model_status
from app.services.desensitize_service import desensitize, restore
from app.services.export_service import export_to_word, export_to_pdf
from fastapi.responses import FileResponse

# 创建路由
router = APIRouter()

# 全局变量
graph = None                    # 主 LangGraph 图实例
llm = None                      # LLM 实例（流式输出专用）
contract_review_graph = None    # 合同审查子图
document_gen_graph = None       # 文书生成子图
case_analysis_graph = None      # 案例分析子图
legal_calculator_graph = None   # 法律计算器子图


# ==================== 请求/响应模型 ====================

class ChatRequest(BaseModel):
    """聊天请求"""
    query: str                          # 用户问题
    session_id: Optional[str] = None    # 会话 ID（不传则自动生成）
    task_type: Optional[str] = None     # 强制指定任务类型（qa/contract_review/document_gen/case_analysis）
    file_text: Optional[str] = None     # 上传文件提取的文本（合同审查用）


class ChatResponse(BaseModel):
    """普通聊天响应"""
    answer: str         # AI 回答
    query_type: str     # 问题分类/任务类型
    sources: list       # 检索到的法律依据
    session_id: str     # 会话 ID


class ExportRequest(BaseModel):
    """文档导出请求"""
    content: str                    # 要导出的文档内容
    title: Optional[str] = "法律文书"  # 文档标题
    format: str = "word"            # 导出格式：word 或 pdf
    filename: Optional[str] = None  # 自定义文件名（不含扩展名）


# ==================== 初始化函数 ====================

def init_graph():
    """初始化所有 LangGraph 图 + 数据库 + LLM"""
    global graph, llm, contract_review_graph, document_gen_graph, case_analysis_graph, legal_calculator_graph

    print("🏗️  初始化 LangGraph 图...")
    load_sample_legal_data()
    graph = build_graph()

    # 预构建各功能子图（用于流式输出中获取进度信息）
    contract_review_graph = build_contract_review_graph()
    document_gen_graph = build_document_gen_graph()
    case_analysis_graph = build_case_analysis_graph()
    legal_calculator_graph = build_legal_calculator_graph()

    # 初始化 LLM（流式输出专用）
    llm = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        os.getenv("DEEPSEEK_API_KEY"),
        temperature=0.7,
        streaming=True
    )

    # 初始化 SQLite 数据库
    init_db()

    print("✅ 所有组件初始化完成")


# ==================== 辅助函数 ====================

def _format_sources(documents: list) -> list:
    """格式化检索文档为结构化引用来源
    
    返回格式：
    [
        {
            "law_name": "中华人民共和国劳动合同法",
            "article": "第四十七条",
            "content": "条文内容前200字..."
        },
        ...
    ]
    """
    sources = []
    for doc in documents:
        if isinstance(doc, dict):
            text = doc.get("text", "")
            meta = doc.get("metadata", {})
            sources.append({
                "law_name": meta.get("law_name", ""),
                "article": meta.get("article", ""),
                "content": text[:200] + "..." if len(text) > 200 else text,
                "full_content": text
            })
        else:
            content = str(doc)
            sources.append({
                "law_name": "",
                "article": "",
                "content": content[:200] + "..." if len(content) > 200 else content,
                "full_content": content
            })
    return sources


def _parse_inline_citations(answer: str) -> list:
    """从回答正文中提取内联引用标记
    
    匹配格式：[引用:法律名称|条款号]
    返回去重后的引用列表：[{"law_name": "...", "article": "..."}, ...]
    """
    import re
    pattern = r'\[引用:([^|]+)\|([^\]]+)\]'
    matches = re.findall(pattern, answer)
    
    # 去重
    seen = set()
    citations = []
    for law_name, article in matches:
        key = f"{law_name}|{article}"
        if key not in seen:
            seen.add(key)
            citations.append({
                "law_name": law_name.strip(),
                "article": article.strip()
            })
    return citations


def _get_session_id(request_id: Optional[str]) -> str:
    """获取或生成会话 ID"""
    return request_id or str(uuid.uuid4())[:8]


# ==================== API 路由 ====================

@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "message": "法律智能助手 API 运行正常"}


@router.post("/upload/file")
async def upload_file(file: UploadFile):
    """
    文件上传接口
    支持 .pdf / .docx / .txt / .md 格式
    上传后自动解析提取文本内容，返回解析结果
    """
    # 检查文件扩展名是否在允许列表中
    allowed_types = {'.pdf', '.docx', '.txt', '.md'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型：{file_ext}，仅支持 {', '.join(allowed_types)}"
        )

    # 检查文件大小（限制 10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    # 保存到临时目录
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

    with open(temp_path, "wb") as f:
        f.write(content)

    try:
        # 调用文件解析服务提取文本
        text = parse_file(temp_path)
        return {
            "success": True,
            "filename": file.filename,
            "file_type": file_ext,
            "text_content": text,
            "text_length": len(text)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    普通问答接口（一次性返回完整结果）
    通过主路由自动分发到对应功能
    """
    global graph

    if graph is None:
        raise HTTPException(status_code=500, detail="系统未初始化")

    session_id = _get_session_id(request.session_id)

    try:
        initial_state = {
            "query": request.query,
            "task_type": request.task_type or None,
            "messages": [],
            "documents": [],
            "tool_results": [],
            "final_answer": ""
        }

        result = graph.invoke(initial_state)

        answer = result.get("final_answer", "抱歉，未能生成回答。")
        query_type = result.get("query_type", result.get("task_type", "unknown"))
        documents = result.get("documents", [])
        sources = _format_sources(documents)

        # 保存到 SQLite
        save_message(session_id, "user", request.query)
        save_message(
            session_id, "assistant", answer,
            query_type, json.dumps(sources, ensure_ascii=False)
        )

        return ChatResponse(
            answer=answer,
            query_type=query_type,
            sources=sources,
            session_id=session_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败：{str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式接口（SSE 打字机效果）
    支持所有功能：Q&A / 合同审查 / 文书生成 / 案例分析
    
    SSE 事件格式：
      event: progress  → 处理进度提示（如"正在分析合同..."）
      event: metadata  → 元数据（任务类型等）
      event: token     → 文本片段（逐字推送）
      event: done      → 结束信号
      event: error     → 错误信息
    """
    global graph, llm

    if graph is None:
        raise HTTPException(status_code=500, detail="系统未初始化")

    session_id = _get_session_id(request.session_id)

    async def event_generator():
        """SSE 事件流生成器"""
        full_answer = ""

        try:
            query = request.query
            
            # ===== 敏感信息脱敏 =====
            # 在传给 LLM 之前，将手机号/身份证/银行卡等替换为占位符
            query_desensitized, sensitive_mapping = desensitize(query)
            if sensitive_mapping:
                from app.services.desensitize_service import _desensitizer
                print(f"   [脱敏] {_desensitizer.get_summary(sensitive_mapping)}")

            # === 第1步：意图识别 ===
            if request.task_type:
                intent = request.task_type
            else:
                intent = _get_intent(query)

            # 推送进度提示
            progress_map = {
                "qa": "🔍 正在分析问题...",
                "contract_review": "📋 正在启动合同审查（4个AI专家协作）...",
                "document_gen": "✍️ 正在启动文书生成（3个AI专家协作）...",
                "case_analysis": "📊 正在启动案例分析（3个AI专家协作）...",
                "legal_calculator": "🔢 正在启动法律计算器（3个AI专家协作）..."
            }

            # 非法律问题拦截：直接返回提示，不走 LLM
            if intent == "off_topic":
                off_topic_msg = "抱歉，我是法律智能助手，无法回答与法律无关的问题。如果您有法律方面的疑问，欢迎随时向我提问。"
                yield f"event: metadata\ndata: {json.dumps({'task_type': 'off_topic'}, ensure_ascii=False)}\n\n"
                # 分段流式输出，模拟打字效果
                chunk_size = 40
                for i in range(0, len(off_topic_msg), chunk_size):
                    chunk = off_topic_msg[i:i+chunk_size]
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.03)
                yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'off_topic'}, ensure_ascii=False)}\n\n"
                save_message(session_id, "user", query)
                save_message(session_id, "assistant", off_topic_msg, "off_topic", "[]")
                return

            yield f"event: progress\ndata: {json.dumps({'content': progress_map.get(intent, '处理中...')}, ensure_ascii=False)}\n\n"
            yield f"event: metadata\ndata: {json.dumps({'task_type': intent}, ensure_ascii=False)}\n\n"

            # === 根据意图分发处理 ===
            if intent == "qa":
                full_answer = await _stream_qa(query, session_id)
                # _stream_qa 内部已经 yield 了所有 token 事件
                # 需要重新实现以支持 yield
                # 所以这里改为直接调用流式逻辑
                
            elif intent == "contract_review":
                full_answer = await _stream_contract_review(query, session_id)

            elif intent == "document_gen":
                full_answer = await _stream_document_gen(query, session_id)

            elif intent == "case_analysis":
                full_answer = await _stream_case_analysis(query, session_id)

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"❌ 流式输出异常：{error_msg}")
            yield f"event: error\ndata: {json.dumps({'content': str(e)}, ensure_ascii=False)}\n\n"

    # 由于 async generator 中需要 yield，重新设计
    async def stream_handler():
        """实际的流式处理"""
        full_answer = ""

        try:
            query = request.query

            # ===== 敏感信息脱敏 =====
            # 在传给 LLM 之前，将手机号/身份证/银行卡等替换为占位符
            query_desensitized, sensitive_mapping = desensitize(query)
            if sensitive_mapping:
                from app.services.desensitize_service import _desensitizer
                print(f"   [脱敏] {_desensitizer.get_summary(sensitive_mapping)}")

            # ===== 意图识别：关键词过滤 + LLM 上下文追问检测 =====
            # 第一层：关键词预过滤（永远执行，零成本）
            has_legal_keywords = _is_legal_topic(query)

            if has_legal_keywords:
                # 命中法律关键词 → 直接走 LLM 分类
                if request.task_type:
                    intent = request.task_type
                else:
                    intent = _get_intent(query)
            else:
                # 关键词未命中 → 检查对话历史，判断是否为法律追问
                recent_history = []
                try:
                    recent_history = get_history(session_id, limit=7)
                except Exception as e:
                    print(f"   ⚠️ 获取历史失败：{e}")

                if len(recent_history) >= 2:
                    # 有历史对话 → 格式化历史，让 LLM 判断是否为追问
                    history_lines = []
                    for msg in recent_history[-6:]:
                        role_label = "用户" if msg["role"] == "user" else "助手"
                        content_text = msg["content"][:200]
                        history_lines.append(f"{role_label}：{content_text}")
                    history_str = "\n".join(history_lines)

                    if _is_legal_followup(query, history_str):
                        # 是法律追问 → 走 LLM 分类
                        if request.task_type:
                            intent = request.task_type
                        else:
                            intent = _get_intent(query)
                    else:
                        intent = "off_topic"
                else:
                    # 无历史对话，关键词也没命中 → 让 LLM 兜底判断（避免误杀）
                    print(f"   [意图识别] 关键词未命中+无历史，调用 LLM 兜底判断...")
                    if request.task_type:
                        intent = request.task_type
                    else:
                        intent = _get_intent(query)
                    # LLM 判定为 qa 以外的任务类型时直接放行；qa 类型也放行（说明 LLM 认为是法律问题）
                    # 只有 _get_intent 明确返回 off_topic 才拦截（当前 _get_intent 不会返回 off_topic，所以基本都会放行）

            progress_map = {
                "qa": "🔍 正在分析问题...",
                "contract_review": "📋 正在启动合同审查（4个AI专家协作）...",
                "document_gen": "✍️ 正在启动文书生成（3个AI专家协作）...",
                "case_analysis": "📊 正在启动案例分析（3个AI专家协作）...",
                "legal_calculator": "🔢 正在启动法律计算器（3个AI专家协作）..."
            }

            # 非法律问题拦截：直接返回专业提示，不走 LLM
            if intent == "off_topic":
                off_topic_msg = "抱歉，我是法律智能助手，无法回答与法律无关的问题。如果您有法律方面的疑问，欢迎随时向我提问。"
                yield f"event: metadata\ndata: {json.dumps({'task_type': 'off_topic'}, ensure_ascii=False)}\n\n"
                chunk_size = 40
                for i in range(0, len(off_topic_msg), chunk_size):
                    chunk = off_topic_msg[i:i+chunk_size]
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.03)
                yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'off_topic'}, ensure_ascii=False)}\n\n"
                save_message(session_id, "user", query)
                save_message(session_id, "assistant", off_topic_msg, "off_topic", "[]")
                return

            yield f"event: progress\ndata: {json.dumps({'content': progress_map.get(intent, '处理中...')}, ensure_ascii=False)}\n\n"
            yield f"event: metadata\ndata: {json.dumps({'task_type': intent}, ensure_ascii=False)}\n\n"

            # 根据意图分发
            if intent == "qa":
                # QA 流式处理
                state = {
                    "query": query_desensitized,
                    "task_type": "qa",
                    "messages": [],
                    "documents": [],
                    "tool_results": [],
                    "final_answer": "",
                    "query_type": ""
                }

                yield f"event: progress\ndata: {json.dumps({'content': '🔀 正在分类问题...'}, ensure_ascii=False)}\n\n"
                router_result = router_node(state)
                query_type = router_result.get("query_type", "simple")
                state["query_type"] = query_type

                yield f"event: metadata\ndata: {json.dumps({'query_type': query_type}, ensure_ascii=False)}\n\n"

                # ===== 智能追问引导：判断问题信息是否充足 =====
                # 先获取对话历史（追问判断也需要）
                chat_history_for_analysis = ""
                try:
                    history_for_analysis = get_history(session_id, limit=7)
                    history_for_analysis = [msg for msg in history_for_analysis if not (msg["role"] == "user" and msg["content"] == query)]
                    history_for_analysis = history_for_analysis[-6:]
                    if history_for_analysis:
                        history_lines_tmp = []
                        for msg in history_for_analysis:
                            role_label = "用户" if msg["role"] == "user" else "助手"
                            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
                            history_lines_tmp.append(f"{role_label}：{content}")
                        chat_history_for_analysis = "\n".join(history_lines_tmp)
                except Exception as e:
                    print(f"   获取对话历史失败：{e}")
                    chat_history_for_analysis = ""
                
                question_analysis = analyze_question(query_desensitized, chat_history_for_analysis)
                
                if question_analysis.get("need_followup") and question_analysis.get("followup_questions"):
                    # 需要追问：生成追问内容并返回，不走 RAG 流程
                    followup_qs = question_analysis["followup_questions"]
                    followup_msg = "为了更好地帮您分析，我还需要了解几个关键信息：\n\n"
                    for i, q in enumerate(followup_qs, 1):
                        followup_msg += f"{i}. {q}\n"
                    followup_msg += "\n请您补充以上信息，我会给您更精准的法律分析。"
                    
                    yield f"event: progress\ndata: {json.dumps({'content': '💬 正在分析问题...'}, ensure_ascii=False)}\n\n"
                    yield f"event: metadata\ndata: {json.dumps({'task_type': 'followup'}, ensure_ascii=False)}\n\n"
                    
                    # 流式输出追问内容
                    chunk_size = 30
                    for i in range(0, len(followup_msg), chunk_size):
                        chunk = followup_msg[i:i+chunk_size]
                        yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.03)
                    
                    yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'followup'}, ensure_ascii=False)}\n\n"
                    save_message(session_id, "user", query)
                    save_message(session_id, "assistant", followup_msg, "followup", "[]")
                    return

                documents = []
                if query_type != "general":
                    yield f"event: progress\ndata: {json.dumps({'content': '📚 正在检索法律知识库...'}, ensure_ascii=False)}\n\n"
                    agent_result = agent_node(state)
                    documents = agent_result.get("documents", [])

                # ===== 多轮对话：获取对话历史 =====
                chat_history = ""
                try:
                    history = get_history(session_id, limit=7)  # 取最近7条（含当前用户问题，实际取6条历史）
                    # 排除当前这条用户消息（还没保存到数据库）
                    history = [msg for msg in history if not (msg["role"] == "user" and msg["content"] == query)]
                    # 只取最近6条（3轮对话）
                    history = history[-6:]
                    if history:
                        history_lines = []
                        for msg in history:
                            role_label = "用户" if msg["role"] == "user" else "助手"
                            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
                            history_lines.append(f"{role_label}：{content}")
                        chat_history = "\n".join(history_lines)
                        print(f"   📜 多轮对话：加载了 {len(history)} 条历史消息")
                except Exception as e:
                    print(f"   ⚠️ 获取对话历史失败：{e}")
                    chat_history = "（无历史对话）"

                # 构建 prompt 并流式输出
                if not documents:
                    prompt = f"请用你的知识回答以下法律问题（结合对话历史理解用户意图）：\n\n对话历史：\n{chat_history}\n\n用户当前问题：{query}"
                else:
                    # 拼接 context（适配带元数据的新格式）
                    context_parts = []
                    for doc in documents:
                        if isinstance(doc, dict):
                            text = doc.get("text", "")
                            meta = doc.get("metadata", {})
                            law = meta.get("law_name", "")
                            article = meta.get("article", "")
                            if law:
                                context_parts.append(f"[来源: {law} {article}]\n{text}")
                            else:
                                context_parts.append(text)
                        else:
                            context_parts.append(str(doc))
                    context = "\n\n---\n\n".join(context_parts)
                    prompt = GENERATOR_PROMPT.format(query=query_desensitized, context=context, chat_history=chat_history)

                async for token in astream_with_fallback(prompt):
                    content = token.content
                    if content:
                        full_answer += content
                        yield f"event: token\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

                # ===== 还原脱敏信息 =====
                if sensitive_mapping:
                    full_answer = restore(full_answer, sensitive_mapping)
                
                sources = _format_sources(documents)
                
                # 解析正文中的内联引用标记，补充到 sources
                inline_citations = _parse_inline_citations(full_answer)
                if inline_citations:
                    # 将内联引用与检索来源合并（去重，并补上 full_content）
                    existing_keys = {f"{s.get('law_name', '')}|{s.get('article', '')}" for s in sources}
                    for cite in inline_citations:
                        cite_key = f"{cite['law_name']}|{cite['article']}"
                        if cite_key not in existing_keys:
                            # 尝试从已有 sources 中模糊匹配全文
                            matched_full = ""
                            for s in sources:
                                if s.get("law_name") and cite["law_name"] in s["law_name"]:
                                    matched_full = s.get("full_content", "")
                                    break
                            sources.append({
                                "law_name": cite["law_name"],
                                "article": cite["article"],
                                "content": matched_full[:200] + "..." if len(matched_full) > 200 else matched_full,
                                "full_content": matched_full
                            })
                
                yield f"event: done\ndata: {json.dumps({'sources': sources, 'session_id': session_id, 'query_type': query_type}, ensure_ascii=False)}\n\n"

                save_message(session_id, "user", query)
                save_message(session_id, "assistant", full_answer, query_type, json.dumps(sources, ensure_ascii=False))

            elif intent == "contract_review":
                # 优先使用上传文件内容，没有则用输入框文本
                contract_text = request.file_text if request.file_text else query
                
                yield f"event: progress\ndata: {json.dumps({'content': '📋 Agent① 正在解析合同条款...'}, ensure_ascii=False)}\n\n"
                
                result = contract_review_graph.invoke({
                    "contract_text": contract_text,
                    "extracted_clauses": "",
                    "risk_items": "",
                    "compliance_result": "",
                    "final_report": ""
                })

                yield f"event: progress\ndata: {json.dumps({'content': '✅ 审查完成，正在输出报告...'}, ensure_ascii=False)}\n\n"

                full_answer = result.get("final_report", "合同审查完成，但未能生成报告。")
                
                # 分段流式输出报告
                chunk_size = 50
                for i in range(0, len(full_answer), chunk_size):
                    chunk = full_answer[i:i+chunk_size]
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)

                yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'contract_review'}, ensure_ascii=False)}\n\n"

                # 保存消息（截断合同文本作为用户消息）
                save_message(session_id, "user", contract_text[:200] + ("..." if len(contract_text) > 200 else ""))
                save_message(session_id, "assistant", full_answer, "contract_review", "[]")

            elif intent == "document_gen":
                yield f"event: progress\ndata: {json.dumps({'content': '✍️ Agent① 正在分析文书需求...'}, ensure_ascii=False)}\n\n"

                result = document_gen_graph.invoke({
                    "user_requirement": query,
                    "requirement_analysis": "",
                    "document_draft": "",
                    "final_document": "",
                    "document_type": ""
                })

                yield f"event: progress\ndata: {json.dumps({'content': '✅ 文书生成完成，正在输出...'}, ensure_ascii=False)}\n\n"

                full_answer = result.get("final_document", "文书生成完成，但未能生成文档。")
                
                chunk_size = 50
                for i in range(0, len(full_answer), chunk_size):
                    chunk = full_answer[i:i+chunk_size]
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)

                yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'document_gen'}, ensure_ascii=False)}\n\n"

                save_message(session_id, "user", query)
                save_message(session_id, "assistant", full_answer, "document_gen", "[]")

            elif intent == "case_analysis":
                yield f"event: progress\ndata: {json.dumps({'content': '📊 Agent① 正在梳理案件事实...'}, ensure_ascii=False)}\n\n"

                result = case_analysis_graph.invoke({
                    "case_description": query,
                    "facts_summary": "",
                    "legal_references": "",
                    "analysis_report": ""
                })

                yield f"event: progress\ndata: {json.dumps({'content': '✅ 分析完成，正在输出报告...'}, ensure_ascii=False)}\n\n"

                full_answer = result.get("analysis_report", "案例分析完成，但未能生成报告。")
                
                chunk_size = 50
                for i in range(0, len(full_answer), chunk_size):
                    chunk = full_answer[i:i+chunk_size]
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)

                yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'case_analysis'}, ensure_ascii=False)}\n\n"

                save_message(session_id, "user", query)
                save_message(session_id, "assistant", full_answer, "case_analysis", "[]")

            elif intent == "legal_calculator":
                yield f"event: progress\ndata: {json.dumps({'content': '🔢 Agent① 正在解析计算参数...'}, ensure_ascii=False)}\n\n"

                result = legal_calculator_graph.invoke({
                    "user_query": query,
                    "parsed_params": "",
                    "calculation_result": "",
                    "final_report": "",
                    "calc_type": ""
                })

                yield f"event: progress\ndata: {json.dumps({'content': '✅ 计算完成，正在输出报告...'}, ensure_ascii=False)}\n\n"

                full_answer = result.get("final_report", "法律计算完成，但未能生成报告。")
                
                chunk_size = 50
                for i in range(0, len(full_answer), chunk_size):
                    chunk = full_answer[i:i+chunk_size]
                    yield f"event: token\ndata: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)

                yield f"event: done\ndata: {json.dumps({'sources': [], 'session_id': session_id, 'query_type': 'legal_calculator'}, ensure_ascii=False)}\n\n"

                save_message(session_id, "user", query)
                save_message(session_id, "assistant", full_answer, "legal_calculator", "[]")

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"❌ 流式输出异常：{error_msg}")
            yield f"event: error\ndata: {json.dumps({'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream_handler(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==================== 文档导出 API ====================

@router.post("/export/document")
async def export_document(request: ExportRequest):
    """
    文档导出接口
    将 AI 生成的法律文书导出为 Word 或 PDF 文件并下载
    
    参数：
        content:  文档正文内容
        title:    文档标题（默认"法律文书"）
        format:   导出格式 "word" 或 "pdf"（默认 "word"）
        filename: 自定义文件名（不含扩展名）
    
    返回：
        文件下载响应
    """
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="导出内容不能为空")

    fmt = request.format.lower()
    if fmt not in ("word", "pdf"):
        raise HTTPException(status_code=400, detail=f"不支持的格式：{fmt}，仅支持 word 或 pdf")

    try:
        if fmt == "word":
            filepath = export_to_word(
                content=request.content,
                title=request.title,
                filename=request.filename
            )
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = ".docx"
        else:
            filepath = export_to_pdf(
                content=request.content,
                title=request.title,
                filename=request.filename
            )
            media_type = "application/pdf"
            ext = ".pdf"

        # 生成下载文件名
        download_name = request.filename or "法律文书"
        download_filename = f"{download_name}{ext}"

        return FileResponse(
            path=filepath,
            filename=download_filename,
            media_type=media_type
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{str(e)}")


# ==================== 历史记录 API ====================

@router.get("/history/sessions")
async def list_sessions():
    """获取所有对话会话列表"""
    sessions = get_all_sessions()
    return {"sessions": sessions}


@router.get("/history/search")
async def search_history(q: str = ""):
    """
    按关键词搜索对话历史
    
    参数：
        q - 搜索关键词（必填）
    
    返回：匹配的会话列表
    """
    if not q.strip():
        return {"sessions": []}
    
    results = search_sessions(q.strip())
    return {"sessions": results, "keyword": q.strip()}


@router.get("/history/{session_id}")
async def get_session_history(session_id: str):
    """获取某个会话的完整对话记录"""
    messages = get_history(session_id)
    return {"session_id": session_id, "messages": messages}


@router.delete("/history/{session_id}")
async def remove_session(session_id: str):
    """删除某个会话"""
    delete_session(session_id)
    return {"message": f"会话 {session_id} 已删除"}
