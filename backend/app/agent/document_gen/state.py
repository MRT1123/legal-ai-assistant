"""
法律文书生成 - 状态定义
3个 Agent 流水线协作的共享状态
"""

from typing import TypedDict


class DocumentGenState(TypedDict):
    """文书生成状态 - 3个 Agent 依次处理
    
    流程：
    用户描述需求 → ①需求分析Agent → ②文书起草Agent → ③格式审核Agent → 输出文书
    """
    # 用户输入：需求描述
    user_requirement: str
    
    # Agent ① 输出：结构化需求分析（JSON）
    requirement_analysis: str
    
    # Agent ② 输出：文书初稿
    document_draft: str
    
    # Agent ③ 输出：最终文书（审核后）
    final_document: str
    
    # 文书类型（由需求分析 Agent 判断）
    document_type: str
