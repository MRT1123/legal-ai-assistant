import os
"""
案例分析 - 3个 Agent 节点实现
流水线：事实梳理 → 法条检索 → 策略分析
"""

from langchain_openai import ChatOpenAI
from app.agent.case_analysis.state import CaseAnalysisState
from app.agent.case_analysis.prompts import (
    FACT_EXTRACTION_PROMPT,
    LEGAL_RESEARCH_PROMPT,
    STRATEGY_ANALYSIS_PROMPT
)

# 所有 Agent 共用一个 LLM 实例
llm = ChatOpenAI(
    model="deepseek-chat",
    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    os.getenv("DEEPSEEK_API_KEY", ""),
    temperature=0
)


def fact_agent(state: CaseAnalysisState) -> dict:
    """Agent ① 事实梳理 - 从用户描述中提取关键事实
    
    类比：律师第一次接待客户，把客户讲的情况整理成清晰的事实梳理
    """
    print("\n📌 [事实梳理Agent] 梳理案件事实...")
    
    prompt = FACT_EXTRACTION_PROMPT.format(
        case_description=state["case_description"]
    )
    response = llm.invoke(prompt)
    
    facts = response.content
    print(f"   ✓ 事实梳理完成（{len(facts)} 字）")
    return {"facts_summary": facts}


def research_agent(state: CaseAnalysisState) -> dict:
    """Agent ② 法条检索 - 查找相关法律依据和判例
    
    类比：法律研究员根据律师整理的事实，去检索相关法条和类案
    """
    print("\n📚 [法条检索Agent] 检索法律依据...")
    
    prompt = LEGAL_RESEARCH_PROMPT.format(
        facts_summary=state["facts_summary"],
        case_description=state["case_description"]
    )
    response = llm.invoke(prompt)
    
    references = response.content
    print(f"   ✓ 法条检索完成（{len(references)} 字）")
    return {"legal_references": references}


def strategy_agent(state: CaseAnalysisState) -> dict:
    """Agent ③ 策略分析 - 综合事实和法律依据给出策略建议
    
    类比：资深律师根据案件事实和法律研究，给出诉讼策略和分析报告
    """
    print("\n📊 [策略分析Agent] 生成分析报告...")
    
    prompt = STRATEGY_ANALYSIS_PROMPT.format(
        facts_summary=state["facts_summary"],
        legal_references=state["legal_references"]
    )
    response = llm.invoke(prompt)
    
    report = response.content
    print(f"   ✓ 分析报告完成（{len(report)} 字）")
    return {"analysis_report": report}
