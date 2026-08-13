import os
"""
法律计算器 - 3个 Agent 节点实现
流水线：参数解析 → 计算执行 → 结果审核
"""

import json
from langchain_openai import ChatOpenAI
from app.agent.legal_calculator.state import CalculatorState
from app.agent.legal_calculator.prompts import (
    PARAM_PARSE_PROMPT, CALCULATION_EXEC_PROMPT, RESULT_REVIEW_PROMPT
)
from app.agent.legal_calculator.calculators import (
    calculate_compensation, calculate_penalty, calculate_interest,
    calculate_injury, calculate_support
)

# 所有 Agent 共用一个 LLM 实例
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    api_key=os.getenv("DEEPSEEK_API_KEY", ""),
    temperature=0
)

# 计算类型到计算函数的映射
CALCULATOR_MAP = {
    "compensation": calculate_compensation,
    "penalty": calculate_penalty,
    "interest": calculate_interest,
    "injury": calculate_injury,
    "support": calculate_support,
}


def parse_params_agent(state: CalculatorState) -> dict:
    """Agent ① 参数解析 - 从用户自然语言中提取计算参数
    
    类比：用户用自然语言描述计算需求，这个 Agent 负责"翻译"成结构化的参数
    """
    print("\n🔢 [参数解析Agent] 正在解析用户需求...")
    
    user_query = state["user_query"]
    prompt = PARAM_PARSE_PROMPT.format(user_query=user_query)
    response = llm.invoke(prompt)
    
    # 解析 LLM 返回的 JSON
    try:
        content = response.content
        # 尝试提取 JSON 部分（LLM 可能在 JSON 前后加文字说明）
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            parsed = json.loads(json_str)
        else:
            parsed = json.loads(content)
    except json.JSONDecodeError:
        # 如果解析失败，使用默认值
        parsed = {
            "calc_type": "compensation",
            "calc_type_name": "经济补偿金",
            "params": {},
            "missing_params": [],
            "assumptions": "无法解析用户输入，使用默认参数"
        }
    
    calc_type = parsed.get("calc_type", "compensation")
    print(f"   ✓ 识别计算类型：{parsed.get('calc_type_name', calc_type)}")
    print(f"   ✓ 提取参数：{parsed.get('params', {})}")
    
    return {
        "parsed_params": json.dumps(parsed, ensure_ascii=False),
        "calc_type": calc_type
    }


def calculation_agent(state: CalculatorState) -> dict:
    """Agent ② 计算执行 - 使用纯 Python 计算引擎执行精确计算
    
    类比：拿到参数后，用精确的数学公式和法律规则进行计算
    """
    print("\n🧮 [计算执行Agent] 正在执行计算...")
    
    # 解析参数
    try:
        params_data = json.loads(state["parsed_params"])
    except json.JSONDecodeError:
        params_data = {}
    
    calc_type = state.get("calc_type") or params_data.get("calc_type", "compensation")
    calc_params = params_data.get("params", {})
    
    # 调用对应的纯计算函数（不依赖 LLM，确保精确）
    calc_func = CALCULATOR_MAP.get(calc_type)
    if calc_func:
        try:
            result = calc_func(calc_params)
            print(f"   ✓ 计算完成，结果：{result.get('total_amount', 'N/A')} 元")
        except Exception as e:
            print(f"   ✗ 计算出错：{e}")
            # 计算出错时，回退到 LLM 计算
            result = _fallback_llm_calculation(calc_type, params_data, str(e))
    else:
        # 未知类型，使用 LLM 兜底
        result = _fallback_llm_calculation(calc_type, params_data, "未知计算类型")
    
    return {"calculation_result": json.dumps(result, ensure_ascii=False)}


def _fallback_llm_calculation(calc_type: str, params_data: dict, error_msg: str) -> dict:
    """当纯计算函数失败时，回退到 LLM 进行计算"""
    prompt = CALCULATION_EXEC_PROMPT.format(
        calc_type=calc_type,
        calc_type_name=params_data.get("calc_type_name", calc_type),
        parsed_params=state_parsed_params_safe(params_data)
    )
    response = llm.invoke(prompt)
    
    try:
        content = response.content
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(content[json_start:json_end])
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "calc_type": calc_type,
            "calc_type_name": params_data.get("calc_type_name", calc_type),
            "params_used": params_data.get("params", {}),
            "calculation_steps": [{"step": "LLM 计算", "formula": "N/A", "result": response.content}],
            "total_amount": 0,
            "total_amount_text": "计算异常",
            "legal_basis": [],
            "notes": f"计算异常：{error_msg}"
        }


def state_parsed_params_safe(params_data: dict) -> str:
    """安全地将参数转为可读字符串"""
    try:
        return json.dumps(params_data, ensure_ascii=False, indent=2)
    except Exception:
        return str(params_data)


def review_agent(state: CalculatorState) -> dict:
    """Agent ③ 结果审核 - 校验结果并生成用户友好的最终报告
    
    类比：资深会计师审核计算结果，确保准确后出具正式报告
    """
    print("\n📝 [结果审核Agent] 正在审核并生成报告...")
    
    # 解析计算结果
    try:
        calc_result = json.loads(state["calculation_result"])
    except json.JSONDecodeError:
        calc_result = {}
    
    # 解析参数
    try:
        params_data = json.loads(state["parsed_params"])
    except json.JSONDecodeError:
        params_data = {}
    
    calc_type_name = calc_result.get("calc_type_name", params_data.get("calc_type_name", "法律计算"))
    
    prompt = RESULT_REVIEW_PROMPT.format(
        calc_type_name=calc_type_name,
        parsed_params=json.dumps(params_data, ensure_ascii=False, indent=2),
        calculation_result=json.dumps(calc_result, ensure_ascii=False, indent=2)
    )
    response = llm.invoke(prompt)
    
    report = response.content
    print(f"   ✓ 报告生成完成（{len(report)} 字）")
    return {"final_report": report}
