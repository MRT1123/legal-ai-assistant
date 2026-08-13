"""
法律智能助手 - 状态定义
定义 LangGraph Agent 的状态结构（State）
"""

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 状态定义 - 整个图的"共享记忆"
    
    类比：一个文件夹，所有节点都能往里放东西、读东西
    """
    # 用户的原始问题
    query: str
    
    # 主路由识别的任务类型（qa / contract_review / document_gen / case_analysis）
    task_type: Optional[str]
    
    # 问题分类结果（general / simple / complex）—— 仅 QA 模式使用
    query_type: str
    
    # 检索到的文档片段列表
    documents: list
    
    # Agent 调用的工具及其返回结果
    tool_results: list
    
    # 最终生成的回答
    final_answer: str
    
    # 对话消息历史（支持多轮对话）
    messages: Annotated[list, add_messages]
