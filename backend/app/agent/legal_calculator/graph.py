"""
法律计算器 - LangGraph 子图定义
3个 Agent 顺序流水线：参数解析 → 计算执行 → 结果审核
"""

from langgraph.graph import StateGraph, START, END
from app.agent.legal_calculator.state import CalculatorState
from app.agent.legal_calculator.nodes import (
    parse_params_agent, calculation_agent, review_agent
)


def build_legal_calculator_graph():
    """构建法律计算器子图
    
    流程（顺序执行）：
    START → 参数解析Agent → 计算执行Agent → 结果审核Agent → END
    """
    graph = StateGraph(CalculatorState)
    
    # 添加3个 Agent 节点
    graph.add_node("parse_params", parse_params_agent)    # ① 参数解析
    graph.add_node("calculate", calculation_agent)         # ② 计算执行
    graph.add_node("review", review_agent)                 # ③ 结果审核
    
    # 顺序流水线
    graph.add_edge(START, "parse_params")
    graph.add_edge("parse_params", "calculate")
    graph.add_edge("calculate", "review")
    graph.add_edge("review", END)
    
    # 编译
    app = graph.compile()
    print("✅ 法律计算器子图构建完成（3 Agent 流水线）")
    return app
