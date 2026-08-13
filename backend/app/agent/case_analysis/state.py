"""
案例分析 - 状态定义
3个 Agent 流水线协作的共享状态
"""

from typing import TypedDict


class CaseAnalysisState(TypedDict):
    """案例分析状态 - 3个 Agent 依次处理
    
    流程：
    用户描述案情 → ①事实梳理Agent → ②法条检索Agent → ③策略分析Agent → 输出分析报告
    """
    # 用户输入：案情描述
    case_description: str
    
    # Agent ① 输出：结构化事实梳理
    facts_summary: str
    
    # Agent ② 输出：相关法条和判例
    legal_references: str
    
    # Agent ③ 输出：最终分析报告
    analysis_report: str
