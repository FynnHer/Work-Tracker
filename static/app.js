"use strict";

const $ = (id) => document.getElementById(id);
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let status = null;        // last /api/status response
let fetchedAt = 0;        // performance.now() when status was fetched
let selectedDay = null;   // "YYYY-MM-DD" shown in the day panel
let editingId = null;     // session id being edited in the form

// ------------------------------------------------------------ helpers

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

const pad2 = (n) => String(n).padStart(2, "0");
const ymd = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const parseYmd = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const weekdayIdx = (d) => (d.getDay() + 6) % 7; // Monday = 0

function fmtDur(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${pad2(m)}m`;
}

function fmtClock(sec) {
  sec = Math.max(0, Math.floor(sec));
  return `${pad2(Math.floor(sec / 3600))}:${pad2(Math.floor((sec % 3600) / 60))}:${pad2(sec % 60)}`;
}

function fmtLongDate(d) {
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
}

const hhmm = (iso) => iso.slice(11, 16);

function level(sec) {
  if (sec <= 0) return 0;
  const h = sec / 3600;
  if (h < 2) return 1;
  if (h < 5) return 2;
  if (h < 8) return 3;
  return 4;
}

// ------------------------------------------------------------ status + timer

async function loadStatus() {
  status = await api("GET", "/api/status");
  fetchedAt = performance.now();
  renderStatus();
  renderWeek();
}

/** Seconds elapsed since the status was fetched (only counts while running). */
function liveExtra() {
  return status && status.running ? (performance.now() - fetchedAt) / 1000 : 0;
}

function renderStatus() {
  if (!status) return;
  const extra = liveExtra();
  const run = status.running;

  // Timer
  $("clock").textContent = fmtClock(run ? run.seconds + extra : 0);
  $("since").textContent = run
    ? `Running since ${hhmm(run.start_time)}${run.note ? " · " + run.note : ""}`
    : "Timer stopped";
  const btn = $("toggle");
  btn.textContent = run ? "Stop" : "Start";
  btn.className = "btn " + (run ? "stop" : "start");
  const noteEl = $("note");
  if (run && document.activeElement !== noteEl) noteEl.value = run.note;

  // Today
  const todaySec = status.today_seconds + extra;
  const todayTarget = status.daily_target;
  $("today-worked").textContent = fmtDur(todaySec);
  $("today-target").textContent = todayTarget ? fmtDur(todayTarget).replace(" 00m", "") : "0h";
  $("today-bar").style.width = todayTarget ? Math.min(100, (todaySec / todayTarget) * 100) + "%" : "0";
  const todayLeft = Math.max(0, todayTarget - todaySec);
  if (!todayTarget) {
    $("today-remaining").textContent = "Weekend — no target today";
  } else if (todayLeft <= 0) {
    $("today-remaining").textContent = `Done! ${fmtDur(todaySec - todayTarget)} overtime`;
  } else {
    let txt = `${fmtDur(todayLeft)} left`;
    if (run) {
      const end = new Date(Date.now() + todayLeft * 1000);
      txt += ` · finished at ${pad2(end.getHours())}:${pad2(end.getMinutes())}`;
    }
    $("today-remaining").textContent = txt;
  }

  // Week
  const weekSec = status.week_seconds + extra;
  $("week-worked").textContent = fmtDur(weekSec);
  $("week-bar").style.width = Math.min(100, (weekSec / status.weekly_target) * 100) + "%";
  const weekLeft = status.weekly_target - weekSec;
  $("week-remaining").textContent = weekLeft > 0
    ? `${fmtDur(weekLeft)} left this week`
    : `Done! ${fmtDur(-weekLeft)} overtime this week`;

  // Balance
  showBalance($("balance"), status.balance_seconds);
  showBalance($("balance-today"), status.balance_seconds + todaySec - todayTarget);
}

function showBalance(el, bal) {
  bal = Math.trunc(bal);
  el.textContent = (bal > 0 ? "+" : bal < 0 ? "−" : "±") + fmtDur(Math.abs(bal));
  el.className = "value " + (bal > 0 ? "positive" : bal < 0 ? "negative" : "");
}

function renderWeek() {
  const wrap = $("week");
  wrap.innerHTML = "";
  const maxSec = Math.max(10 * 3600, ...status.week_days.map((d) => d.seconds + (d.date === status.today ? liveExtra() : 0)));
  status.week_days.forEach((d, i) => {
    const sec = d.seconds + (d.date === status.today ? liveExtra() : 0);
    const col = document.createElement("div");
    col.className = "day-col" + (d.date === status.today ? " today" : "");
    col.innerHTML = `
      <div class="track">
        <div class="fill" style="height:${(sec / maxSec) * 100}%"></div>
        ${d.target ? `<div class="goal" style="bottom:${(d.target / maxSec) * 100}%"></div>` : ""}
      </div>
      <div class="name">${DAY_NAMES[i]}</div>
      <div class="hours">${fmtDur(sec)}</div>`;
    col.addEventListener("click", () => selectDay(d.date));
    wrap.appendChild(col);
  });
}

$("toggle").addEventListener("click", async () => {
  try {
    if (status && status.running) {
      await api("POST", "/api/stop", { note: $("note").value });
      $("note").value = "";
    } else {
      await api("POST", "/api/start", { note: $("note").value });
    }
    await refreshAll();
  } catch (e) {
    alert(e.message);
  }
});

// While running, the note field edits the running session's note (saved on Enter / blur).
async function saveRunningNote() {
  const run = status && status.running;
  if (!run || $("note").value.trim() === run.note) return;
  try {
    await api("PATCH", `/api/sessions/${run.id}`, { note: $("note").value });
    await loadStatus();
    if (selectedDay === status.today) await loadDay();
  } catch (e) {
    alert(e.message);
  }
}

$("note").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  if (status && status.running) $("note").blur();
  else $("toggle").click();
});
$("note").addEventListener("blur", saveRunningNote);

// ------------------------------------------------------------ heatmap

function heatmapRange() {
  const today = parseYmd(status.today);
  const v = $("year-select").value;
  if (v === "last") return { start: addDays(today, -364), end: today, label: "in the last year" };
  const y = Number(v);
  return { start: new Date(y, 0, 1), end: new Date(y, 11, 31), label: `in ${y}` };
}

function fillYearSelect() {
  const sel = $("year-select");
  const current = sel.value || "last";
  const thisYear = parseYmd(status.today).getFullYear();
  sel.innerHTML = `<option value="last">Last 12 months</option>`;
  for (let y = thisYear; y >= status.first_year; y--) {
    sel.insertAdjacentHTML("beforeend", `<option value="${y}">${y}</option>`);
  }
  sel.value = [...sel.options].some((o) => o.value === current) ? current : "last";
}

async function renderHeatmap() {
  const today = parseYmd(status.today);
  const { start, end, label } = heatmapRange();
  const fetchEnd = end > today ? today : end;
  const totals = await api("GET", `/api/days?from=${ymd(start)}&to=${ymd(fetchEnd)}`);

  const grid = $("heatmap");
  grid.innerHTML = "";

  // Weekday labels in column 1
  ["Mon", "", "Wed", "", "Fri", "", ""].forEach((name, i) => {
    const el = document.createElement("div");
    el.className = "weekday";
    el.style.gridRow = i + 2;
    el.textContent = name;
    grid.appendChild(el);
  });

  const gridStart = addDays(start, -weekdayIdx(start));
  const gridEnd = addDays(end, 6 - weekdayIdx(end));
  let total = 0, activeDays = 0, lastMonthCol = -10;

  for (let i = 0, d = gridStart; d <= gridEnd; i++, d = addDays(gridStart, i)) {
    const col = 2 + Math.floor(i / 7);
    const key = ymd(d);
    const inRange = d >= start && d <= end;
    const sec = totals[key] || 0;

    // Month label where a month begins (or at the very first column)
    if (inRange && (d.getDate() === 1 || d.getTime() === start.getTime()) && col - lastMonthCol >= 3) {
      const m = document.createElement("div");
      m.className = "month";
      m.style.gridColumn = `${col} / span 3`;
      m.textContent = MONTHS[d.getMonth()];
      grid.appendChild(m);
      lastMonthCol = col;
    }

    const cell = document.createElement("div");
    cell.style.gridColumn = col;
    cell.style.gridRow = weekdayIdx(d) + 2;
    if (!inRange) {
      cell.className = "cell pad";
    } else if (d > today) {
      cell.className = "cell future";
    } else {
      cell.className = `cell l${level(sec)}` + (key === selectedDay ? " selected" : "");
      cell.dataset.date = key;
      cell.dataset.sec = sec;
      total += sec;
      if (sec > 0) activeDays++;
    }
    grid.appendChild(cell);
  }

  $("heatmap-title").textContent = `${fmtDur(total)} worked ${label}`;
  $("heatmap-summary").textContent = `${activeDays} active day${activeDays === 1 ? "" : "s"}`;
}

const tooltip = $("tooltip");
$("heatmap").addEventListener("mouseover", (e) => {
  const c = e.target.closest(".cell[data-date]");
  if (!c) { tooltip.hidden = true; return; }
  const sec = Number(c.dataset.sec);
  tooltip.textContent = `${sec ? fmtDur(sec) : "No work"} on ${fmtLongDate(parseYmd(c.dataset.date))}`;
  const r = c.getBoundingClientRect();
  tooltip.style.left = r.left + r.width / 2 + "px";
  tooltip.style.top = r.top - 6 + "px";
  tooltip.hidden = false;
});
$("heatmap").addEventListener("mouseleave", () => (tooltip.hidden = true));
$("heatmap").addEventListener("click", (e) => {
  const c = e.target.closest(".cell[data-date]");
  if (c) selectDay(c.dataset.date);
});
$("year-select").addEventListener("change", renderHeatmap);

// ------------------------------------------------------------ day panel + manual entries

async function selectDay(day) {
  selectedDay = day;
  document.querySelectorAll(".heatmap .cell.selected").forEach((c) => c.classList.remove("selected"));
  const cell = document.querySelector(`.heatmap .cell[data-date="${day}"]`);
  if (cell) cell.classList.add("selected");
  resetForm();
  await loadDay();
}

async function loadDay() {
  const sessions = await api("GET", `/api/sessions?date=${selectedDay}`);
  const day = parseYmd(selectedDay);
  $("day-title").textContent = fmtLongDate(day);

  const list = $("day-sessions");
  list.innerHTML = "";
  if (!sessions.length) {
    list.innerHTML = `<li class="empty">No sessions on this day.</li>`;
    return;
  }
  for (const s of sessions) {
    const li = document.createElement("li");
    const sameDay = (iso) => iso && iso.slice(0, 10) === selectedDay;
    const startTxt = sameDay(s.start_time) ? hhmm(s.start_time) : s.start_time.slice(5, 16).replace("T", " ");
    const endTxt = s.running ? "now" : sameDay(s.end_time) ? hhmm(s.end_time) : s.end_time.slice(5, 16).replace("T", " ");
    li.innerHTML = `
      <span class="times">${startTxt} – ${endTxt}</span>
      <span class="dur">${fmtDur(s.seconds)}</span>
      <span class="note"></span>`;
    li.querySelector(".note").textContent = s.note;
    if (!s.running) {
      const edit = document.createElement("button");
      edit.className = "btn link";
      edit.textContent = "Edit";
      edit.onclick = () => startEdit(s);
      const del = document.createElement("button");
      del.className = "btn link";
      del.textContent = "Delete";
      del.onclick = async () => {
        if (!confirm("Delete this session?")) return;
        await api("DELETE", `/api/sessions/${s.id}`);
        await refreshAll();
      };
      li.append(edit, del);
    } else {
      li.insertAdjacentHTML("beforeend", `<span class="small positive">running</span>`);
    }
    list.appendChild(li);
  }
}

function resetForm() {
  editingId = null;
  $("f-start").value = `${selectedDay}T09:00`;
  $("f-end").value = `${selectedDay}T17:00`;
  $("f-note").value = "";
  $("f-submit").textContent = "Add entry";
  $("f-cancel").hidden = true;
  $("form-error").textContent = "";
}

function startEdit(s) {
  editingId = s.id;
  $("f-start").value = s.start_time.slice(0, 16);
  $("f-end").value = s.end_time.slice(0, 16);
  $("f-note").value = s.note;
  $("f-submit").textContent = "Save";
  $("f-cancel").hidden = false;
  $("form-error").textContent = "";
}

$("f-cancel").addEventListener("click", resetForm);

$("session-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { start_time: $("f-start").value, end_time: $("f-end").value, note: $("f-note").value };
  try {
    if (editingId) await api("PUT", `/api/sessions/${editingId}`, body);
    else await api("POST", "/api/sessions", body);
    resetForm();
    await refreshAll();
  } catch (err) {
    $("form-error").textContent = err.message;
  }
});

// ------------------------------------------------------------ boot

async function refreshAll() {
  await loadStatus();
  fillYearSelect();
  await Promise.all([renderHeatmap(), loadDay()]);
}

async function init() {
  status = await api("GET", "/api/status");
  selectedDay = status.today;
  $("today-label").textContent = fmtLongDate(parseYmd(status.today));
  resetForm();
  await refreshAll();

  // Tick the live numbers every second; resync with the server every minute.
  setInterval(() => {
    if (status && status.running) { renderStatus(); renderWeek(); }
  }, 1000);
  setInterval(async () => {
    const prevToday = status.today;
    await loadStatus();
    if (status.today !== prevToday) {
      $("today-label").textContent = fmtLongDate(parseYmd(status.today));
      await refreshAll();
    }
  }, 60000);
}

init().catch((e) => {
  document.querySelector("main").insertAdjacentHTML(
    "afterbegin",
    `<div class="card error">Could not reach the server: ${e.message}</div>`
  );
});
