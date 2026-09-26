"""月度校验与结算。现金、指数、账面、负债只通过分录变动。"""

from __future__ import annotations

from money_sim.constants import (
    BREACH_MONTHS,
    BREACH_STRESS,
    BUILD_COST,
    BUILDS_TO_LAUNCH,
    BURNOUT_LIMIT,
    CONDITION_LOW,
    CONSUME_AUTONOMY,
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
    FRESH_LEARN_EARLY,
    FRESH_LEARN_LATE,
    FRESH_PRACTICE,
    LATE_FRESH_MONTH,
    SHOCK_BOOK_PCT,
    SHOCK_INDEX_PCT,
    HOME_DISTRESS_KEEP,
    JOB_OFFER_AUTONOMY,
    JOB_OFFER_FRESH,
    JOB_OFFER_MONTHS,
    JOB_OFFER_P_FRESH,
    JOB_OFFER_P_STALE,
    HOME_DRIFT,
    HOME_SELL_COST,
    MORTGAGE_RATE_DEN,
    MORTGAGE_RATE_NUM,
    SHOCK_MEDICAL,
    SHOCK_MEDICAL_STRESS,
    SHOCK_P,
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
    condition_after,
    consume_lifestyle_gain,
    consume_network_gain,
    consume_outlook,
    consume_stress_relief,
    contract_rest_gain,
    demand_bp,
    down_and_loan,
    ease_position,
    exit_pct,
    home_maintenance,
    home_price,
    home_proceeds,
    index_distribution,
    learn_gain,
    living_cost,
    mortgage_payment,
    outside_offer,
    rent_of,
    risk_distribution,
    rust_step,
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
    leave = bound and (state.energy < LOW_ENERGY_FULL or state.condition < CONDITION_LOW)
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


def housing_bill(state: GameState) -> int:
    full = living_cost(state.lifestyle, state.price_index)
    bill = full - rent_of(full) if state.home_value else full
    if state.home_value:
        bill += state.mortgage_payment + home_maintenance(state.home_value)
    return bill


def ease_of(state: GameState) -> dict:
    return ease_position(realizable_net(state), state.month, state.career, state.network, housing_bill(state))


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

    taking_offer = bool(plan.accept_job and state.pending_offer > 0 and employment == "full" and not bound["leave"])
    if taking_offer:
        pay = 0
    elif state.offer_left > 0 and employment == "full" and not state.offer_gap:
        pay = state.offer_pay
    else:
        pay = salary(state.career, state.network, employment)
    bonus = 0
    penalty = 0
    if plan.break_contract and state.contract_left > 0:
        penalty = salary(state.career, state.network, "full") * BREACH_MONTHS
    build_cost = builds * BUILD_COST
    tuition = learn_slots * TUITION
    sell_proceeds = plan.from_index * (INDEX_SELL_FEE_DEN - INDEX_SELL_FEE_NUM) // INDEX_SELL_FEE_DEN
    price = home_price(state.price_index)
    down, loan = down_and_loan(price)
    buying = bool(plan.buy_home)
    selling_home = bool(plan.sell_home and state.home_value > 0 and not buying)
    will_own = (state.home_value > 0 and not selling_home) or buying
    home_pay = mortgage_payment(loan) if buying else (state.mortgage_payment if will_own else 0)
    maint = home_maintenance(price if buying else state.home_value) if will_own else 0
    outlook = consume_outlook(state.lifestyle, state.price_index, plan.consume_cash, consume_slots > 0)
    charged_full = living_cost(outlook["charged_lifestyle"], state.price_index)
    charged_living = charged_full - rent_of(charged_full) if will_own else charged_full
    sale_net = 0
    if selling_home:
        sale_net = home_proceeds(state.home_value, 100 - HOME_SELL_COST) - state.mortgage
    cash_after = state.cash + pay + bonus + proceeds - penalty - tuition - build_cost - plan.consume_cash
    cash_after -= plan.to_index + plan.to_business + plan.debt_pay
    cash_after += sell_proceeds + sale_net
    if buying:
        cash_after -= down
    rest_gain = contract_rest_gain(state.autonomy)
    energy_after = state.energy + WORK_ENERGY[employment]
    for slot in plan.slots:
        gain = SLOT_ENERGY[slot]
        # 合同月不能真正下班。回多少看这个月开始时的时间自主。
        if slot == "rest" and bound["contracted_pay"]:
            gain = rest_gain
        energy_after += gain
    next_condition = condition_after(state.condition, employment, plan.slots)
    autonomy_next = state.autonomy
    if taking_offer:
        autonomy_next = max(8, autonomy_next - JOB_OFFER_AUTONOMY)
    autonomy_next += WORK_AUTONOMY[employment]
    autonomy_next += 2 * sum(1 for slot in plan.slots if slot == "rest")
    if consume_slots:
        autonomy_next += CONSUME_AUTONOMY
    autonomy_next = clamp(autonomy_next, 8, 96)
    position = ease_of(state)
    return {
        "salary": pay,
        "bonus": bonus,
        "penalty": penalty,
        "leave": bound["leave"],
        "job_gap": taking_offer,
        "employment": employment,
        "ease_open": position["open"],
        "ease_projected": position["projected"],
        "operating": operating,
        "living": charged_living,
        "housing_living": charged_living,
        "down_payment": down if buying else 0,
        "mortgage_payment": home_pay if will_own and not selling_home else 0,
        "home_maintenance": maint,
        "home_sale_net": sale_net,
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
        "condition_next": next_condition,
        "autonomy_next": autonomy_next,
        "learn_slots": learn_slots,
        "consume_slots": consume_slots,
        "consume_autonomy": CONSUME_AUTONOMY if consume_slots else 0,
        "lifestyle_next": outlook["lifestyle_next"],
        "living_delta_rent": outlook["living_delta_rent"] if consume_slots else 0,
        "living_delta_own": outlook["living_delta_own"] if consume_slots else 0,
        "rent_delta": outlook["rent_delta"] if consume_slots else 0,
        "exiting": exiting,
        "contract_rest": rest_gain,
        "rust_step": rust_step(state.month, state.autonomy),
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
    elif plan.sign_months and state.condition < CONDITION_LOW:
        errors.append("状态太差，这个月签了也上不了全职")
    if plan.break_contract and state.contract_left <= 0:
        errors.append("没有合同可违约")
    if bound["leave"]:
        if plan.employment != "free":
            if state.energy < LOW_ENERGY_FULL:
                errors.append("这个月是病假，要自己安排时间")
            else:
                errors.append("状态太差，这个月停薪请假，要自己安排时间")
    elif bound["bound"] and plan.employment != "full":
        errors.append("合同没到期")
    elif plan.employment == "full" and state.energy < LOW_ENERGY_FULL:
        errors.append("精力不足，无法全职")
    elif plan.employment == "full" and state.condition < CONDITION_LOW:
        errors.append("状态太差，无法全职")
    if plan.employment == "light" and not bound["bound"] and not ease_of(state)["open"]:
        errors.append("还没攒到可以少工作的位置")
    if plan.employment == "light" and plan.sign_months:
        errors.append("轻职这个月不能再签全职合同")
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
        if state.locked > 0:
            errors.append("封闭的指数不能卖")
        else:
            errors.append("可卖的指数不够")
    if plan.lock_amount and plan.unlock:
        errors.append("同一个月不能又封闭又解锁")
    if plan.unlock and state.locked <= 0:
        errors.append("没有封闭仓可解锁")
    if plan.lock_amount and state.lock_left > 0:
        errors.append("封闭还没到期")
    if plan.lock_amount > max(0, liquid):
        errors.append("可卖的指数不够封闭")
    if plan.buy_home and plan.sell_home:
        errors.append("同一个月不能又买又卖房子")
    if plan.buy_home and state.home_value > 0:
        errors.append("已经有一套自住房")
    if plan.sell_home and state.home_value <= 0:
        errors.append("没有房子可卖")
    if plan.accept_job:
        if state.pending_offer <= 0:
            errors.append("这个月没有外部报价")
        elif bound["leave"] or bound["employment"] != "full":
            errors.append("这份报价要这个月上全职")
        elif state.contract_left > 0 and not plan.break_contract:
            errors.append("还在合同里，跳槽要先违约")
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
    if plan.buy_home and not errors:
        cushion = quoted["cash_after_choices"] - quoted["housing_living"] - quoted["mortgage_payment"] - quoted["home_maintenance"]
        if cushion < 0:
            errors.append("首付之后，这个月的月供和生活费不够")
    return errors


def preview(state: GameState, plan: Plan) -> dict:
    errors = validate(state, plan)
    if plan.employment not in WORK_SLOTS or any(slot not in LEGAL_SLOTS for slot in plan.slots):
        return {"ok": False, "errors": errors, "warnings": []}
    quoted = quote(state, plan)
    warnings: list[str] = []
    if quoted["energy_after"] < 0:
        warnings.append("精力会透支。连续三个月透支会过劳，本局失败。")
    due = quoted["living"] + quoted["mortgage_payment"] + quoted["home_maintenance"]
    if quoted["cash_after_choices"] - due < 0:
        warnings.append("生活费和月供可能让现金为负，并迫使你卖出资产或借债。")
    if state.regime == "bear":
        warnings.append("收缩期里，指数、店和身体可能在同一个月一起挨打。")
    if state.career_fresh <= 0 and "learn_career" not in plan.slots:
        warnings.append(f"职业技能已经过时，这个月不学还会再掉 {quoted['rust_step']} 点。")
    if bound_rest := quoted.get("contract_rest"):
        if commitment(state, plan)["contracted_pay"] and "rest" in plan.slots:
            warnings.append(f"合同月休息只回 {bound_rest} 点精力。")
    if quoted["job_gap"]:
        warnings.append("接手外部报价的这个月没有工资，月供和生活费照付。这份报价本身不加技能，学习仍然算。")
    if quoted["employment"] == "light":
        warnings.append("轻职工资低于全职，时间自主会上去。状态恢复了仍可以留在轻职。景气月继续全职往往更合适。")
    if quoted["employment"] == "full" and quoted["condition_next"] < CONDITION_LOW:
        warnings.append("下月状态低于 40，不能再全职。合同还在就会停薪请假。")
    if quoted["consume_slots"]:
        warnings.append(
            f"消费让时间自主 +{quoted['consume_autonomy']}，多花的钱不会再加。"
            f"下月租房生活费多 {quoted['living_delta_rent']}，已购房多 {quoted['living_delta_own']}。"
        )
    if plan.buy_home and not errors:
        warnings.append("买下之后可兑现会先掉一截，月供停不下来，房子也不能当月按市价拿回来。")
    if state.regime == "bear" and (plan.buy_home or state.home_value > 0):
        warnings.append("收缩期房价会往下走，月供却一分不少。")
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
    elif account == "home":
        state.home_value += amount
    elif account == "mortgage":
        state.mortgage += amount
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
    if plan.accept_job and s.pending_offer > 0 and quoted["job_gap"]:
        s.offer_pay = s.pending_offer
        s.offer_left = JOB_OFFER_MONTHS
        s.offer_gap = True
        s.pending_offer = 0
        s.autonomy = max(8, s.autonomy - JOB_OFFER_AUTONOMY)
        notes.append("接了外部报价，这个月交接，没有工资。这份报价不加技能")

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
        if state.energy < LOW_ENERGY_FULL:
            notes.append("合同月请了病假，没有工资")
        else:
            notes.append("状态太低，合同月停薪请假，没有工资")

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
    if plan.buy_home:
        _buy_home(s, ledger, notes)
    elif plan.sell_home and s.home_value > 0:
        _close_home(s, 100 - HOME_SELL_COST, "sell_home", ledger, notes)
        notes.append("卖掉自住房，扣掉交易成本并还清房贷")

    s.energy = quoted["energy_after"]
    s.condition = quoted["condition_next"]
    s.stress += WORK_STRESS[quoted["employment"]]
    s.autonomy += WORK_AUTONOMY[quoted["employment"]]
    for slot in plan.slots:
        s.stress += SLOT_STRESS[slot]
        if slot == "rest":
            s.autonomy += 2
        if slot.startswith("learn_"):
            attr = {"learn_career": "career", "learn_venture": "venture", "learn_invest": "invest"}[slot]
            current = getattr(s, attr)
            fresh_now = getattr(s, {"learn_career": "career_fresh", "learn_venture": "venture_fresh", "learn_invest": "invest_fresh"}[slot])
            # 快过时才来学，或技能已经够高，都只续新鲜。提前学才按递减公式涨。
            if fresh_now <= 3 or current >= 56:
                gain = 1
            else:
                gain = learn_gain(current)
            if start_autonomy < 28:
                gain = max(1, gain - 2)
            setattr(s, attr, min(100, current + gain))
    if "consume" in plan.slots:
        s.autonomy += CONSUME_AUTONOMY
    if plan.consume_cash:
        s.stress -= consume_stress_relief(plan.consume_cash)
        s.lifestyle += consume_lifestyle_gain(plan.consume_cash)
        s.network += consume_network_gain(plan.consume_cash)
    s.lifestyle = clamp(s.lifestyle, 100, 220)

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

    full_live = living_cost(s.lifestyle, s.price_index)
    live = full_live - rent_of(full_live) if s.home_value > 0 else full_live
    _move(s, "cash", -live, "living", ledger)
    if s.home_value > 0:
        _service_home(s, ledger, notes)
    if s.debt > 0:
        interest = s.debt * DEBT_RATE_NUM // DEBT_RATE_DEN
        _move(s, "cash", -interest, "interest", ledger)

    event = _apply_event(s, rng, quoted["employment"], quoted["salary"], gross, ledger, notes)
    shock = "none"
    if regime == "bear" and rng.random() < SHOCK_P:
        apply_contraction_bundle(s, event, ledger, notes)
        shock = "contraction"
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
    if s.home_value > 0:
        delta = s.home_value * HOME_DRIFT.get(regime, 0) // 1000
        if delta:
            _move(s, "home", delta, "home_drift", ledger)
    if plan.lock_amount and s.lock_left == 0 and s.locked == 0:
        s.locked = min(plan.lock_amount, s.portfolio)
        s.lock_left = LOCK_TERM
        notes.append(f"封闭 {s.locked} 元指数，{LOCK_TERM} 个月内不能卖")

    _apply_rust(s, plan, resolved_month, start_autonomy, notes)
    _roll_job_offer(s, quoted, rng, notes)

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
        "condition": s.condition,
        "stress": s.stress,
        "autonomy": s.autonomy,
        "salary": quoted["salary"],
        "living": live,
        "business_net": business_net,
        "invest_return": invest_return,
        "event": event,
        "shock": shock,
        "home_value": s.home_value,
        "mortgage": s.mortgage,
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


def _apply_rust(state: GameState, plan: Plan, month: int, autonomy: int, notes: list[str]) -> None:
    """上班不保养职业技能。新鲜耗尽之后才掉点，学习或对口行动才会续上。"""
    specs = (
        ("career", "career_fresh", "learn_career", None, "职业"),
        ("venture", "venture_fresh", "learn_venture", "venture", "经营"),
        ("invest", "invest_fresh", "learn_invest", "invest", "投资"),
    )
    for attr, fresh_attr, learn_slot, practice_slot, label in specs:
        learned = learn_slot in plan.slots
        practiced = learned or (practice_slot is not None and practice_slot in plan.slots)
        if attr == "career" and state.offer_gap:
            practiced = True
        fresh = getattr(state, fresh_attr)
        if learned:
            cap = FRESH_LEARN_LATE if month >= LATE_FRESH_MONTH else FRESH_LEARN_EARLY
            setattr(state, fresh_attr, cap)
            continue
        if practiced:
            setattr(state, fresh_attr, max(fresh, FRESH_PRACTICE))
            continue
        if fresh > 0:
            setattr(state, fresh_attr, fresh - 1)
            continue
        drop = min(getattr(state, attr), rust_step(month, autonomy))
        if drop:
            setattr(state, attr, getattr(state, attr) - drop)
            notes.append(f"{label}技能过时，掉了 {drop} 点")


def apply_contraction_bundle(state: GameState, already: str, ledger: list[dict], notes: list[str]) -> None:
    """收缩月把指数、店和身体打在一起。合同挡裁员，挡不住这里。"""
    notes.append("收缩期的冲击叠在一起")
    before = state.portfolio
    loss = before * SHOCK_INDEX_PCT // 100
    if loss:
        _move(state, "portfolio", -loss, "contraction_index", ledger)
        if state.locked > 0 and before > 0:
            state.locked = min(state.portfolio, state.locked * state.portfolio // before)
    if state.business_stage in ("trial", "running") and state.business_book > 0 and already != "setback":
        kept = state.business_book * (100 - SHOCK_BOOK_PCT) // 100
        haircut = state.business_book - kept
        if haircut:
            _move(state, "book", -haircut, "contraction_book", ledger)
    if state.stress > SHOCK_MEDICAL_STRESS and already != "medical":
        _move(state, "cash", -SHOCK_MEDICAL, "contraction_medical", ledger)
        notes.append(f"收缩月看病又花了 {SHOCK_MEDICAL} 元")


def _apply_event(state, rng, employment, salary_paid, gross, ledger, notes) -> str:
    options: list[tuple[str, float]] = []
    if state.stress > 55:
        options.append(("medical", 0.08))
    if employment in ("full", "light", "part") and state.contract_left <= 0:
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


def _roll_job_offer(state: GameState, quoted: dict, rng, notes: list[str]) -> None:
    if quoted["employment"] != "full" and state.offer_left > 0 and not state.offer_gap:
        state.offer_left = 0
        state.offer_pay = 0
        notes.append("没有继续全职，外部报价失效")
    if state.offer_gap:
        state.offer_gap = False
    elif state.offer_left > 0:
        state.offer_left -= 1
        if state.offer_left == 0:
            state.offer_pay = 0
            notes.append("外部报价到期，工资回到按技能算")
    employed = quoted["employment"] in ("full", "light", "part") and not quoted["leave"]
    if state.offer_left == 0 and employed and state.status == "playing":
        chance = JOB_OFFER_P_FRESH if state.career_fresh >= JOB_OFFER_FRESH else JOB_OFFER_P_STALE
        if rng.random() < chance:
            state.pending_offer = outside_offer(state.career, state.network, state.career_fresh)
            notes.append(f"有一份外部全职报价，月薪 {state.pending_offer} 元")
        else:
            state.pending_offer = 0
    else:
        state.pending_offer = 0


def _buy_home(state: GameState, ledger: list[dict], notes: list[str]) -> None:
    price = home_price(state.price_index)
    down, loan = down_and_loan(price)
    _move(state, "cash", -down, "home_down", ledger)
    _move(state, "home", price, "home_buy", ledger)
    _move(state, "mortgage", loan, "home_loan", ledger)
    state.mortgage_payment = mortgage_payment(loan)
    notes.append(f"买入自住房，首付 {down} 元，月供 {state.mortgage_payment} 元")


def _close_home(state: GameState, keep_pct: int, reason: str, ledger: list[dict], notes: list[str]) -> None:
    proceeds = home_proceeds(state.home_value, keep_pct)
    owed = state.mortgage
    value = state.home_value
    if value:
        _move(state, "home", -value, reason, ledger)
    if proceeds:
        _move(state, "cash", proceeds, reason, ledger)
    if owed:
        _move(state, "mortgage", -owed, reason, ledger)
        _move(state, "cash", -owed, reason, ledger)
    state.mortgage_payment = 0


def _service_home(state: GameState, ledger: list[dict], notes: list[str]) -> None:
    if state.mortgage > 0 and state.mortgage_payment > 0:
        interest = state.mortgage * MORTGAGE_RATE_NUM // MORTGAGE_RATE_DEN
        principal = min(state.mortgage, max(0, state.mortgage_payment - interest))
        due = principal + interest
        _move(state, "cash", -due, "mortgage", ledger)
        if principal:
            _move(state, "mortgage", -principal, "mortgage", ledger)
        if state.mortgage <= 0:
            state.mortgage_payment = 0
            notes.append("房贷还清了")
    maint = home_maintenance(state.home_value)
    if maint:
        _move(state, "cash", -maint, "home_maint", ledger)


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
    if state.cash < 0 and state.home_value > 0:
        _close_home(state, HOME_DISTRESS_KEEP, "distress_home", ledger, notes)
        notes.append("现金不够，房子被折价卖掉还贷")
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
