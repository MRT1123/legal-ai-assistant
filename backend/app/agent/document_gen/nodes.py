import os
"""
法律文书生成 - 3个 Agent 节点实现
流水线：需求分析 → 文书起草 → 格式审核
"""

from langchain_openai import ChatOpenAI
from app.agent.document_gen.state import DocumentGenState
from app.agent.document_gen.prompts import (
    REQUIREMENT_ANALYSIS_PROMPT,
    DOCUMENT_DRAFT_PROMPT,
    DOCUMENT_REVIEW_PROMPT
)

# 所有 Agent 共用一个 LLM 实例
llm = ChatOpenAI(
    model="deepseek-chat",
    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    os.getenv("DEEPSEEK_API_KEY", ""),
    temperature=0
)


def requirement_agent(state: DocumentGenState) -> dict:
    """Agent ① 需求分析 - 从用户描述中提取文书所需的全部要素
    
    类比：律师接待客户，先了解清楚情况、记录关键信息
    """
    print("\n🎯 [需求分析Agent] 分析用户需求...")
    
    prompt = REQUIREMENT_ANALYSIS_PROMPT.format(
        user_requirement=state["user_requirement"]
    )
    response = llm.invoke(prompt)
    
    analysis = response.content
    print(f"   ✓ 需求分析完成（{len(analysis)} 字）")
    
    # 尝试提取文书类型（简单关键词匹配）
    doc_type = "法律文书"
    type_keywords = {
        "劳动仲裁": "劳动仲裁申请书",
        "起诉状": "民事起诉状",
        "律师函": "律师函",
        "答辩状": "答辩状",
        "和解协议": "和解协议书"
    }
    for keyword, dtype in type_keywords.items():
        if keyword in analysis:
            doc_type = dtype
            break
    
    return {
        "requirement_analysis": analysis,
        "document_type": doc_type
    }


def draft_agent(state: DocumentGenState) -> dict:
    """Agent ② 文书起草 - 根据需求分析生成文书初稿
    
    类比：律师助理根据律师整理的案件信息，起草文书初稿
    """
    print(f"\n✍️ [文书起草Agent] 起草{state['document_type']}...")
    
    prompt = DOCUMENT_DRAFT_PROMPT.format(
        requirement_analysis=state["requirement_analysis"],
        document_type=state["document_type"]
    )
    response = llm.invoke(prompt)
    
    draft = response.content
    print(f"   ✓ 文书初稿完成（{len(draft)} 字）")
    return {"document_draft": draft}


def review_agent(state: DocumentGenState) -> dict:
    """Agent ③ 格式审核 - 检查并完善文书格式
    
    类比：资深律师审核助理写的文书，修正格式、补充遗漏
    """
    print("\n✅ [格式审核Agent] 审核文书...")
    
    prompt = DOCUMENT_REVIEW_PROMPT.format(
        document_draft=state["document_draft"]
    )
    response = llm.invoke(prompt)
    
    final_doc = response.content
    print(f"   ✓ 文书审核完成（{len(final_doc)} 字）")
    return {"final_document": final_doc}
