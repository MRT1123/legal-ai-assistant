"""
单元测试 - 法律计算器模块

覆盖场景：
- 经济补偿金（N / 2N / N+1 三种模式）
- 高收入上限截断
- 合同违约金（按比例 / 按日 / 30%上限提示）
- 逾期利息（含 LPR 4倍合法性检查）
- 人身损害赔偿（伤残等级系数）
- 抚养费（1/2/多个子女比例）
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.agent.legal_calculator.calculators import (
    calculate_compensation,
    calculate_penalty,
    calculate_interest,
    calculate_injury,
    calculate_support,
    _amount_to_chinese,
)


# ==================== 经济补偿金 ====================

class TestCompensation:
    """经济补偿金计算"""

    def test_legal_dismissal_n(self):
        """合法解除 = N"""
        result = calculate_compensation({
            "monthly_salary": 10000,
            "work_years": 3,
            "dismissal_type": "legal"
        })
        assert result["total_amount"] == 30000  # 10000 * 3
        assert "N" in result["calc_type_name"]

    def test_illegal_dismissal_2n(self):
        """违法解除 = 2N"""
        result = calculate_compensation({
            "monthly_salary": 10000,
            "work_years": 3,
            "dismissal_type": "illegal"
        })
        assert result["total_amount"] == 60000  # 10000 * 3 * 2

    def test_no_notice_n_plus_1(self):
        """未提前通知 = N+1"""
        result = calculate_compensation({
            "monthly_salary": 10000,
            "work_years": 3,
            "dismissal_type": "no_notice"
        })
        assert result["total_amount"] == 40000  # 10000*3 + 10000

    def test_high_salary_cap(self):
        """高收入超过社平3倍，按上限且年限最多12年"""
        result = calculate_compensation({
            "monthly_salary": 100000,  # 远超15000*3=45000
            "work_years": 20,
            "dismissal_type": "legal",
            "local_avg_salary": 15000
        })
        # 按上限45000 * 12年
        assert result["total_amount"] == 45000 * 12
        assert result["notes"] is not None  # 应该有上限提示

    def test_fractional_years(self):
        """工龄含小数：超过6个月按1年，不足6个月按0.5年"""
        result = calculate_compensation({
            "monthly_salary": 10000,
            "work_years": 3.7,  # 3年7个月 -> 4年
            "dismissal_type": "legal"
        })
        assert result["total_amount"] == 40000  # 10000 * 4

    def test_half_year(self):
        """工龄含0.5年"""
        result = calculate_compensation({
            "monthly_salary": 10000,
            "work_years": 3.3,  # 3年3个月 -> 3.5年
            "dismissal_type": "legal"
        })
        assert result["total_amount"] == 35000  # 10000 * 3.5

    def test_has_steps(self):
        """结果包含计算步骤"""
        result = calculate_compensation({
            "monthly_salary": 8000,
            "work_years": 2,
            "dismissal_type": "legal"
        })
        assert len(result["calculation_steps"]) > 0
        assert result["total_amount"] == 16000

    def test_has_legal_basis(self):
        """结果包含法律依据"""
        result = calculate_compensation({
            "monthly_salary": 8000,
            "work_years": 2,
            "dismissal_type": "legal"
        })
        assert len(result["legal_basis"]) > 0
        assert "劳动合同法" in result["legal_basis"][0]


# ==================== 合同违约金 ====================

class TestPenalty:
    """合同违约金计算"""

    def test_basic_penalty(self):
        """基本违约金"""
        result = calculate_penalty({
            "contract_amount": 100000,
            "penalty_rate": 0.1
        })
        assert result["total_amount"] == 10000

    def test_daily_penalty(self):
        """按日计算违约金"""
        result = calculate_penalty({
            "contract_amount": 100000,
            "penalty_rate": 0.001,
            "breach_days": 30
        })
        # 100000 * 0.001 * 30 = 3000
        assert result["total_amount"] == 3000

    def test_over_30_percent_warning(self):
        """违约金超过合同金额30%应提示"""
        result = calculate_penalty({
            "contract_amount": 100000,
            "penalty_rate": 0.5  # 50% > 30%
        })
        assert result["total_amount"] == 50000
        assert "过高" in result["notes"] or "上限" in result["notes"]


# ==================== 逾期利息 ====================

class TestInterest:
    """逾期利息计算"""

    def test_basic_interest(self):
        """基本利息计算"""
        result = calculate_interest({
            "principal": 100000,
            "annual_rate": 0.05,
            "overdue_days": 365
        })
        # 100000 * (0.05/365) * 365 = 5000
        assert abs(result["total_amount"] - 5000) < 1

    def test_lpr_exceed_warning(self):
        """利率超过LPR 4倍应提示"""
        result = calculate_interest({
            "principal": 100000,
            "annual_rate": 0.20,  # 20% > LPR 4倍(13.8%)
            "overdue_days": 30
        })
        # 应该在步骤中有合法性检查
        has_check = any("合法性" in step.get("step", "") for step in result["calculation_steps"])
        assert has_check


# ==================== 人身损害赔偿 ====================

class TestInjury:
    """人身损害赔偿计算"""

    def test_disability_level_10(self):
        """十级伤残，系数10%"""
        result = calculate_injury({
            "disability_level": 10,
            "avg_salary": 100000,
            "medical_expenses": 5000
        })
        # 伤残赔偿金 = 100000 * 20 * 0.1 = 200000
        disability_part = 100000 * 20 * 0.1
        assert result["total_amount"] == disability_part + 5000

    def test_disability_level_1(self):
        """一级伤残，系数100%"""
        result = calculate_injury({
            "disability_level": 1,
            "avg_salary": 80000
        })
        # 80000 * 20 * 1.0 = 1600000
        assert result["total_amount"] == 1600000

    def test_no_disability(self):
        """未评定伤残等级"""
        result = calculate_injury({
            "disability_level": 0,
            "medical_expenses": 10000,
            "lost_wages": 5000
        })
        assert result["total_amount"] == 15000

    def test_with_care_fee(self):
        """含护理费"""
        result = calculate_injury({
            "disability_level": 8,
            "avg_salary": 80000,
            "medical_expenses": 10000,
            "care_days": 30,
            "care_standard": 200
        })
        # 伤残: 80000*20*0.3 = 480000
        # 医疗: 10000
        # 护理: 200*30 = 6000
        expected = 480000 + 10000 + 6000
        assert result["total_amount"] == expected


# ==================== 抚养费 ====================

class TestSupport:
    """抚养费计算"""

    def test_one_child(self):
        """一个子女，比例25%"""
        result = calculate_support({
            "payer_income": 10000,
            "children_count": 1
        })
        assert result["total_amount"] == 2500  # 10000 * 25%

    def test_two_children(self):
        """两个子女，比例40%"""
        result = calculate_support({
            "payer_income": 10000,
            "children_count": 2
        })
        assert result["total_amount"] == 4000  # 10000 * 40%

    def test_custom_ratio(self):
        """用户指定比例"""
        result = calculate_support({
            "payer_income": 10000,
            "children_count": 1,
            "support_ratio": 0.3
        })
        assert result["total_amount"] == 3000  # 10000 * 30%


# ==================== 金额转中文 ====================

class TestAmountToChinese:
    """金额转中文大写"""

    def test_zero(self):
        assert _amount_to_chinese(0) == "零元整"

    def test_simple_amount(self):
        result = _amount_to_chinese(10000)
        assert "元" in result

    def test_amount_with_decimal(self):
        result = _amount_to_chinese(100.50)
        assert "角" in result
