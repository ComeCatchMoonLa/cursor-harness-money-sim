const SLOT_OPTIONS = [
  ["learn_career", "学习·职业"],
  ["learn_venture", "学习·经营"],
  ["learn_invest", "学习·投资"],
  ["venture", "副业"],
  ["invest", "投资"],
  ["rest", "休息"],
  ["consume", "消费"],
];

const WORK_SLOTS = { full: 3, part: 2, free: 0 };
const STATUS_TEXT = {
  playing: "进行中",
  won: "胜利",
  bankrupt: "破产",
  burnout: "过劳失败",
  shortfall: "未达成",
};

let state = null;
let previewTimer = 0;

function skillText(value, fresh, rustStep) {
  if (Number(fresh) > 0) {
    return `${value} · 新鲜 ${fresh} 月`;
  }
  return `${value} · 过时，每月 -${rustStep}`;
}

function wan(value) {
  const number = Number(value) || 0;
  const sign = number < 0 ? "-" : "";
  return `${sign}${(Math.abs(number) / 10000).toFixed(2)} 万`;
}

async function api(path, body) {
  const response = await fetch(path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  const payload = await response.json();
  if (!response.ok && payload.error) {
    throw new Error(payload.error);
  }
  return payload;
}

function readPlan() {
  return {
    employment: document.querySelector("#employment").value,
    slots: [...document.querySelectorAll("[data-slot]")].map((node) => node.value),
    to_index: Number(document.querySelector("#to-index").value || 0),
    from_index: Number(document.querySelector("#from-index").value || 0),
    to_business: Number(document.querySelector("#to-business").value || 0),
    debt_pay: Number(document.querySelector("#debt-pay").value || 0),
    consume_cash: Number(document.querySelector("#consume").value || 0),
    risk_pct: Number(document.querySelector("#risk").value || 0),
    lock_amount: Number(document.querySelector("#lock-amount").value || 0),
    automate: document.querySelector("#automate").checked,
    exit_business: document.querySelector("#exit").checked,
    accept_offer: document.querySelector("#accept").checked,
    sign_months: Number(document.querySelector("#contract").value || 0),
    break_contract: document.querySelector("#break-contract").checked,
    unlock: document.querySelector("#unlock").checked,
    buy_home: document.querySelector("#buy-home").checked,
    sell_home: document.querySelector("#sell-home").checked,
  };
}

function setText(id, text) {
  document.querySelector(id).textContent = text;
}

function renderStatus() {
  ensureSlots();
  const shownMonth = state.month;
  setText("#month-label", `第 ${state.year} 年 ${state.month_of_year} 月 · 第 ${shownMonth}/108 月`);
  setText("#regime", state.regime_risk ? `景气：${state.regime_label} · ${state.regime_risk}` : `景气：${state.regime_label}`);
  setText("#net-worth", wan(state.realizable));
  setText("#book-worth", wan(state.net_worth));
  const history = state.history || [];
  if (history.length >= 2) {
    const delta = history[history.length - 1] - history[history.length - 2];
    const sign = delta > 0 ? "+" : "";
    setText("#net-delta", `上一月 ${sign}${wan(delta)}`);
  } else {
    setText("#net-delta", "开局 72.00 万");
  }
  const ratio = Math.max(0, Math.min(1, state.realizable / state.goal));
  document.querySelector("#goal-bar").style.width = `${(ratio * 100).toFixed(1)}%`;
  const banner = document.querySelector("#status-banner");
  banner.textContent = STATUS_TEXT[state.status] || state.status;
  banner.classList.toggle("bad", state.status === "bankrupt" || state.status === "burnout" || state.status === "shortfall");
  setText("#cash", wan(state.cash));
  setText("#portfolio", wan(state.portfolio));
  setText("#business", `${wan(state.business_book)} · ${state.stage_label}`);
  setText("#exit-value", wan(state.exit_value));
  setText("#debt", wan(state.debt));
  setText("#living", wan(state.living));
  setText("#housing", state.home_value
    ? `自住 ${wan(state.home_value)} · 贷款 ${wan(state.mortgage)} · 月供 ${wan(state.mortgage_payment)}`
    : `租房 · 房价 ${wan(state.home_price)} · 首付 ${wan(state.down_payment)}`);
  setText("#energy", `${state.energy}/100`);
  setText("#stress", `${state.stress}/100`);
  setText("#autonomy", `${state.autonomy}/100`);
  document.querySelector("#energy-bar").value = state.energy;
  document.querySelector("#stress-bar").value = state.stress;
  document.querySelector("#autonomy-bar").value = state.autonomy;
  setText("#career", skillText(state.career, state.career_fresh, state.rust_step));
  setText("#venture", skillText(state.venture, state.venture_fresh, state.rust_step));
  setText("#invest", skillText(state.invest, state.invest_fresh, state.rust_step));
  setText("#lifestyle", `${state.lifestyle}%`);
  const restNote = `合同月休息回 ${state.contract_rest}`;
  setText("#contract-label", state.contract_left ? `剩余 ${state.contract_left} 个月 · ${restNote}` : `没有合同 · ${restNote}`);
  setText("#lock-label", state.lock_left ? `${wan(state.locked)} · 剩余 ${state.lock_left} 个月` : "没有封闭");
  setText("#stage", state.burnout_streak ? `连续透支 ${state.burnout_streak} 个月` : "透支记满 3 个月会过劳失败");
  const full = document.querySelector('#employment option[value="full"]');
  const part = document.querySelector('#employment option[value="part"]');
  full.textContent = `全职 · 工资 ${wan(state.salary_full)} · 占 3 个时间槽`;
  part.textContent = `兼职 · 工资 ${wan(state.salary_part)} · 占 2 个时间槽`;
  const offer = document.querySelector("#offer");
  if (state.offer_exit_pct > 0) {
    offer.hidden = false;
    offer.textContent = `本月有人收购副业，按账面的 ${state.offer_exit_pct}%。可以接受，也可以留下。`;
  } else {
    offer.hidden = true;
    offer.textContent = "";
  }
  document.querySelector("#btn-resolve").disabled = state.status !== "playing";
  renderChart(history);
  renderLog();
}

function renderChart(history) {
  const svg = document.querySelector("#chart");
  const width = 280;
  const height = 100;
  const min = Math.min(...history, 0);
  const max = Math.max(...history, state.goal, 1);
  const span = max - min || 1;
  const points = history.map((value, index) => {
    const x = history.length === 1 ? 0 : (index / (history.length - 1)) * width;
    const y = height - ((value - min) / span) * (height - 8) - 4;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const goalY = height - ((state.goal - min) / span) * (height - 8) - 4;
  svg.replaceChildren();
  const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
  line.setAttribute("x1", "0");
  line.setAttribute("x2", String(width));
  line.setAttribute("y1", goalY.toFixed(1));
  line.setAttribute("y2", goalY.toFixed(1));
  line.setAttribute("stroke", "#c4a574");
  line.setAttribute("stroke-dasharray", "4 4");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "#0f6b4c");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("points", points);
  svg.append(line, path);
}

function renderLog() {
  const list = document.querySelector("#log");
  list.replaceChildren();
  const rows = state.recent || [];
  if (!rows.length) {
    const item = document.createElement("li");
    item.textContent = "还没有结算。";
    list.append(item);
    return;
  }
  rows.slice().reverse().forEach((row) => {
    const item = document.createElement("li");
    const notes = (row.notes || []).join("；");
    const shown = row.realizable == null ? row.net_worth : row.realizable;
    const shock = row.shock && row.shock !== "none" ? ` · ${row.shock}` : "";
    item.textContent = `第 ${row.month} 月 ${STATUS_TEXT[row.status] || row.status} · 可兑现 ${wan(shown)} · 工资 ${wan(row.salary)} · 生活费 ${wan(row.living)} · 副业 ${wan(row.business_net)} · 投资 ${wan(row.invest_return)} · ${row.event}${shock}${notes ? " · " + notes : ""}`;
    list.append(item);
  });
}

function ensureSlots() {
  const breaking = document.querySelector("#break-contract").checked;
  const bound = state && state.contract_left > 0 && !breaking;
  const leave = bound && state.energy < 14;
  const employment = document.querySelector("#employment");
  employment.disabled = Boolean(bound);
  document.querySelector("#contract").disabled = Boolean(state && state.contract_left > 0 && !breaking);
  if (leave) employment.value = "free";
  else if (bound) employment.value = "full";
  const mode = employment.value;
  const locked = WORK_SLOTS[mode];
  const work = document.querySelector("#work-slots");
  work.replaceChildren();
  for (let index = 0; index < locked; index += 1) {
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.textContent = "工作";
    work.append(chip);
  }
  const free = 4 - locked;
  const box = document.querySelector("#slots");
  if (box.dataset.free === String(free) && box.childElementCount === free) {
    return;
  }
  const previous = [...box.querySelectorAll("[data-slot]")].map((node) => node.value);
  box.replaceChildren();
  box.dataset.free = String(free);
  for (let index = 0; index < free; index += 1) {
    const label = document.createElement("label");
    label.textContent = `时间槽 ${index + 1}`;
    const select = document.createElement("select");
    select.dataset.slot = "1";
    if (index === 0) {
      select.dataset.testid = "slot-0";
      select.setAttribute("data-testid", "slot-0");
    }
    SLOT_OPTIONS.forEach(([value, text]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      select.append(option);
    });
    select.value = previous[index] || "rest";
    select.addEventListener("change", schedulePreview);
    label.append(select);
    box.append(label);
  }
}

function showPreview(payload) {
  const box = document.querySelector("#preview");
  if (!payload) {
    box.textContent = "调整方案后这里会显示预计代价。";
    return;
  }
  if (payload.errors && payload.errors.length) {
    box.textContent = payload.errors.join(" ");
    return;
  }
  const quote = payload.quote || {};
  const warnings = (payload.warnings || []).join(" ");
  const extra = [
    quote.bonus ? `签约奖金 ${wan(quote.bonus)}` : "",
    quote.penalty ? `违约金 ${wan(quote.penalty)}` : "",
    quote.leave ? "这个月停薪请假" : "",
    quote.down_payment ? `首付 ${wan(quote.down_payment)}` : "",
    quote.mortgage_payment ? `月供 ${wan(quote.mortgage_payment)}` : "",
    quote.home_maintenance ? `维修 ${wan(quote.home_maintenance)}` : "",
    quote.home_sale_net ? `卖房结算 ${wan(quote.home_sale_net)}` : "",
  ].filter(Boolean).join("，");
  box.textContent = `预计工资 ${wan(quote.salary)}，学费 ${wan(quote.tuition)}，建设 ${wan(quote.build_cost)}，生活费 ${wan(quote.living)}，行动后精力 ${quote.energy_after}。${extra ? extra + "。" : ""}${warnings}`;
}

function schedulePreview() {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(async () => {
    ensureSlots();
    if (!state || state.status !== "playing") {
      return;
    }
    try {
      showPreview(await api("/api/preview", readPlan()));
    } catch (error) {
      document.querySelector("#preview").textContent = error.message;
    }
  }, 120);
}

async function resolveMonth() {
  const button = document.querySelector("#btn-resolve");
  button.disabled = true;
  try {
    const result = await api("/api/resolve", readPlan());
    if (result.errors && result.errors.length) {
      showPreview({ errors: result.errors });
      return;
    }
    state = result.state;
    document.querySelector("#contract").value = "0";
    document.querySelector("#lock-amount").value = "0";
    document.querySelector("#break-contract").checked = false;
    document.querySelector("#unlock").checked = false;
    renderStatus();
    showPreview(null);
    schedulePreview();
  } catch (error) {
    document.querySelector("#preview").textContent = error.message;
  } finally {
    button.disabled = !state || state.status !== "playing";
  }
}

async function boot() {
  state = await api("/api/state");
  resetForm();
  renderStatus();
  schedulePreview();
}

function resetForm() {
  document.querySelector("#employment").value = "full";
  document.querySelector("#contract").value = "0";
  ["#to-index", "#from-index", "#to-business", "#debt-pay", "#risk", "#consume", "#lock-amount"].forEach((selector) => {
    document.querySelector(selector).value = "0";
  });
  ["#automate", "#exit", "#accept", "#break-contract", "#unlock", "#buy-home", "#sell-home"].forEach((selector) => {
    document.querySelector(selector).checked = false;
  });
  ensureSlots();
}

document.querySelector("#employment").addEventListener("change", () => {
  ensureSlots();
  schedulePreview();
});
["#to-index", "#from-index", "#to-business", "#debt-pay", "#risk", "#consume", "#lock-amount", "#contract", "#automate", "#exit", "#accept", "#break-contract", "#unlock", "#buy-home", "#sell-home"].forEach((selector) => {
  document.querySelector(selector).addEventListener("input", schedulePreview);
  document.querySelector(selector).addEventListener("change", schedulePreview);
});
document.querySelector("#btn-resolve").addEventListener("click", resolveMonth);
document.querySelector("#btn-new").addEventListener("click", async () => {
  state = await api("/api/new", {});
  resetForm();
  renderStatus();
  schedulePreview();
});
document.querySelector("#btn-save").addEventListener("click", async () => {
  state = (await api("/api/save", {})).state;
  document.querySelector("#preview").textContent = "已写入本机存档。";
});
document.querySelector("#btn-load").addEventListener("click", async () => {
  try {
    state = (await api("/api/load", {})).state;
    resetForm();
    renderStatus();
    schedulePreview();
  } catch (error) {
    document.querySelector("#preview").textContent = error.message;
  }
});

boot();
