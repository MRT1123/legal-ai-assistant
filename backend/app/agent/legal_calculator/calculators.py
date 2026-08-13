"""
法律计算器 - 计算引擎
纯 Python 计算逻辑，不依赖 LLM，确保计算结果精确可靠
"""

import math
import json


def calculate_compensation(params: dict) -> dict:
    """经济补偿金/赔偿金计算
    
    支持三种模式：
    - N：合法解除（协商一致/客观情况变化等）
    - 2N：违法解除赔偿金
    - N+1：未提前30天通知的代通知金
    
    法律依据：《劳动合同法》第47条、第87条
    """
    monthly_salary = float(params.get("monthly_salary", 0))
    work_years = float(params.get("work_years", 0))
    dismissal_type = params.get("dismissal_type", "legal")  # legal/illegal/no_notice
    
    # 工龄取整规则：6个月以上按1年，不足6个月按0.5年
    if work_years == int(work_years):
        n_months = int(work_years)
    else:
        integer_part = int(work_years)
        decimal_part = work_years - integer_part
        if decimal_part > 0.5:
            n_months = integer_part + 1
        elif decimal_part > 0:
            n_months = integer_part + 0.5
        else:
            n_months = integer_part
    
    # 月工资上限（以当地社平工资3倍为上限，这里用默认值，实际可调整）
    # 默认假设当地上年度职工月平均工资为 15000 元（可根据城市调整）
    local_avg_salary = float(params.get("local_avg_salary", 15000))
    salary_cap = local_avg_salary * 3
    
    # 如果月工资超过3倍社平工资，按上限计算，且年限最高12年
    if monthly_salary > salary_cap:
        actual_salary = salary_cap
        max_years = 12
        high_salary_note = f"月工资超过当地社平工资3倍（{salary_cap:.0f}元），按上限计算，年限最高12年"
    else:
        actual_salary = monthly_salary
        max_years = None
        high_salary_note = None
    
    effective_months = n_months
    if max_years and effective_months > max_years:
        effective_months = max_years
    
    # 计算 N
    n_amount = actual_salary * effective_months
    
    steps = []
    
    if dismissal_type == "illegal":
        # 违法解除：2N
        total = n_amount * 2
        mode_name = "违法解除赔偿金（2N）"
        steps.append({
            "step": "计算经济补偿金 N",
            "formula": f"月工资 {actual_salary:.0f} 元 × 工龄 {effective_months} 年 = {n_amount:.0f} 元",
            "result": f"{n_amount:.0f} 元"
        })
        steps.append({
            "step": "计算赔偿金 2N",
            "formula": f"{n_amount:.0f} 元 × 2 = {total:.0f} 元",
            "result": f"{total:.0f} 元"
        })
    elif dismissal_type == "no_notice":
        # 未提前通知：N+1
        total = n_amount + actual_salary
        mode_name = "经济补偿金+代通知金（N+1）"
        steps.append({
            "step": "计算经济补偿金 N",
            "formula": f"月工资 {actual_salary:.0f} 元 × 工龄 {effective_months} 年 = {n_amount:.0f} 元",
            "result": f"{n_amount:.0f} 元"
        })
        steps.append({
            "step": "加1个月代通知金",
            "formula": f"月工资 {actual_salary:.0f} 元 × 1 = {actual_salary:.0f} 元",
            "result": f"{actual_salary:.0f} 元"
        })
        steps.append({
            "step": "合计 N+1",
            "formula": f"{n_amount:.0f} + {actual_salary:.0f} = {total:.0f} 元",
            "result": f"{total:.0f} 元"
        })
    else:
        # 合法解除：N
        total = n_amount
        mode_name = "经济补偿金（N）"
        steps.append({
            "step": "计算经济补偿金 N",
            "formula": f"月工资 {actual_salary:.0f} 元 × 工龄 {effective_months} 年 = {total:.0f} 元",
            "result": f"{total:.0f} 元"
        })
    
    legal_basis = [
        "《劳动合同法》第四十七条：经济补偿按劳动者在本单位工作的年限，每满一年支付一个月工资的标准向劳动者支付",
        "《劳动合同法》第八十七条：用人单位违反本法规定解除或者终止劳动合同的，应当依照本法第四十七条规定的经济补偿标准的二倍向劳动者支付赔偿金"
    ]
    
    return {
        "calc_type": "compensation",
        "calc_type_name": f"经济补偿金计算 - {mode_name}",
        "params_used": {
            "月工资": monthly_salary,
            "实际计算工资": actual_salary,
            "工作年限": work_years,
            "有效计算年限": effective_months,
            "辞退类型": dismissal_type,
            "计算模式": mode_name
        },
        "calculation_steps": steps,
        "total_amount": total,
        "total_amount_text": _amount_to_chinese(total),
        "legal_basis": legal_basis,
        "notes": high_salary_note or "无特殊限制"
    }


def calculate_penalty(params: dict) -> dict:
    """合同违约金计算
    
    法律依据：《民法典》第585条
    """
    contract_amount = float(params.get("contract_amount", 0))
    penalty_rate = float(params.get("penalty_rate", 0))
    breach_days = params.get("breach_days")  # 可选
    
    steps = []
    
    if breach_days and float(breach_days) > 0:
        # 按日计算
        daily_rate = penalty_rate
        total = contract_amount * daily_rate * float(breach_days)
        steps.append({
            "step": "计算每日违约金",
            "formula": f"合同金额 {contract_amount:.0f} 元 × 日比例 {daily_rate}",
            "result": f"{contract_amount * daily_rate:.2f} 元/天"
        })
        steps.append({
            "step": "计算总违约金",
            "formula": f"每日违约金 × 违约天数 {breach_days} 天",
            "result": f"{total:.2f} 元"
        })
    else:
        # 按比例计算
        total = contract_amount * penalty_rate
        steps.append({
            "step": "计算违约金",
            "formula": f"合同金额 {contract_amount:.0f} 元 × 违约金比例 {penalty_rate*100:.1f}%",
            "result": f"{total:.2f} 元"
        })
    
    # 检查是否超过30%上限
    cap_amount = contract_amount * 0.3
    over_cap = total > cap_amount
    if over_cap:
        steps.append({
            "step": "上限检查",
            "formula": f"违约金 {total:.0f} 元 > 合同金额30% = {cap_amount:.0f} 元",
            "result": "⚠️ 违约金可能过高，对方可请求法院调整"
        })
    
    legal_basis = [
        "《民法典》第五百八十五条：当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金",
        "《民法典》第五百八十五条第二款：约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少"
    ]
    
    return {
        "calc_type": "penalty",
        "calc_type_name": "合同违约金计算",
        "params_used": {
            "合同金额": contract_amount,
            "违约金比例": f"{penalty_rate*100:.1f}%",
            "违约天数": breach_days or "未指定"
        },
        "calculation_steps": steps,
        "total_amount": total,
        "total_amount_text": _amount_to_chinese(total),
        "legal_basis": legal_basis,
        "notes": f"违约金上限提示：合同金额的30%为 {cap_amount:.0f} 元，超过此金额可能被认定为过高" if over_cap else "违约金在合理范围内"
    }


def calculate_interest(params: dict) -> dict:
    """逾期利息计算
    
    法律依据：《民法典》第676条、最高法民间借贷司法解释
    """
    principal = float(params.get("principal", 0))
    annual_rate = float(params.get("annual_rate", 0))
    overdue_days = int(params.get("overdue_days", 0))
    
    # 日利率 = 年利率 / 365
    daily_rate = annual_rate / 365
    
    total = principal * daily_rate * overdue_days
    
    steps = [
        {
            "step": "计算日利率",
            "formula": f"年利率 {annual_rate*100:.2f}% ÷ 365 = {daily_rate*100:.6f}%/天",
            "result": f"日利率 {daily_rate:.8f}"
        },
        {
            "step": "计算逾期利息",
            "formula": f"本金 {principal:.0f} 元 × 日利率 × {overdue_days} 天",
            "result": f"{total:.2f} 元"
        }
    ]
    
    # LPR 参考（2024年1年期LPR约3.45%）
    lpr_1year = 0.0345
    lpr_4x = lpr_1year * 4
    
    if annual_rate > lpr_4x:
        steps.append({
            "step": "利率合法性检查",
            "formula": f"约定年利率 {annual_rate*100:.2f}% > LPR 4倍 = {lpr_4x*100:.2f}%",
            "result": "⚠️ 利率超过法律保护上限，超出部分不受法律保护"
        })
    
    legal_basis = [
        "《民法典》第六百七十六条：借款人未按照约定的期限返还借款的，应当按照约定或者国家有关规定支付逾期利息",
        "《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》：出借人请求借款人按照合同约定利率支付利息的，人民法院应予支持，但是双方约定的利率超过合同成立时一年期贷款市场报价利率四倍的除外"
    ]
    
    return {
        "calc_type": "interest",
        "calc_type_name": "逾期利息计算",
        "params_used": {
            "本金": principal,
            "年利率": f"{annual_rate*100:.2f}%",
            "逾期天数": overdue_days,
            "日利率": f"{daily_rate*100:.6f}%"
        },
        "calculation_steps": steps,
        "total_amount": total,
        "total_amount_text": _amount_to_chinese(total),
        "legal_basis": legal_basis,
        "notes": f"当前1年期LPR为{lpr_1year*100:.2f}%，法律保护上限为{lpr_4x*100:.2f}%"
    }


def calculate_injury(params: dict) -> dict:
    """人身损害赔偿计算
    
    法律依据：《民法典》第1179条、《人身损害赔偿司法解释》
    """
    disability_level = int(params.get("disability_level", 0))  # 1-10
    avg_salary = float(params.get("avg_salary", 0))  # 当地职工年平均工资
    medical_expenses = float(params.get("medical_expenses", 0))
    lost_wages = float(params.get("lost_wages", 0))
    care_days = int(params.get("care_days", 0))
    care_standard = float(params.get("care_standard", 0))
    
    # 伤残系数：一级100%，二级90%...十级10%
    disability_coefficient = (11 - disability_level) / 10.0 if disability_level > 0 else 0
    
    steps = []
    total = 0
    
    # 1. 残疾赔偿金
    if disability_level > 0 and avg_salary > 0:
        disability_compensation = avg_salary * 20 * disability_coefficient
        steps.append({
            "step": "残疾赔偿金",
            "formula": f"年平均工资 {avg_salary:.0f} 元 × 20年 × 伤残系数 {disability_coefficient*100:.0f}%",
            "result": f"{disability_compensation:.0f} 元"
        })
        total += disability_compensation
    elif disability_level > 0:
        # 使用默认年平均工资（参考全国城镇非私营单位就业人员年平均工资约11万）
        default_avg = 110000
        disability_compensation = default_avg * 20 * disability_coefficient
        steps.append({
            "step": f"残疾赔偿金（使用参考值）",
            "formula": f"参考年平均工资 {default_avg} 元 × 20年 × 伤残系数 {disability_coefficient*100:.0f}%",
            "result": f"{disability_compensation:.0f} 元"
        })
        total += disability_compensation
    
    # 2. 医疗费
    if medical_expenses > 0:
        steps.append({
            "step": "医疗费",
            "formula": f"按实际发生额 {medical_expenses:.0f} 元",
            "result": f"{medical_expenses:.0f} 元"
        })
        total += medical_expenses
    
    # 3. 误工费
    if lost_wages > 0:
        steps.append({
            "step": "误工费",
            "formula": f"按实际减少的收入计算 {lost_wages:.0f} 元",
            "result": f"{lost_wages:.0f} 元"
        })
        total += lost_wages
    
    # 4. 护理费
    if care_days > 0 and care_standard > 0:
        care_amount = care_standard * care_days
        steps.append({
            "step": "护理费",
            "formula": f"护理标准 {care_standard:.0f} 元/天 × {care_days} 天",
            "result": f"{care_amount:.0f} 元"
        })
        total += care_amount
    
    legal_basis = [
        "《民法典》第一千一百七十九条：侵害他人造成人身损害的，应当赔偿医疗费、护理费、交通费、营养费、住院伙食补助费等为治疗和康复支出的合理费用，以及因误工减少的收入",
        "《最高人民法院关于审理人身损害赔偿案件适用法律若干问题的解释》",
        "伤残等级对应系数：一级100%、二级90%、三级80%、四级70%、五级60%、六级50%、七级40%、八级30%、九级20%、十级10%"
    ]
    
    return {
        "calc_type": "injury",
        "calc_type_name": "人身损害赔偿计算",
        "params_used": {
            "伤残等级": f"{disability_level}级" if disability_level else "未评定",
            "伤残系数": f"{disability_coefficient*100:.0f}%" if disability_level else "N/A",
            "医疗费": medical_expenses,
            "误工费": lost_wages,
            "护理天数": care_days,
            "护理标准": care_standard
        },
        "calculation_steps": steps,
        "total_amount": total,
        "total_amount_text": _amount_to_chinese(total),
        "legal_basis": legal_basis,
        "notes": "伤残赔偿金按20年计算。60周岁以上的，年龄每增加一岁减少一年；75周岁以上的，按5年计算。"
    }


def calculate_support(params: dict) -> dict:
    """抚养费/赡养费计算
    
    法律依据：《民法典》第1067条、第1085条
    """
    payer_income = float(params.get("payer_income", 0))
    children_count = int(params.get("children_count", 1))
    support_ratio = params.get("support_ratio")  # 可选
    
    steps = []
    
    if support_ratio:
        # 用户指定了比例
        ratio = float(support_ratio)
        monthly = payer_income * ratio
    else:
        # 按法定比例
        if children_count == 1:
            ratio = 0.25  # 一般20%-30%，取中间值
            monthly = payer_income * ratio
        elif children_count == 2:
            ratio = 0.40  # 两个子女一般40%左右
            monthly = payer_income * ratio
        else:
            ratio = 0.50  # 多个子女不超过50%
            monthly = payer_income * ratio
    
    annual = monthly * 12
    
    steps.append({
        "step": "确定抚养费比例",
        "formula": f"支付方月收入 {payer_income:.0f} 元，抚养{children_count}个子女，适用比例 {ratio*100:.0f}%",
        "result": f"月付 {monthly:.0f} 元"
    })
    steps.append({
        "step": "计算年抚养费",
        "formula": f"月付 {monthly:.0f} 元 × 12个月",
        "result": f"{annual:.0f} 元/年"
    })
    
    # 计算到18岁的总额（假设当前子女年龄）
    child_age = int(params.get("child_age", 0))
    if child_age > 0 and child_age < 18:
        remaining_years = 18 - child_age
        total_until_18 = annual * remaining_years
        steps.append({
            "step": f"计算至子女18岁总额（假设当前{child_age}岁）",
            "formula": f"年抚养费 {annual:.0f} 元 × 剩余 {remaining_years} 年",
            "result": f"{total_until_18:.0f} 元"
        })
    
    legal_basis = [
        "《民法典》第一千零六十七条：父母不履行抚养义务的，未成年子女或者不能独立生活的成年子女，有要求父母给付抚养费的权利",
        "《民法典》第一千零八十五条：离婚后，子女由一方直接抚养的，另一方应当负担部分或者全部抚养费",
        "《最高人民法院关于适用〈中华人民共和国民法典〉婚姻家庭编的解释（一）》第四十九条：抚养费的数额，可以根据子女的实际需要、父母双方的负担能力和当地的实际生活水平确定。有固定收入的，抚养费一般可以按其月总收入的百分之二十至三十的比例给付"
    ]
    
    return {
        "calc_type": "support",
        "calc_type_name": "抚养费计算",
        "params_used": {
            "支付方月收入": payer_income,
            "子女数量": children_count,
            "适用比例": f"{ratio*100:.0f}%"
        },
        "calculation_steps": steps,
        "total_amount": monthly,  # 月付金额
        "total_amount_text": f"每月 {_amount_to_chinese(monthly)}",
        "legal_basis": legal_basis,
        "notes": "抚养费比例可在20%-30%之间调整，具体由法院根据子女实际需要、父母负担能力和当地生活水平确定。"
    }


def _amount_to_chinese(amount: float) -> str:
    """将数字金额转换为中文大写"""
    if amount == 0:
        return "零元整"
    
    digits = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
    units_int = ['', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿', '拾', '佰', '仟']
    units_dec = ['角', '分']
    
    # 分离整数和小数部分
    amount_int = int(amount)
    amount_dec = round((amount - amount_int) * 100)
    
    result = ""
    
    if amount_int == 0:
        result = "零"
    else:
        str_int = str(amount_int)
        length = len(str_int)
        for i, d in enumerate(str_int):
            digit = int(d)
            pos = length - 1 - i
            if digit != 0:
                result += digits[digit] + units_int[pos]
            else:
                if result and not result.endswith('零'):
                    result += '零'
        result = result.rstrip('零')
    
    result += "元"
    
    if amount_dec == 0:
        result += "整"
    else:
        jiao = amount_dec // 10
        fen = amount_dec % 10
        if jiao > 0:
            result += digits[jiao] + "角"
        elif fen > 0:
            result += "零"
        if fen > 0:
            result += digits[fen] + "分"
    
    return result
