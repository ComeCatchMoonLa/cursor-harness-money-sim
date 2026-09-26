"""V1 经济常数。改动规则或这些数之后，要重跑批量模拟。"""

MONTHS = 108
START_CASH = 180_000
START_PORTFOLIO = 540_000
WIN_NET = 1_500_000

BASE_LIVING = 13_200
PRICE_START = 1_000
PRICE_GROWTH_NUM = 10_025
PRICE_GROWTH_DEN = 10_000

START_ENERGY = 76
START_STRESS = 22
START_AUTONOMY = 42
START_CAREER = 24
START_VENTURE = 6
START_INVEST = 10
START_LIFESTYLE = 100
START_NETWORK = 4

SALARY_BASE = 11_500
SALARY_PER_SKILL = 210
PART_TIME_NUM = 74
PART_TIME_DEN = 100
NETWORK_SALARY_DEN = 500

WORK_ENERGY = {"full": -22, "part": -12, "free": 0}
WORK_STRESS = {"full": 7, "part": 4, "free": -2}
WORK_AUTONOMY = {"full": -3, "part": 1, "free": 4}
WORK_SLOTS = {"full": 3, "part": 2, "free": 0}
LOW_ENERGY_FULL = 14
TOTAL_SLOTS = 4

SLOT_ENERGY = {
    "learn_career": -13,
    "learn_venture": -13,
    "learn_invest": -11,
    "venture": -15,
    "invest": -9,
    "rest": 26,
    "consume": 4,
}
SLOT_STRESS = {
    "learn_career": 3,
    "learn_venture": 3,
    "learn_invest": 2,
    "venture": 5,
    "invest": 2,
    "rest": -14,
    "consume": 0,
}
LEGAL_SLOTS = frozenset(SLOT_ENERGY)
REGEN = 7
STRESS_BLOCK_REGEN = 80

TUITION = 1_000
BUILD_COST = 7_000
BUILDS_TO_LAUNCH = 3
MIN_CONSUME = 2_000

DEBT_CAP = 160_000
DEBT_RATE_NUM = 12
DEBT_RATE_DEN = 1_000

INDEX_SELL_FEE_NUM = 3
INDEX_SELL_FEE_DEN = 1_000
EMERGENCY_FEE_NUM = 2
EMERGENCY_FEE_DEN = 100
DISTRESS_EXIT_NUM = 30
DISTRESS_EXIT_DEN = 100

BURNOUT_LIMIT = 3
REGIME_SWITCH_P = 0.18
OFFER_P = 0.10

REGIME_LABEL = {"bull": "景气", "chop": "平淡", "bear": "收缩"}

LOG_FIELDS = (
    "type",
    "month",
    "status",
    "cash",
    "portfolio",
    "business_book",
    "debt",
    "net_worth",
    "energy",
    "salary",
    "living",
    "business_net",
    "invest_return",
    "event",
    "fail_reason",
)
