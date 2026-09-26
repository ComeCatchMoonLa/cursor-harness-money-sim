"""对局时对上已经留下的路线。不替玩家选下一步，也不往已结算的月份后面走。"""

from __future__ import annotations

from money_sim.engine import resolve
from money_sim.routes import EMPLOY_TEXT, starting_policies
from money_sim.state import new_game

# 一句话：赌什么、怕什么、在哪个月转弯。两句相同就当成同一条。
STAKES = {
    "steady": "赌工资一直在，怕停薪之后储蓄够不到 150 万，不因为少工作的位置开了就转弯。",
    "grind": "赌不保养也能把工资留住，怕状态掉下去被迫停薪，不因为累了就改去休息。",
    "yolo": "赌店本身能长到 150 万，怕没有工资之后现金先断，开局就离开全职。",
    "owner": "赌店做起来之后工资还垫着，怕店一亏就把工资也停了，按店的阶段在全职和兼职之间换。",
    "coast": "赌轻职储蓄盖住 150 万就可以不拿工资，怕景气、合同和账单把你拉回全职，转弯在盖住的那个月。",
}


def collapse_routes(routes: list[dict]) -> list[dict]:
    seen: set[str] = set()
    kept = []
    for route in routes:
        stake = route.get("stake") or ""
        if stake in seen:
            continue
        seen.add(stake)
        kept.append(route)
    return kept


def replay_employment(policy, seed: int, months: int) -> list[str]:
    state = new_game(seed)
    played = []
    for _ in range(max(0, months)):
        if state.status != "playing":
            break
        state, errors, report = resolve(state, policy(state))
        if errors or report is None:
            break
        played.append(report["employment"])
    return played


def closer_name(player: list[str], paths: dict[str, list[str]]) -> str | None:
    """已结算月份里，就业相同次数最多的那一条。打平就不挑。"""
    if not player or not paths:
        return None
    scores = {}
    for name, employment in paths.items():
        scores[name] = sum(left == right for left, right in zip(player, employment))
    best = max(scores.values())
    names = [name for name, score in scores.items() if score == best]
    if len(names) != 1:
        return None
    return names[0]


def match_report(seed: int, player: list[str], left: str, right: str) -> dict:
    policies = dict(starting_policies())
    if left not in policies or right not in policies or left == right:
        raise ValueError("要两条不同的已留下路线")
    months = len(player)
    paths = {name: replay_employment(policy, seed, months) for name, policy in policies.items()}
    closer = closer_name(player, paths)
    titles = {name: stake_title(name) for name in policies}
    rows = []
    for index in range(months):
        rows.append(
            {
                "month": index + 1,
                "player": player[index],
                "left": paths[left][index] if index < len(paths[left]) else None,
                "right": paths[right][index] if index < len(paths[right]) else None,
            }
        )
    return {
        "closer": closer,
        "closer_title": titles.get(closer) if closer else None,
        "left": left,
        "right": right,
        "months": rows,
        "labels": EMPLOY_TEXT,
    }


def stake_title(name: str) -> str:
    titles = {
        "steady": "一直上班",
        "grind": "只上班不保养",
        "yolo": "辞职压进店",
        "owner": "把店做起来",
        "coast": "盖住之后停薪",
    }
    return titles.get(name, name)
