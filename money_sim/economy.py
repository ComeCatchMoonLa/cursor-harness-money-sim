"""纯公式。结算和预览都走这里，避免界面另算一套数。"""

from __future__ import annotations

import math

from money_sim.constants import (
    BASE_LIVING,
    NETWORK_SALARY_DEN,
    PART_TIME_DEN,
    PART_TIME_NUM,
    PRICE_START,
    SALARY_BASE,
    SALARY_PER_SKILL,
)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def clamp_return(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def salary(career: int, network: int, employment: str) -> int:
    full = SALARY_BASE + career * SALARY_PER_SKILL
    full = full * (NETWORK_SALARY_DEN + network) // NETWORK_SALARY_DEN
    if employment == "full":
        return full
    if employment == "part":
        return full * PART_TIME_NUM // PART_TIME_DEN
    return 0


def living_cost(lifestyle: int, price_index: int) -> int:
    return BASE_LIVING * lifestyle // 100 * price_index // PRICE_START


def learn_gain(skill: int) -> int:
    return max(1, int(round(8 * (1 - skill / 140))))


def exit_pct(stage: str, last_business_net: int, offer_pct: int, accept_offer: bool) -> int:
    if accept_offer and offer_pct > 0:
        return offer_pct
    if stage == "building":
        return 90
    if stage == "running":
        return 62 if last_business_net > 0 else 48
    return 0


def _capital_factor(book: int) -> float:
    """资金会把店撑起来，但很快饱和。再往后只有成本在涨。"""
    if book <= 0:
        return 0.0
    return 1.35 * (1 - math.exp(-book / 36_000))


def business_gross(
    book: int,
    venture: int,
    demand_bp: int,
    attention: int,
    automated: bool,
    autonomy: int,
) -> int:
    """亲自经营才有完整收入。没人照看会塌；雇人能保住大部分，但不是第二份工资。"""
    if book <= 0:
        return 0
    skill_f = 0.42 + venture * 0.008
    gross = int(12_500 * skill_f * _capital_factor(book) * (demand_bp / 100))
    # 一个时间槽只能维持，两个槽才是在做这家店。更多槽有用，但不再线性加钱。
    if attention <= 0 and not automated:
        gross = gross * 8 // 100
    elif attention <= 0 and automated:
        gross = gross * 82 // 100
    elif attention == 1:
        gross = gross * 48 // 100
    elif attention >= 4:
        gross = gross * 138 // 100
    elif attention == 3:
        gross = gross * 122 // 100
    if autonomy >= 65 and attention > 0:
        gross = gross * 106 // 100
    return gross


def business_opex(book: int, automated: bool) -> int:
    staff = 4_500 if automated else 0
    return 1_000 + book // 2_000 + staff


def demand_bp(regime: str, network: int, noise_bp: int) -> int:
    base = {"bull": 112, "chop": 100, "bear": 78}[regime]
    return base * (500 + network) // 500 * noise_bp // 100


def index_distribution(skill: int, regime: str) -> tuple[float, float, float, float]:
    mu = 0.004 + skill * 0.000012
    sigma = max(0.028, 0.042 - skill * 0.00006)
    if regime == "bull":
        mu += 0.003
    elif regime == "bear":
        mu -= 0.007
    return mu, sigma, -0.28, 0.22


def risk_distribution(skill: int, regime: str) -> tuple[float, float, float, float]:
    mu = 0.006 + skill * 0.00002
    sigma = 0.08
    if regime == "bull":
        mu += 0.004
    elif regime == "bear":
        mu -= 0.012
    return mu, sigma, -0.45, 0.40


def consume_lifestyle_gain(spend: int) -> int:
    return min(4, max(1, spend // 10_000))


def consume_stress_relief(spend: int) -> int:
    return min(22, spend // 1_500)


def consume_network_gain(spend: int) -> int:
    return min(8, max(1, spend // 3_000))
