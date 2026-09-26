"""对局状态。随机数状态放在局里，方便存档后继续同一条路径。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from money_sim.constants import (
    MONTHS,
    PRICE_START,
    START_AUTONOMY,
    START_CAREER,
    START_CAREER_FRESH,
    START_CASH,
    START_ENERGY,
    START_INVEST,
    START_INVEST_FRESH,
    START_LIFESTYLE,
    START_NETWORK,
    START_PORTFOLIO,
    START_STRESS,
    START_VENTURE,
    START_VENTURE_FRESH,
    WIN_NET,
)


def net_worth(state: "GameState") -> int:
    """账面。副业按投入的本金计，房子按市价计，用来和分录对账。"""
    return state.cash + state.portfolio + state.business_book + state.home_value - state.mortgage - state.debt


def realizable_net(state: "GameState") -> int:
    """可兑现。店和房子都按现在主动退出能拿到的折扣计，封闭的指数仍算你的。"""
    from money_sim.economy import exit_pct, home_equity

    book = 0
    if state.business_stage != "none" and state.business_book > 0:
        pct = exit_pct(state.business_stage, state.last_business_net, 0, False)
        book = state.business_book * pct // 100
    return state.cash + state.portfolio + book + home_equity(state.home_value, state.mortgage) - state.debt


@dataclass
class GameState:
    month: int = 1
    status: str = "playing"
    seed: int = 1
    rng_version: int = 3
    rng_state: list[int] = field(default_factory=list)
    rng_gauss: float | None = None
    cash: int = START_CASH
    portfolio: int = START_PORTFOLIO
    business_book: int = 0
    business_stage: str = "none"
    business_progress: int = 0
    automated: bool = False
    debt: int = 0
    energy: int = START_ENERGY
    stress: int = START_STRESS
    autonomy: int = START_AUTONOMY
    career: int = START_CAREER
    venture: int = START_VENTURE
    invest: int = START_INVEST
    lifestyle: int = START_LIFESTYLE
    network: int = START_NETWORK
    price_index: int = PRICE_START
    regime: str = "chop"
    burnout_streak: int = 0
    offer_exit_pct: int = 0
    last_business_net: int = 0
    contract_left: int = 0
    contract_term: int = 0
    locked: int = 0
    lock_left: int = 0
    trial_months: int = 0
    career_fresh: int = START_CAREER_FRESH
    venture_fresh: int = START_VENTURE_FRESH
    invest_fresh: int = START_INVEST_FRESH
    home_value: int = 0
    mortgage: int = 0
    mortgage_payment: int = 0
    pending_offer: int = 0
    offer_pay: int = 0
    offer_left: int = 0
    offer_gap: bool = False
    history: list[int] = field(default_factory=list)
    last_report: dict | None = None

    def clone(self) -> "GameState":
        return GameState(
            month=self.month,
            status=self.status,
            seed=self.seed,
            rng_version=self.rng_version,
            rng_state=list(self.rng_state),
            rng_gauss=self.rng_gauss,
            cash=self.cash,
            portfolio=self.portfolio,
            business_book=self.business_book,
            business_stage=self.business_stage,
            business_progress=self.business_progress,
            automated=self.automated,
            debt=self.debt,
            energy=self.energy,
            stress=self.stress,
            autonomy=self.autonomy,
            career=self.career,
            venture=self.venture,
            invest=self.invest,
            lifestyle=self.lifestyle,
            network=self.network,
            price_index=self.price_index,
            regime=self.regime,
            burnout_streak=self.burnout_streak,
            offer_exit_pct=self.offer_exit_pct,
            last_business_net=self.last_business_net,
            contract_left=self.contract_left,
            contract_term=self.contract_term,
            locked=self.locked,
            lock_left=self.lock_left,
            trial_months=self.trial_months,
            career_fresh=self.career_fresh,
            venture_fresh=self.venture_fresh,
            invest_fresh=self.invest_fresh,
            home_value=self.home_value,
            mortgage=self.mortgage,
            mortgage_payment=self.mortgage_payment,
            pending_offer=self.pending_offer,
            offer_pay=self.offer_pay,
            offer_left=self.offer_left,
            offer_gap=self.offer_gap,
            history=list(self.history),
            last_report=self.last_report,
        )


@dataclass
class Plan:
    employment: str
    slots: list[str]
    to_index: int = 0
    from_index: int = 0
    to_business: int = 0
    debt_pay: int = 0
    consume_cash: int = 0
    risk_pct: int = 0
    automate: bool = False
    exit_business: bool = False
    accept_offer: bool = False
    sign_months: int = 0
    break_contract: bool = False
    lock_amount: int = 0
    unlock: bool = False
    buy_home: bool = False
    sell_home: bool = False
    accept_job: bool = False


def rng_of(state: GameState) -> random.Random:
    rng = random.Random()
    rng.setstate((state.rng_version, tuple(state.rng_state), state.rng_gauss))
    return rng


def store_rng(state: GameState, rng: random.Random) -> None:
    version, seq, gauss = rng.getstate()
    state.rng_version = version
    state.rng_state = list(seq)
    state.rng_gauss = gauss


def new_game(seed: int | None = None) -> GameState:
    if seed is None:
        seed = random.SystemRandom().randrange(1, 1_000_000_000)
    rng = random.Random(seed)
    version, seq, gauss = rng.getstate()
    state = GameState(
        seed=seed,
        rng_version=version,
        rng_state=list(seq),
        rng_gauss=gauss,
    )
    state.history = [realizable_net(state)]
    return state


def to_save_dict(state: GameState) -> dict:
    data = {
        "save_version": 1,
        "month": state.month,
        "status": state.status,
        "seed": state.seed,
        "rng_version": state.rng_version,
        "rng_state": list(state.rng_state),
        "rng_gauss": state.rng_gauss,
        "cash": state.cash,
        "portfolio": state.portfolio,
        "business_book": state.business_book,
        "business_stage": state.business_stage,
        "business_progress": state.business_progress,
        "automated": state.automated,
        "debt": state.debt,
        "energy": state.energy,
        "stress": state.stress,
        "autonomy": state.autonomy,
        "career": state.career,
        "venture": state.venture,
        "invest": state.invest,
        "lifestyle": state.lifestyle,
        "network": state.network,
        "price_index": state.price_index,
        "regime": state.regime,
        "burnout_streak": state.burnout_streak,
        "offer_exit_pct": state.offer_exit_pct,
        "last_business_net": state.last_business_net,
        "contract_left": state.contract_left,
        "contract_term": state.contract_term,
        "locked": state.locked,
        "lock_left": state.lock_left,
        "trial_months": state.trial_months,
        "career_fresh": state.career_fresh,
        "venture_fresh": state.venture_fresh,
        "invest_fresh": state.invest_fresh,
        "home_value": state.home_value,
        "mortgage": state.mortgage,
        "mortgage_payment": state.mortgage_payment,
        "pending_offer": state.pending_offer,
        "offer_pay": state.offer_pay,
        "offer_left": state.offer_left,
        "offer_gap": state.offer_gap,
        "history": list(state.history),
        "last_report": state.last_report,
    }
    return data


def from_save_dict(data: dict) -> GameState:
    state = GameState(
        month=int(data["month"]),
        status=str(data["status"]),
        seed=int(data["seed"]),
        rng_version=int(data["rng_version"]),
        rng_state=[int(x) for x in data["rng_state"]],
        rng_gauss=None if data.get("rng_gauss") is None else float(data["rng_gauss"]),
        cash=int(data["cash"]),
        portfolio=int(data["portfolio"]),
        business_book=int(data["business_book"]),
        business_stage=str(data["business_stage"]),
        business_progress=int(data["business_progress"]),
        automated=bool(data["automated"]),
        debt=int(data["debt"]),
        energy=int(data["energy"]),
        stress=int(data["stress"]),
        autonomy=int(data["autonomy"]),
        career=int(data["career"]),
        venture=int(data["venture"]),
        invest=int(data["invest"]),
        lifestyle=int(data["lifestyle"]),
        network=int(data["network"]),
        price_index=int(data["price_index"]),
        regime=str(data["regime"]),
        burnout_streak=int(data["burnout_streak"]),
        offer_exit_pct=int(data["offer_exit_pct"]),
        last_business_net=int(data["last_business_net"]),
        contract_left=int(data.get("contract_left", 0)),
        contract_term=int(data.get("contract_term", 0)),
        locked=int(data.get("locked", 0)),
        lock_left=int(data.get("lock_left", 0)),
        trial_months=int(data.get("trial_months", 0)),
        career_fresh=int(data.get("career_fresh", START_CAREER_FRESH)),
        venture_fresh=int(data.get("venture_fresh", START_VENTURE_FRESH)),
        invest_fresh=int(data.get("invest_fresh", START_INVEST_FRESH)),
        home_value=int(data.get("home_value", 0)),
        mortgage=int(data.get("mortgage", 0)),
        mortgage_payment=int(data.get("mortgage_payment", 0)),
        pending_offer=int(data.get("pending_offer", 0)),
        offer_pay=int(data.get("offer_pay", 0)),
        offer_left=int(data.get("offer_left", 0)),
        offer_gap=bool(data.get("offer_gap", False)),
        history=[int(x) for x in data["history"]],
        last_report=data.get("last_report"),
    )
    return state


def _housing_view(state: GameState) -> dict:
    from money_sim.economy import down_and_loan, home_price, mortgage_payment

    price = home_price(state.price_index)
    down, loan = down_and_loan(price)
    return {
        "home_value": state.home_value,
        "mortgage": state.mortgage,
        "mortgage_payment": state.mortgage_payment,
        "home_price": price,
        "down_payment": down,
        "next_payment": state.mortgage_payment if state.home_value else mortgage_payment(loan),
        "pending_offer": state.pending_offer,
        "offer_pay": state.offer_pay,
        "offer_left": state.offer_left,
    }


def _rust_step(state: GameState) -> int:
    from money_sim.economy import rust_step

    return rust_step(state.month, state.autonomy)


def _contract_rest(state: GameState) -> int:
    from money_sim.economy import contract_rest_gain

    return contract_rest_gain(state.autonomy)


def display_month(state: GameState) -> int:
    if state.status == "playing":
        return state.month
    return max(1, min(MONTHS, state.month - 1))


def public_view(state: GameState) -> dict:
    shown = display_month(state)
    return {
        "month": shown,
        "month_index": state.month,
        "months": MONTHS,
        "year": (shown - 1) // 12 + 1,
        "month_of_year": (shown - 1) % 12 + 1,
        "status": state.status,
        "cash": state.cash,
        "portfolio": state.portfolio,
        "business_book": state.business_book,
        "business_stage": state.business_stage,
        "business_progress": state.business_progress,
        "automated": state.automated,
        "debt": state.debt,
        "energy": state.energy,
        "stress": state.stress,
        "autonomy": state.autonomy,
        "career": state.career,
        "venture": state.venture,
        "invest": state.invest,
        "lifestyle": state.lifestyle,
        "network": state.network,
        "price_index": state.price_index,
        "regime": state.regime,
        "burnout_streak": state.burnout_streak,
        "offer_exit_pct": state.offer_exit_pct,
        "last_business_net": state.last_business_net,
        "net_worth": net_worth(state),
        "realizable": realizable_net(state),
        "contract_left": state.contract_left,
        "contract_term": state.contract_term,
        "locked": state.locked,
        "lock_left": state.lock_left,
        "trial_months": state.trial_months,
        "career_fresh": state.career_fresh,
        "venture_fresh": state.venture_fresh,
        "invest_fresh": state.invest_fresh,
        "rust_step": _rust_step(state),
        "contract_rest": _contract_rest(state),
        "regime_risk": "指数、店和身体可能在同一个月一起挨打" if state.regime == "bear" else "",
        **_housing_view(state),
        "goal": WIN_NET,
        "start_net": START_CASH + START_PORTFOLIO,
        "history": list(state.history),
        "last_report": state.last_report,
        "seed": state.seed,
    }
