"""对局状态。随机数状态放在局里，方便存档后继续同一条路径。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from money_sim.constants import (
    MONTHS,
    PRICE_START,
    START_AUTONOMY,
    START_CAREER,
    START_CASH,
    START_ENERGY,
    START_INVEST,
    START_LIFESTYLE,
    START_NETWORK,
    START_PORTFOLIO,
    START_STRESS,
    START_VENTURE,
    WIN_NET,
)


def net_worth(state: "GameState") -> int:
    return state.cash + state.portfolio + state.business_book - state.debt


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
    state.history = [net_worth(state)]
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
        history=[int(x) for x in data["history"]],
        last_report=data.get("last_report"),
    )
    return state


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
        "goal": WIN_NET,
        "start_net": START_CASH + START_PORTFOLIO,
        "history": list(state.history),
        "last_report": state.last_report,
        "seed": state.seed,
    }
