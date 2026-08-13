"""
案例分析 - LangGraph 子图定义
3个 Agent 顺序流水线：事实梳理 → 法条检索 → 策略分析
"""

from langgraph.graph import StateGraph, START, END
from app.agent.case_analysis.state import CaseAnalysisState
from app.agent.case_analysis.nodes import (
    fact_agent, research_agent, strategy_agent
)


def build_case_analysis_graph():
    """构建案例分析子图
    
    流程（顺序执行）：
    START → 事实梳理Agent → 法条检索Agent → 策略分析Agent → END
    """
    graph = StateGraph(CaseAnalysisState)
    
    # 添加3个 Agent 节点
    graph.add_node("fact", fact_agent)          # ① 事实梳理
    graph.add_node("research", research_agent)   # ② 法条检索
    graph.add_node("strategy", strategy_agent)   # ③ 策略分析
    
    # 顺序流水线
    graph.add_edge(START, "fact")
    graph.add_edge("fact", "research")
    graph.add_edge("research", "strategy")
    graph.add_edge("strategy", END)
    
    # 编译
    app = graph.compile()
    print("✅ 案例分析子图构建完成（3 Agent 流水线）")
    return app
