"""
合同风险审查 - 状态定义
4个 Agent 流水线协作的共享状态
"""

from typing import TypedDict


class ContractReviewState(TypedDict):
    """合同审查状态 - 4个 Agent 依次往里面写结果
    
    流程：
    用户输入合同 → ①解析Agent → ②风险Agent → ③合规Agent → ④报告Agent → 输出报告
    """
    # 用户输入：合同原文
    contract_text: str
    
    # Agent ① 输出：提取的关键条款（JSON 字符串）
    extracted_clauses: str
    
    # Agent ② 输出：识别出的风险点列表（JSON 字符串）
    risk_items: str
    
    # Agent ③ 输出：合规检查结果
    compliance_result: str
    
    # Agent ④ 输出：最终审查报告（Markdown 格式）
    final_report: str
