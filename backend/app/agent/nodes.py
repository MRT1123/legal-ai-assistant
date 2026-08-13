"""
法律智能助手 - 节点实现
Router（路由）→ Agent（推理）→ Generator（生成）三个核心节点
"""

from langchain_openai import ChatOpenAI
from app.agent.state import AgentState
from app.agent.prompts import ROUTER_PROMPT, GENERATOR_PROMPT, QUESTION_ANALYZER_PROMPT
import json


# 从模型服务层获取 LLM 实例（支持多模型 Fallback）
from app.services.model_service import get_llm, invoke_with_fallback

# 兼容旧代码：llm 变量仍然可用，但推荐用 invoke_with_fallback
llm = get_llm()


def router_node(state: AgentState) -> dict:
    """路由节点 - 判断用户问题属于什么类型
    
    类比：前台接待员，先看问题是什么类型，再决定交给谁处理
    - general：通用问题，不需要检索知识库
    - simple：简单问题，直接检索回答
    - complex：复杂问题，需要多步推理
    """
    query = state["query"]
    print(f"\n🔀 [路由节点] 分析问题：{query}")
    
    # 让 LLM 判断问题类型
    response = llm.invoke(ROUTER_PROMPT.format(query=query))
    
    # 解析分类结果
    try:
        result = json.loads(response.content)
        query_type = result.get("type", "simple")
        reason = result.get("reason", "")
    except json.JSONDecodeError:
        query_type = "simple"
        reason = "JSON解析失败，默认走简单路径"
    
    print(f"   分类结果：{query_type}（{reason}）")
    
    return {"query_type": query_type}


def agent_node(state: AgentState) -> dict:
    """Agent 节点 - 执行检索和推理
    
    类比：核心工作人员，拿到任务后去查资料、分析、整理结果
    """
    query = state["query"]
    query_type = state["query_type"]
    
    print(f"\n🤖 [Agent节点] 开始处理（类型：{query_type}）")
    
    # MVP 阶段：先做简单的文档检索
    # 后续会接入混合检索（Dense + BM25 + RRF）
    from app.services.rag_service import retrieve_documents
    
    # 调用检索服务
    documents = retrieve_documents(query)
    
    print(f"   检索到 {len(documents)} 个相关文档片段")
    for i, doc in enumerate(documents):
        text = doc["text"] if isinstance(doc, dict) else str(doc)
        meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        law = meta.get("law_name", "未知")
        article = meta.get("article", "")
        print(f"   片段{i+1}：[{law} {article}] {text[:50]}...")
    
    return {"documents": documents}


def generator_node(state: AgentState) -> dict:
    """Generator 节点 - 整合检索结果，生成最终回答
    
    类比：资深律师，根据查到的法条和案例，给出专业回答
    """
    query = state["query"]
    documents = state.get("documents", [])
    query_type = state.get("query_type", "simple")
    
    print(f"\n📝 [生成节点] 整合信息，生成回答...")
    
    # 如果没有检索到文档，直接让 LLM 回答
    if not documents:
        print("   ⚠️ 未检索到相关文档，使用通用知识回答")
        response = llm.invoke(f"请用你的知识回答以下法律问题（注意：如果不确定，请说明）：\n\n问题：{query}")
        return {"final_answer": response.content}
    
    # 把检索到的文档拼成上下文（适配带元数据的新格式）
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
    
    # 让 LLM 基于检索结果生成回答
    prompt = GENERATOR_PROMPT.format(query=query, context=context)
    response = llm.invoke(prompt)
    
    answer = response.content
    print(f"   ✓ 回答生成完成（{len(answer)} 字）")
    
    return {"final_answer": answer}


def analyze_question(query: str, chat_history: str = "") -> dict:
    """问题分析节点 - 判断用户问题是否需要追问补充信息
    
    类比：律师接案时先了解基本情况，信息不够就先问清楚
    
    返回：
        {
            "need_followup": bool,      # 是否需要追问
            "reason": str,              # 判断理由
            "followup_questions": list  # 追问问题列表
        }
    """
    print(f"\n[问题分析] 分析用户问题：{query}")
    
    # 调用 LLM 判断是否需要追问
    prompt = QUESTION_ANALYZER_PROMPT.format(
        query=query,
        chat_history=chat_history if chat_history else "（无历史对话）"
    )
    # 使用带 Fallback 的 LLM 调用
    try:
        response_content = invoke_with_fallback(prompt)
    except RuntimeError as e:
        print(f"   LLM 调用失败：{e}")
        return {"need_followup": False, "reason": "LLM不可用，默认不追问", "followup_questions": []}
    
    # 解析结果
    try:
        result = json.loads(response_content)
        need_followup = result.get("need_followup", False)
        reason = result.get("reason", "")
        followup_questions = result.get("followup_questions", [])
    except json.JSONDecodeError:
        # JSON 解析失败，默认不追问
        need_followup = False
        reason = "JSON解析失败，默认不追问"
        followup_questions = []
    
    if need_followup:
        print(f"   需要追问：{followup_questions}")
    else:
        print(f"   信息充足，直接回答（{reason}）")
    
    return {
        "need_followup": need_followup,
        "reason": reason,
        "followup_questions": followup_questions
    }
