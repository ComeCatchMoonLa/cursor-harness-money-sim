"""月度校验与结算。现金、指数、账面、负债只通过分录变动。"""

from __future__ import annotations

from money_sim.constants import (
    BREACH_MONTHS,
    BREACH_STRESS,
    BUILD_COST,
    BUILDS_TO_LAUNCH,
    BURNOUT_LIMIT,
    CONTRACT_TERMS,
    DEBT_CAP,
    DEBT_RATE_DEN,
    DEBT_RATE_NUM,
    DISTRESS_EXIT_DEN,
    DISTRESS_EXIT_NUM,
    EMERGENCY_FEE_DEN,
    EMERGENCY_FEE_NUM,
    INDEX_SELL_FEE_DEN,
    INDEX_SELL_FEE_NUM,
    LEAVE_STRESS,
    LEGAL_SLOTS,
    LOCK_MU_BONUS,
    LOCK_TERM,
    LOW_ENERGY_FULL,
    MIN_CONSUME,
    MONTHS,
    OFFER_P,
    PRICE_GROWTH_DEN,
    PRICE_GROWTH_NUM,
    REGEN,
    REGIME_SWITCH_P,
    STRESS_BLOCK_REGEN,
    TOTAL_SLOTS,
    TRIAL_DEMAND_NUM,
    TRIAL_MONTHS,
    TUITION,
    UNLOCK_HAIRCUT_DEN,
    UNLOCK_HAIRCUT_NUM,
    WIN_NET,
    WORK_AUTONOMY,
    WORK_ENERGY,
    WORK_SLOTS,
    WORK_STRESS,
    SLOT_ENERGY,
    SLOT_STRESS,
)
from money_sim.economy import (
    business_gross,
    business_opex,
    clamp,
    clamp_return,
    consume_lifestyle_gain,
    consume_network_gain,
    consume_stress_relief,
    demand_bp,
    exit_pct,
    index_distribution,
    learn_gain,
    living_cost,
    risk_distribution,
    salary,
)
from money_sim.state import GameState, Plan, net_worth, realizable_net, rng_of, store_rng


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def commitment(state: GameState, plan: Plan) -> dict:
    """合同把就业锁死。精力不够时这个月停薪请假，而不是把局卡死。"""
    bound = state.contract_left > 0 and not plan.break_contract
    leave = bound and state.energy < LOW_ENERGY_FULL
    if leave:
        employment = "free"
    elif bound:
        employment = "full"
    else:
        employment = plan.employment
    return {
        "employment": employment,
        "bound": bound,
        "leave": leave,
        "contracted_pay": bound and not leave,
    }


def quote(state: GameState, plan: Plan) -> dict:
    """确定性报价。随机收益不在这里。"""
    bound = commitment(state, plan)
    employment = bound["employment"] if bound["employment"] in WORK_SLOTS else "free"
    exiting = bool(plan.exit_business or plan.accept_offer)
    venture_slots = sum(1 for slot in plan.slots if slot == "venture")
    learn_slots = sum(1 for slot in plan.slots if slot.startswith("learn_"))
    consume_slots = sum(1 for slot in plan.slots if slot == "consume")

    start_stage = state.business_stage
    stage = start_stage
    progress = state.business_progress
    builds = 0
    if not exiting and stage not in ("running", "trial"):
        for _ in range(venture_slots):
            if stage in ("running", "trial"):
                break
            builds += 1
            progress += 1
            if stage == "none":
                stage = "building"
            if progress >= BUILDS_TO_LAUNCH:
                stage = "trial"
                progress = BUILDS_TO_LAUNCH
    operating = start_stage in ("trial", "running")
    if exiting:
        stage_after = "none"
        progress_after = 0
        attention = 0
    else:
        stage_after = stage
        progress_after = progress
        attention = venture_slots if operating else 0

    book_for_exit = state.business_book if exiting else 0
    pct = 0
    proceeds = 0
    if exiting and state.business_book > 0 and state.business_stage != "none":
        pct = exit_pct(state.business_stage, state.last_business_net, state.offer_exit_pct, plan.accept_offer)
        proceeds = state.business_book * pct // 100
        book_for_exit = state.business_book

    pay = salary(state.career, state.network, employment)
    bonus = 0
    penalty = 0
    if plan.break_contract and state.contract_left > 0:
        penalty = salary(state.career, state.network, "full") * BREACH_MONTHS
    build_cost = builds * BUILD_COST
    tuition = learn_slots * TUITION
    sell_proceeds = plan.from_index * (INDEX_SELL_FEE_DEN - INDEX_SELL_FEE_NUM) // INDEX_SELL_FEE_DEN
    cash_after = state.cash + pay + bonus + proceeds - penalty - tuition - build_cost - plan.consume_cash
    cash_after -= plan.to_index + plan.to_business + plan.debt_pay
    cash_after += sell_proceeds
    energy_after = state.energy + WORK_ENERGY[employment]
    for slot in plan.slots:
        gain = SLOT_ENERGY[slot]
        # 合同月不能真正下班，休息只能勉强维持。
        if slot == "rest" and bound["contracted_pay"]:
            gain = min(gain, 10)
        energy_after += gain
    return {
        "salary": pay,
        "bonus": bonus,
        "penalty": penalty,
        "leave": bound["leave"],
        "employment": employment,
        "operating": operating,
        "living": living_cost(state.lifestyle, state.price_index),
        "tuition": tuition,
        "build_cost": build_cost,
        "builds": builds,
        "stage_after": stage_after,
        "progress_after": progress_after,
        "will_run": operating,
        "attention": attention,
        "exit_pct": pct,
        "exit_proceeds": proceeds,
        "exit_book": book_for_exit if exiting else 0,
        "sell_proceeds": sell_proceeds,
        "cash_after_choices": cash_after,
        "energy_after": energy_after,
        "learn_slots": learn_slots,
        "consume_slots": consume_slots,
        "exiting": exiting,
    }


def validate(state: GameState, plan: Plan) -> list[str]:
    errors: list[str] = []
    if state.status != "playing":
        return ["本局已结束"]
    if plan.employment not in WORK_SLOTS:
        return ["就业形态无效"]
    bound = commitment(state, plan)
    if plan.sign_months not in (0, *CONTRACT_TERMS):
        errors.append("合同期限只能是 6 或 12 个月")
    if plan.sign_months and plan.break_contract:
        errors.append("同一个月不能又签又违约")
    if plan.sign_months and state.contract_left and not plan.break_contract:
        errors.append("合同没到期，不能再签")
    if plan.sign_months and state.energy < LOW_ENERGY_FULL:
        errors.append("精力不够，这个月签了也上不了班")
    if plan.break_contract and state.contract_left <= 0:
        errors.append("没有合同可违约")
    if bound["leave"]:
        if plan.employment != "free":
            errors.append("这个月是病假，要自己安排时间")
    elif bound["bound"] and plan.employment != "full":
        errors.append("合同没到期")
    elif plan.employment == "full" and state.energy < LOW_ENERGY_FULL:
        errors.append("精力不足，无法全职")
    need = TOTAL_SLOTS - WORK_SLOTS[plan.employment]
    if len(plan.slots) != need:
        errors.append(f"本月应安排 {need} 个自由时间槽")
    for slot in plan.slots:
        if slot not in LEGAL_SLOTS:
            errors.append(f"未知行动：{slot}")
    numbers = {
        "买入指数": plan.to_index,
        "卖出指数": plan.from_index,
        "投入副业": plan.to_business,
        "还债": plan.debt_pay,
        "消费金额": plan.consume_cash,
        "风险仓位": plan.risk_pct,
        "封闭金额": plan.lock_amount,
    }
    for name, value in numbers.items():
        parsed = _as_int(value)
        if parsed is None:
            errors.append(f"{name}必须是整数")
        elif parsed < 0:
            errors.append(f"{name}不能为负")
    if errors:
        return errors
    if plan.risk_pct > 100:
        errors.append("风险仓位不能超过 100")
    if plan.to_index and plan.from_index:
        errors.append("同一个月不能又买又卖指数")
    liquid = state.portfolio - state.locked
    if plan.from_index > max(0, liquid):
        errors.append("封闭的指数不能卖")
    if plan.lock_amount and plan.unlock:
        errors.append("同一个月不能又封闭又解锁")
    if plan.unlock and state.locked <= 0:
        errors.append("没有封闭仓可解锁")
    if plan.lock_amount and state.lock_left > 0:
        errors.append("封闭还没到期")
    if plan.lock_amount > max(0, liquid):
        errors.append("可卖的指数不够封闭")
    if plan.debt_pay > state.debt:
        errors.append("还债不能超过负债")
    if plan.risk_pct > 0 and "invest" not in plan.slots:
        errors.append("没有投资行动就不能提高风险仓位")
    consume_slots = sum(1 for slot in plan.slots if slot == "consume")
    if consume_slots:
        if plan.consume_cash < MIN_CONSUME * consume_slots:
            errors.append("消费行动至少要花一笔钱")
    elif plan.consume_cash:
        errors.append("没有消费行动不能花钱消费")
    exiting = plan.exit_business or plan.accept_offer
    if plan.accept_offer and state.offer_exit_pct <= 0:
        errors.append("这个月没有收购报价")
    if exiting and state.business_stage == "none":
        errors.append("没有副业可退出")
    if exiting and any(slot == "venture" for slot in plan.slots):
        errors.append("退出的同一个月不能再经营副业")
    if exiting and plan.to_business:
        errors.append("退出的同一个月不能再投入副业")
    if plan.to_business and state.business_stage == "none" and "venture" not in plan.slots:
        errors.append("还没有副业，不能只投钱")
    quoted = quote(state, plan)
    if plan.automate and state.business_stage != "running":
        if state.business_stage == "trial":
            errors.append("试营业还不能雇人")
        else:
            errors.append("还没开业，不能雇人")
    if quoted["cash_after_choices"] < 0:
        errors.append("现金不够完成这些支出")
    return errors


def preview(state: GameState, plan: Plan) -> dict:
    errors = validate(state, plan)
    if plan.employment not in WORK_SLOTS or any(slot not in LEGAL_SLOTS for slot in plan.slots):
        return {"ok": False, "errors": errors, "warnings": []}
    quoted = quote(state, plan)
    warnings: list[str] = []
    if quoted["energy_after"] < 0:
        warnings.append("精力会透支。连续三个月透支会过劳，本局失败。")
    if quoted["cash_after_choices"] - quoted["living"] < 0:
        warnings.append("生活费可能让现金为负，并迫使你卖出资产或借债。")
    if state.regime == "bear" and plan.risk_pct > 0:
        warnings.append("收缩期的风险仓更容易大跌。")
    if plan.automate and state.business_book < 150_000:
        warnings.append("账面还不大，雇人的固定成本可能把副业做成亏损。")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "quote": quoted}


def _move(state: GameState, account: str, amount: int, reason: str, ledger: list[dict]) -> None:
    if amount == 0:
        return
    if account == "cash":
        state.cash += amount
    elif account == "portfolio":
        state.portfolio += amount
    elif account == "book":
        state.business_book += amount
    elif account == "debt":
        state.debt += amount
    else:
        raise ValueError(account)
    ledger.append({"account": account, "amount": amount, "reason": reason})


def resolve(state: GameState, plan: Plan) -> tuple[GameState, list[str], dict | None]:
    errors = validate(state, plan)
    if errors:
        return state, errors, None

    s = state.clone()
    rng = rng_of(s)
    ledger: list[dict] = []
    notes: list[str] = []
    quoted = quote(s, plan)
    resolved_month = s.month
    regime = s.regime
    start_autonomy = s.autonomy
    offer_pct = s.offer_exit_pct

    if quoted["exiting"]:
        _move(s, "book", -quoted["exit_book"], "exit_book", ledger)
        _move(s, "cash", quoted["exit_proceeds"], "exit_cash", ledger)
        s.business_stage = "none"
        s.business_progress = 0
        s.automated = False
        s.trial_months = 0
        notes.append(f"退出副业，按账面 {quoted['exit_pct']}% 变现")

    if plan.break_contract:
        _move(s, "cash", -quoted["penalty"], "breach", ledger)
        s.contract_left = 0
        s.contract_term = 0
        s.stress += BREACH_STRESS
        notes.append("违约，付了两个月工资")
    elif plan.sign_months:
        s.contract_left = plan.sign_months
        s.contract_term = plan.sign_months
        _move(s, "cash", quoted["bonus"], "signing_bonus", ledger)
        notes.append(f"签了 {plan.sign_months} 个月全职")
    if quoted["leave"]:
        s.stress += LEAVE_STRESS
        notes.append("合同月请了病假，没有工资")

    _move(s, "cash", quoted["salary"], "salary", ledger)
    if quoted["tuition"]:
        _move(s, "cash", -quoted["tuition"], "tuition", ledger)
    if quoted["build_cost"]:
        _move(s, "cash", -quoted["build_cost"], "build", ledger)
        _move(s, "book", quoted["build_cost"], "build", ledger)
        notes.append("副业建设资金已投入")
    if plan.consume_cash:
        _move(s, "cash", -plan.consume_cash, "consume", ledger)

    s.business_stage = quoted["stage_after"]
    s.business_progress = quoted["progress_after"]
    if quoted["will_run"] and not quoted["exiting"]:
        s.automated = bool(plan.automate)
    elif not quoted["will_run"]:
        s.automated = False

    if plan.to_index:
        _move(s, "cash", -plan.to_index, "buy_index", ledger)
        _move(s, "portfolio", plan.to_index, "buy_index", ledger)
    if plan.from_index:
        _move(s, "portfolio", -plan.from_index, "sell_index", ledger)
        _move(s, "cash", quoted["sell_proceeds"], "sell_index", ledger)
    if plan.to_business:
        _move(s, "cash", -plan.to_business, "inject", ledger)
        _move(s, "book", plan.to_business, "inject", ledger)
    if plan.debt_pay:
        _move(s, "cash", -plan.debt_pay, "debt_pay", ledger)
        _move(s, "debt", -plan.debt_pay, "debt_pay", ledger)

    s.energy = quoted["energy_after"]
    s.stress += WORK_STRESS[quoted["employment"]]
    s.autonomy += WORK_AUTONOMY[quoted["employment"]]
    for slot in plan.slots:
        s.stress += SLOT_STRESS[slot]
        if slot == "rest":
            s.autonomy += 2
        if slot.startswith("learn_"):
            attr = {"learn_career": "career", "learn_venture": "venture", "learn_invest": "invest"}[slot]
            current = getattr(s, attr)
            gain = learn_gain(current)
            if start_autonomy < 28:
                gain = max(1, gain - 2)
            setattr(s, attr, min(100, current + gain))
    if plan.consume_cash:
        s.stress -= consume_stress_relief(plan.consume_cash)
        s.lifestyle += consume_lifestyle_gain(plan.consume_cash)
        s.network += consume_network_gain(plan.consume_cash)

    overdraft = quoted["energy_after"] < 0
    if overdraft:
        s.energy = 0
        s.stress += 18
        s.burnout_streak += 1
        notes.append("精力透支")
    else:
        if s.stress <= STRESS_BLOCK_REGEN:
            s.energy += REGEN

    if plan.unlock and s.locked > 0:
        haircut = s.locked * UNLOCK_HAIRCUT_NUM // UNLOCK_HAIRCUT_DEN
        _move(s, "portfolio", -haircut, "unlock_fee", ledger)
        s.locked = 0
        s.lock_left = 0
        notes.append("提前解锁，扣掉一截封闭仓")

    risk = (plan.risk_pct / 100) if "invest" in plan.slots else 0.0
    mu, sigma, lo, hi = index_distribution(state.invest, regime)
    index_r = clamp_return(rng.gauss(mu, sigma), lo, hi)
    blended = index_r
    if risk > 0:
        mu_r, sigma_r, lo_r, hi_r = risk_distribution(state.invest, regime)
        risk_r = clamp_return(rng.gauss(mu_r, sigma_r), lo_r, hi_r)
        blended = (1 - risk) * index_r + risk * risk_r
    locked_base = min(s.locked, s.portfolio)
    liquid_base = s.portfolio - locked_base
    locked_gain = 0
    if locked_base:
        lock_r = clamp_return(rng.gauss(mu + LOCK_MU_BONUS, sigma), lo, hi)
        locked_gain = int(round(locked_base * lock_r))
    liquid_gain = int(round(liquid_base * blended)) if liquid_base else 0
    invest_return = locked_gain + liquid_gain
    _move(s, "portfolio", invest_return, "invest_pnl", ledger)
    if locked_base:
        s.locked = max(0, min(s.portfolio, locked_base + locked_gain))

    business_net = 0
    gross = 0
    if quoted["operating"] and s.business_stage in ("trial", "running"):
        noise = rng.randint(85, 115)
        demand = demand_bp(regime, state.network, noise)
        if s.business_stage == "trial":
            demand = demand * TRIAL_DEMAND_NUM // 100
        gross = business_gross(
            s.business_book,
            state.venture,
            demand,
            quoted["attention"],
            s.automated,
            start_autonomy,
        )
        opex = business_opex(s.business_book, s.automated)
        business_net = gross - opex
        _move(s, "cash", business_net, "business", ledger)
        s.last_business_net = business_net
        if s.automated and quoted["attention"] <= 0:
            notes.append("雇人看店，这个月没有亲自上阵")
    elif not quoted["exiting"]:
        s.last_business_net = 0

    live = living_cost(s.lifestyle, s.price_index)
    _move(s, "cash", -live, "living", ledger)
    if s.debt > 0:
        interest = s.debt * DEBT_RATE_NUM // DEBT_RATE_DEN
        _move(s, "cash", -interest, "interest", ledger)

    event = _apply_event(s, rng, quoted["employment"], quoted["salary"], gross, ledger, notes)
    _settle_liquidity(s, ledger, notes)

    if not overdraft:
        s.energy = clamp(s.energy, 0, 100)
        if s.energy <= 8:
            s.burnout_streak += 1
        else:
            s.burnout_streak = 0
    else:
        s.energy = 0
    s.stress = clamp(s.stress, 0, 100)
    s.autonomy = clamp(s.autonomy, 8, 96)
    s.career = clamp(s.career, 0, 100)
    s.venture = clamp(s.venture, 0, 100)
    s.invest = clamp(s.invest, 0, 100)
    s.network = clamp(max(0, s.network - 2), 0, 100)
    if "consume" not in plan.slots:
        s.lifestyle = max(100, s.lifestyle - 1)
    s.lifestyle = clamp(s.lifestyle, 100, 220)

    s.price_index = s.price_index * PRICE_GROWTH_NUM // PRICE_GROWTH_DEN
    if rng.random() < REGIME_SWITCH_P:
        choices = [item for item in ("bull", "chop", "bear") if item != s.regime]
        s.regime = rng.choice(choices)
        notes.append("景气变了")

    if s.business_stage == "trial" and quoted["operating"]:
        s.trial_months += 1
        if s.trial_months >= TRIAL_MONTHS:
            s.business_stage = "running"
            notes.append("试营业结束，可以雇人，也可以等收购")
    if s.contract_left > 0:
        s.contract_left -= 1
    if s.lock_left > 0:
        s.lock_left -= 1
        if s.lock_left == 0:
            s.locked = 0
            notes.append("封闭到期，指数可以卖了")
    if plan.lock_amount and s.lock_left == 0 and s.locked == 0:
        s.locked = min(plan.lock_amount, s.portfolio)
        s.lock_left = LOCK_TERM
        notes.append(f"封闭 {s.locked} 元指数，{LOCK_TERM} 个月内不能卖")

    worth = realizable_net(s)
    fail_reason = None
    if s.status == "playing" and worth >= WIN_NET:
        s.status = "won"
    elif s.status == "playing" and s.burnout_streak >= BURNOUT_LIMIT:
        s.status = "burnout"
        fail_reason = "burnout"

    if s.status == "bankrupt":
        fail_reason = "bankrupt"
        report_type = "fail"
    elif s.status == "burnout":
        report_type = "fail"
    elif s.status == "won":
        report_type = "win"
    else:
        report_type = "month_end"

    s.month += 1
    if s.status == "playing" and resolved_month >= MONTHS:
        s.status = "shortfall"
        report_type = "shortfall"

    s.offer_exit_pct = 0
    if s.status == "playing" and s.business_stage == "running" and s.business_book >= 20_000:
        if rng.random() < OFFER_P:
            s.offer_exit_pct = rng.randint(78, 92)
            notes.append(f"下月有收购报价，账面的 {s.offer_exit_pct}%")

    s.history.append(realizable_net(s))
    store_rng(s, rng)
    report = {
        "type": report_type,
        "month": resolved_month,
        "status": s.status,
        "fail_reason": fail_reason,
        "cash": s.cash,
        "portfolio": s.portfolio,
        "business_book": s.business_book,
        "debt": s.debt,
        "net_worth": net_worth(s),
        "energy": s.energy,
        "stress": s.stress,
        "autonomy": s.autonomy,
        "salary": quoted["salary"],
        "living": live,
        "business_net": business_net,
        "invest_return": invest_return,
        "event": event,
        "realizable": realizable_net(s),
        "regime": regime,
        "employment": plan.employment,
        "slots": list(plan.slots),
        "notes": notes,
        "ledger": ledger,
        "offer_exit_pct": offer_pct,
    }
    s.last_report = report
    return s, [], report


def _apply_event(state, rng, employment, salary_paid, gross, ledger, notes) -> str:
    options: list[tuple[str, float]] = []
    if state.stress > 55:
        options.append(("medical", 0.08))
    if employment in ("full", "part") and state.contract_left <= 0:
        chance = 0.025
        if state.stress > 70:
            chance += 0.05
        if state.regime == "bear":
            chance += 0.04
        options.append(("layoff", chance))
    if state.business_stage in ("trial", "running"):
        options.append(("setback", 0.05))
        options.append(("boom", 0.05))
    roll = rng.random()
    cursor = 0.0
    picked = "none"
    for name, chance in options:
        cursor += chance
        if roll < cursor:
            picked = name
            break
    if picked == "medical":
        cost = rng.randint(6, 16) * 1_000
        _move(state, "cash", -cost, "medical", ledger)
        state.stress = max(0, state.stress - 6)
        notes.append(f"医疗支出 {cost} 元")
    elif picked == "layoff":
        _move(state, "cash", -salary_paid, "layoff_clawback", ledger)
        severance = salary_paid // 2
        _move(state, "cash", severance, "severance", ledger)
        state.stress = min(100, state.stress + 12)
        notes.append("被裁员，本月工资改成遣散费")
    elif picked == "setback":
        kept = state.business_book * 82 // 100
        loss = state.business_book - kept
        _move(state, "book", -loss, "setback", ledger)
        notes.append("副业受挫，账面缩水")
    elif picked == "boom":
        bonus = min(12_000, max(1_000, gross // 2))
        _move(state, "cash", bonus, "boom", ledger)
        notes.append("旺季多了一笔有上限的进账")
    return picked


def _settle_liquidity(state: GameState, ledger: list[dict], notes: list[str]) -> None:
    sold_index = False
    while state.cash < 0 and state.portfolio - state.locked > 0:
        need = -state.cash
        unit = EMERGENCY_FEE_DEN - EMERGENCY_FEE_NUM
        sell = (need * EMERGENCY_FEE_DEN + unit - 1) // unit
        sell = min(max(0, state.portfolio - state.locked), max(1, sell))
        if sell <= 0:
            break
        got = sell * unit // EMERGENCY_FEE_DEN
        _move(state, "portfolio", -sell, "emergency_sell", ledger)
        if got <= 0:
            break
        _move(state, "cash", got, "emergency_sell", ledger)
        sold_index = True
    if sold_index:
        notes.append("现金不够，被迫卖出指数")
    if state.cash < 0 and state.business_book > 0:
        proceeds = state.business_book * DISTRESS_EXIT_NUM // DISTRESS_EXIT_DEN
        _move(state, "book", -state.business_book, "distress_book", ledger)
        _move(state, "cash", proceeds, "distress_cash", ledger)
        state.business_stage = "none"
        state.business_progress = 0
        state.automated = False
        state.trial_months = 0
        notes.append("现金不够，副业被贱卖")
    if state.cash < 0:
        room = DEBT_CAP - state.debt
        draw = min(max(0, room), -state.cash)
        if draw:
            _move(state, "debt", draw, "borrow", ledger)
            _move(state, "cash", draw, "borrow", ledger)
            notes.append("借入高息负债")
    if state.cash < 0:
        state.status = "bankrupt"
        notes.append("资产和负债额度都用尽，破产")
