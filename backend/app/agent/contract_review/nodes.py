import os
"""
合同风险审查 - 4个 Agent 节点实现
流水线：解析 → 风险扫描 → 合规检查 → 报告生成
"""

from langchain_openai import ChatOpenAI
from app.agent.contract_review.state import ContractReviewState
from app.agent.contract_review.prompts import (
    EXTRACTION_PROMPT, RISK_SCAN_PROMPT,
    COMPLIANCE_CHECK_PROMPT, REPORT_GENERATE_PROMPT
)

# 所有 Agent 共用一个 LLM 实例（节省资源）
llm = ChatOpenAI(
    model="deepseek-chat",
    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    os.getenv("DEEPSEEK_API_KEY", ""),
    temperature=0
)


def extract_agent(state: ContractReviewState) -> dict:
    """Agent ① 合同解析 - 提取关键条款
    
    类比：拿到一份合同后，先把所有重要条款标注出来、分类整理
    """
    print("\n📋 [合同解析Agent] 开始解析合同...")
    
    contract_text = state["contract_text"]
    prompt = EXTRACTION_PROMPT.format(contract_text=contract_text)
    response = llm.invoke(prompt)
    
    print(f"   ✓ 条款提取完成（{len(response.content)} 字）")
    return {"extracted_clauses": response.content}


def risk_scan_agent(state: ContractReviewState) -> dict:
    """Agent ② 风险扫描 - 识别潜在风险点
    
    类比：拿着标注好的条款逐条审查，找出不合理、有风险的地方
    """
    print("\n🔍 [风险扫描Agent] 开始扫描风险点...")
    
    prompt = RISK_SCAN_PROMPT.format(
        extracted_clauses=state["extracted_clauses"],
        contract_text=state["contract_text"]
    )
    response = llm.invoke(prompt)
    
    print(f"   ✓ 风险扫描完成（{len(response.content)} 字）")
    return {"risk_items": response.content}


def compliance_agent(state: ContractReviewState) -> dict:
    """Agent ③ 合规检查 - 对照法律法规检查合法性
    
    类比：拿着风险清单，逐一对照法律条文，看是否违法
    """
    print("\n⚖️ [合规检查Agent] 开始合规检查...")
    
    prompt = COMPLIANCE_CHECK_PROMPT.format(
        risk_items=state["risk_items"],
        extracted_clauses=state["extracted_clauses"]
    )
    response = llm.invoke(prompt)
    
    print(f"   ✓ 合规检查完成（{len(response.content)} 字）")
    return {"compliance_result": response.content}


def report_agent(state: ContractReviewState) -> dict:
    """Agent ④ 报告生成 - 整合所有分析结果，输出审查报告
    
    类比：资深律师根据前三位分析师的报告，出具最终审查意见书
    """
    print("\n📝 [报告生成Agent] 生成审查报告...")
    
    prompt = REPORT_GENERATE_PROMPT.format(
        extracted_clauses=state["extracted_clauses"],
        risk_items=state["risk_items"],
        compliance_result=state["compliance_result"]
    )
    response = llm.invoke(prompt)
    
    report = response.content
    print(f"   ✓ 报告生成完成（{len(report)} 字）")
    return {"final_report": report}
