"""
法律计算器 - 状态定义
3个 Agent 流水线协作的共享状态
"""

from typing import TypedDict


class CalculatorState(TypedDict):
    """计算器状态 - 3个 Agent 依次处理
    
    流程：
    用户输入计算需求 → ①参数解析Agent → ②计算执行Agent → ③结果审核Agent → 输出报告
    """
    # 用户输入：计算需求描述
    user_query: str
    
    # Agent ① 输出：解析后的计算参数（JSON 字符串）
    parsed_params: str
    
    # Agent ② 输出：计算结果和法律依据（JSON 字符串）
    calculation_result: str
    
    # Agent ③ 输出：最终审核报告（Markdown 格式）
    final_report: str
    
    # 计算类型标识（compensation/penalty/interest/injury/support）
    calc_type: str
