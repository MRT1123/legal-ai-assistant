"""
法律文书生成 - LangGraph 子图定义
3个 Agent 顺序流水线：需求分析 → 文书起草 → 格式审核
"""

from langgraph.graph import StateGraph, START, END
from app.agent.document_gen.state import DocumentGenState
from app.agent.document_gen.nodes import (
    requirement_agent, draft_agent, review_agent
)


def build_document_gen_graph():
    """构建文书生成子图
    
    流程（顺序执行）：
    START → 需求分析Agent → 文书起草Agent → 格式审核Agent → END
    """
    graph = StateGraph(DocumentGenState)
    
    # 添加3个 Agent 节点
    graph.add_node("requirement", requirement_agent)  # ① 需求分析
    graph.add_node("draft", draft_agent)              # ② 文书起草
    graph.add_node("review", review_agent)            # ③ 格式审核
    
    # 顺序流水线
    graph.add_edge(START, "requirement")
    graph.add_edge("requirement", "draft")
    graph.add_edge("draft", "review")
    graph.add_edge("review", END)
    
    # 编译
    app = graph.compile()
    print("✅ 文书生成子图构建完成（3 Agent 流水线）")
    return app
