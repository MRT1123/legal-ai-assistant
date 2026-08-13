"""
合同风险审查 - LangGraph 子图定义
4个 Agent 顺序流水线：解析 → 风险扫描 → 合规检查 → 报告生成
"""

from langgraph.graph import StateGraph, START, END
from app.agent.contract_review.state import ContractReviewState
from app.agent.contract_review.nodes import (
    extract_agent, risk_scan_agent,
    compliance_agent, report_agent
)


def build_contract_review_graph():
    """构建合同审查子图
    
    流程（纯顺序执行，无分支）：
    START → 解析Agent → 风险扫描Agent → 合规检查Agent → 报告Agent → END
    
    为什么是顺序执行？
    因为每个 Agent 都需要上一步的输出作为输入：
    - 风险扫描需要知道解析了哪些条款
    - 合规检查需要知道发现了哪些风险
    - 报告生成需要综合所有结果
    """
    graph = StateGraph(ContractReviewState)
    
    # 添加4个 Agent 节点
    graph.add_node("extract", extract_agent)       # ① 合同解析
    graph.add_node("risk_scan", risk_scan_agent)   # ② 风险扫描
    graph.add_node("compliance", compliance_agent) # ③ 合规检查
    graph.add_node("report", report_agent)         # ④ 报告生成
    
    # 添加顺序边（流水线）
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "risk_scan")
    graph.add_edge("risk_scan", "compliance")
    graph.add_edge("compliance", "report")
    graph.add_edge("report", END)
    
    # 编译
    app = graph.compile()
    print("✅ 合同审查子图构建完成（4 Agent 流水线）")
    return app
