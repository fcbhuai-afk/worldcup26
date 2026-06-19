const data = window.WC26_DATA;
const state = {
  stage: "all",
  group: "all",
  status: "all",
  query: "",
  didInitialJump: false,
};

const stageNames = {
  "group-stage": "小组赛",
  "round-of-32": "32强",
  "round-of-16": "16强",
  "quarter-finals": "四分之一决赛",
  "semi-finals": "半决赛",
  "third-place": "三四名决赛",
  final: "决赛",
};

const venueInfo = {
  "mexico-city": { tz: "America/Mexico_City", label: "墨西哥城", elevation: "约 2240m" },
  guadalajara: { tz: "America/Mexico_City", label: "瓜达拉哈拉", elevation: "约 1560m" },
  monterrey: { tz: "America/Monterrey", label: "蒙特雷", elevation: "约 540m" },
  toronto: { tz: "America/Toronto", label: "多伦多", elevation: "约 76m" },
  vancouver: { tz: "America/Vancouver", label: "温哥华", elevation: "约 70m" },
  "los-angeles": { tz: "America/Los_Angeles", label: "洛杉矶", elevation: "约 30m" },
  "san-francisco": { tz: "America/Los_Angeles", label: "旧金山湾区", elevation: "约 2m" },
  seattle: { tz: "America/Los_Angeles", label: "西雅图", elevation: "约 52m" },
  houston: { tz: "America/Chicago", label: "休斯敦", elevation: "约 13m" },
  dallas: { tz: "America/Chicago", label: "达拉斯/阿灵顿", elevation: "约 184m" },
  atlanta: { tz: "America/New_York", label: "亚特兰大", elevation: "约 320m" },
  miami: { tz: "America/New_York", label: "迈阿密", elevation: "约 2m" },
  "kansas-city": { tz: "America/Chicago", label: "堪萨斯城", elevation: "约 270m" },
  boston: { tz: "America/New_York", label: "波士顿/福克斯堡", elevation: "约 88m" },
  "new-york": { tz: "America/New_York", label: "纽约/新泽西", elevation: "约 7m" },
  philadelphia: { tz: "America/New_York", label: "费城", elevation: "约 12m" },
};

const influenceModels = [
  {
    title: "世界杯小组赛影响因素占比",
    subtitle: "硬实力上调版",
    items: [
      { name: "球队硬实力", detail: "球员能力 / 身价 / 核心球员", value: 35, color: "#287db7" },
      { name: "战术体系", detail: "教练布置 / 阵型匹配", value: 17, color: "#ff7f0e" },
      { name: "阵容深度与轮换", detail: "体能 / 替补 / 连续赛程", value: 13, color: "#2ca02c" },
      { name: "稳定性与执行力", detail: "默契 / 失误率", value: 12, color: "#d62728" },
      { name: "临场状态与心理", detail: "首战压力 / 出线压力", value: 8, color: "#9467bd" },
      { name: "环境与赛程", detail: "气温 / 湿度 / 当地下午 / 旅行", value: 10, color: "#8c564b" },
      { name: "裁判与运气", detail: "VAR / 门柱 / 折射", value: 5, color: "#da70bf" },
    ],
    note: "小组赛仍以硬实力为底盘，但美国/墨西哥/加拿大的午后高温会更明显影响节奏、体能和爆冷空间。",
  },
  {
    title: "世界杯淘汰赛影响因素占比",
    subtitle: "硬实力上调版",
    items: [
      { name: "球队硬实力", detail: "球星质量 / 关键位置", value: 30, color: "#287db7" },
      { name: "战术针对性", detail: "克制关系 / 换人博弈", value: 20, color: "#ff7f0e" },
      { name: "临场状态与心理", detail: "抗压 / 点球 / 落后应对", value: 16, color: "#2ca02c" },
      { name: "防守稳定与失误控制", detail: "零失误 / 门将发挥", value: 13, color: "#d62728" },
      { name: "体能与伤病", detail: "加时 / 连续高强度", value: 9, color: "#9467bd" },
      { name: "定位球与细节", detail: "角球 / 任意球 / 边路传中", value: 6, color: "#8c564b" },
      { name: "裁判与偶然性", detail: "红牌 / VAR / 折射 / 门柱", value: 6, color: "#da70bf" },
    ],
    note: "淘汰赛单场淘汰，战术针对性、临场状态和失误控制的权重会上升。",
  },
];

function el(id) {
  return document.getElementById(id);
}

function fmtDate(iso) {
  const date = new Date(iso);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function fmtLocalDate(iso, hostCity) {
  const info = venueInfo[hostCity];
  if (!info) return "";
  const date = new Date(iso);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: info.tz,
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function cleanCity(city) {
  return venueInfo[city]?.label || (city || "").replaceAll("-", " ");
}

function scoreFor(match) {
  if (match.completed === "True") return `${match.home_score}-${match.away_score}`;
  return "VS";
}

function statusText(match) {
  if (match.completed === "True") return "完赛";
  return match.status_state === "in" ? "进行中" : "未赛";
}

function sourceScore(match) {
  const local = match.completed === "True" ? `${match.home_score}-${match.away_score}` : "未赛";
  const zhibo8 = match.zhibo8?.score && match.zhibo8.score !== "-" ? match.zhibo8.score : "未赛";
  return { local, zhibo8 };
}

function leanPercent(score) {
  const value = Number(score || 0);
  return 50 + value / 2;
}

function signedScore(score) {
  const value = Number(score || 0);
  return value > 0 ? `+${value}` : `${value}`;
}

function parseFactors(match) {
  try {
    return JSON.parse(match.analysis?.factor_breakdown || "[]");
  } catch {
    return [];
  }
}

function parsePreMatchSources(match) {
  try {
    return JSON.parse(match.analysis?.pre_match_sources || "[]");
  } catch {
    return [];
  }
}

function teamUrl(match, side) {
  const zhibo8 = match.zhibo8 || {};
  const team = side === "home" ? zhibo8.home_team_zh : zhibo8.away_team_zh;
  const id = side === "home" ? zhibo8.home_team_id : zhibo8.away_team_id;
  if (!team || !id) return "";
  return `https://data.zhibo8.cc/html/mobile/team.html?pullrefresh=0&match=%E4%B8%96%E7%95%8C%E6%9D%AF&hidenav=true&backbtn=true&team=${encodeURIComponent(team)}&teamid=${encodeURIComponent(id)}`;
}

function renderTeamName(match, side) {
  const en = side === "home" ? match.home_team : match.away_team;
  const zh = side === "home" ? match.crosscheck?.home_team_zh_expected : match.crosscheck?.away_team_zh_expected;
  const url = teamUrl(match, side);
  const label = `${en}${zh ? ` / ${zh}` : ""}`;
  if (!url) return `<span>${label}</span>`;
  return `<a class="team-link" href="${url}" target="_blank" rel="noreferrer" title="打开直播吧球队资料">${label}</a>`;
}

function fillSelect(select, options) {
  select.innerHTML = options
    .map((option) => `<option value="${option.value}">${option.label}</option>`)
    .join("");
}

function initMeta() {
  el("matchCount").textContent = data.meta.match_count;
  el("teamCount").textContent = data.meta.team_count;
  el("venueCount").textContent = data.meta.venue_count;
  el("crosscheckCount").textContent = data.meta.crosscheck_ok;
}

function initFilters() {
  const stages = [...new Set(data.matches.map((m) => m.stage))];
  fillSelect(el("stageFilter"), [
    { value: "all", label: "全部阶段" },
    ...stages.map((stage) => ({ value: stage, label: stageNames[stage] || stage })),
  ]);

  fillSelect(el("groupFilter"), [
    { value: "all", label: "全部小组" },
    ..."ABCDEFGHIJKL".split("").map((group) => ({ value: group, label: `${group} 组` })),
  ]);

  fillSelect(el("statusFilter"), [
    { value: "all", label: "全部状态" },
    { value: "post", label: "已完赛" },
    { value: "pre", label: "未开赛" },
    { value: "in", label: "进行中" },
  ]);

  el("stageFilter").addEventListener("change", (event) => {
    state.stage = event.target.value;
    renderMatches();
  });
  el("groupFilter").addEventListener("change", (event) => {
    state.group = event.target.value;
    renderMatches();
  });
  el("statusFilter").addEventListener("change", (event) => {
    state.status = event.target.value;
    renderMatches();
  });
  el("searchInput").addEventListener("input", (event) => {
    state.query = event.target.value.trim().toLowerCase();
    renderMatches();
  });
  el("resetFilters").addEventListener("click", () => {
    state.stage = "all";
    state.group = "all";
    state.status = "all";
    state.query = "";
    el("stageFilter").value = "all";
    el("groupFilter").value = "all";
    el("statusFilter").value = "all";
    el("searchInput").value = "";
    renderMatches();
  });
}

function initBracketOverlay() {
  el("topBracketLink").addEventListener("click", (event) => {
    event.preventDefault();
    el("knockoutRound32").scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(openBracketFull, 250);
  });
  el("openBracketFull").addEventListener("click", openBracketFull);
  el("closeBracketFull").addEventListener("click", closeBracketFull);
  el("bracketOverlay").addEventListener("click", (event) => {
    if (event.target.id === "bracketOverlay") closeBracketFull();
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeBracketFull();
  });
}

function matchPassesFilters(match) {
  if (state.stage !== "all" && match.stage !== state.stage) return false;
  if (state.group !== "all" && match.group !== state.group) return false;
  if (state.status !== "all" && match.status_state !== state.status) return false;
  if (!state.query) return true;
  const haystack = [
    match.home_team,
    match.away_team,
    match.crosscheck?.home_team_zh_expected,
    match.crosscheck?.away_team_zh_expected,
    match.stadium,
    match.host_city,
    match.stage_cn,
    match.group,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(state.query);
}

function renderMatches() {
  const matches = data.matches
    .filter(matchPassesFilters)
    .slice()
    .sort((a, b) => new Date(a.kickoff_beijing) - new Date(b.kickoff_beijing));
  el("resultHint").textContent = `当前显示 ${matches.length} 场。`;

  if (!matches.length) {
    el("matches").innerHTML = `<div class="empty-state">没有符合条件的比赛。</div>`;
    return;
  }

  el("matches").innerHTML = matches.map(renderMatchCard).join("");
  jumpToCurrentMatch(matches);
}

function findCurrentMatch(matches) {
  const live = matches.find((match) => match.status_state === "in");
  if (live) return live;

  const now = new Date();
  const upcoming = matches.find((match) => new Date(match.kickoff_beijing) >= now);
  if (upcoming) return upcoming;

  return matches[matches.length - 1];
}

function jumpToCurrentMatch(matches) {
  if (state.didInitialJump || state.stage !== "all" || state.group !== "all" || state.status !== "all" || state.query) {
    return;
  }
  state.didInitialJump = true;
  const current = findCurrentMatch(matches);
  if (!current) return;
  const target = document.getElementById(`match-${current.match_number}`);
  if (!target) return;
  target.classList.add("focus-match");
  window.setTimeout(() => {
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 250);
}

function renderMatchCard(match) {
  const scores = sourceScore(match);
  const statusClass = match.completed === "True" ? "post" : "pre";
  const checkStatus = match.crosscheck?.check_status || "待补充";
  const checkLabel = checkStatus === "OK" ? "核对通过" : checkStatus;
  const homeZh = match.crosscheck?.home_team_zh_expected || "";
  const awayZh = match.crosscheck?.away_team_zh_expected || "";
  const compareNote = match.time_discrepancy_note
    ? `<div class="compare-line"><span>时间说明</span><strong>${match.time_discrepancy_note}</strong></div>`
    : "";
  const localTime = fmtLocalDate(match.kickoff_beijing, match.host_city);
  const venue = venueInfo[match.host_city] || {};
  const homeTeamUrl = teamUrl(match, "home");
  const awayTeamUrl = teamUrl(match, "away");
  const lean = Number(match.analysis?.lean_score || 0);
  const factors = parseFactors(match);
  const preMatchSources = parsePreMatchSources(match);
  const homeWin = Number(match.analysis?.home_win_probability ?? 33);
  const draw = Number(match.analysis?.draw_probability ?? 34);
  const awayWin = Number(match.analysis?.away_win_probability ?? 33);

  return `
    <article class="match-card" id="match-${match.match_number}">
      <div class="match-meta">
        <div class="match-number">#${match.match_number}</div>
        <div class="kickoff">${fmtDate(match.kickoff_beijing)}</div>
        <div>${match.stage_cn}${match.group ? ` · ${match.group} 组` : ""}</div>
        <div>当地 ${localTime || "待补充"}</div>
        <div>海拔 ${venue.elevation || "待补充"}</div>
      </div>

      <div class="teams">
        <div class="team-row">
          ${renderTeamName(match, "home")}
          <span class="score">${match.completed === "True" ? match.home_score : ""}</span>
        </div>
        <div class="team-row">
          ${renderTeamName(match, "away")}
          <span class="score">${match.completed === "True" ? match.away_score : ""}</span>
        </div>
        <div class="match-context">
          ${match.stadium}
          <span class="status-pill ${statusClass}">${statusText(match)}</span>
        </div>
        <div class="link-row">
          ${match.espn_summary_url ? `<a href="${match.espn_summary_url}" target="_blank" rel="noreferrer">ESPN 概览</a>` : ""}
          ${match.espn_stats_url ? `<a href="${match.espn_stats_url}" target="_blank" rel="noreferrer">ESPN 数据</a>` : ""}
          ${match.zhibo8?.match_page ? `<a href="${match.zhibo8.match_page}" target="_blank" rel="noreferrer">直播吧</a>` : ""}
        </div>
      </div>

      <aside class="compare-box">
        <h3>信息比对 <span class="check-ok">${checkLabel}</span></h3>
        <div class="lean-block">
          <div class="lean-head">
            <span>赛前倾向</span>
            <strong>${signedScore(lean)}</strong>
          </div>
          <div class="lean-scale" aria-label="赛前倾向值">
            <span style="left:${leanPercent(lean)}%"></span>
          </div>
          <div class="lean-caption">
            <span>${match.home_team}</span>
            <b>${match.analysis?.lean_label || "待定"} · 置信度 ${match.analysis?.confidence || "低"}</b>
            <span>${match.away_team}</span>
          </div>
          <div class="probability-grid" aria-label="赛果概率">
            <div><span>主胜</span><strong>${homeWin}%</strong></div>
            <div><span>平局</span><strong>${draw}%</strong></div>
            <div><span>客胜</span><strong>${awayWin}%</strong></div>
          </div>
        </div>
        <div class="compare-line"><span>主源</span><strong>${scoreFor(match)} · ${match.status}</strong></div>
        <div class="compare-line"><span>直播吧</span><strong>${scores.zhibo8} · ${match.zhibo8?.state_cn || "待补充"}</strong></div>
        <div class="compare-line"><span>比赛ID</span><strong>ESPN ${match.espn_event_id || "-"} / 直播吧 ${match.crosscheck?.zhibo8_match_id || "-"}</strong></div>
        <div class="compare-line"><span>球队资料</span><strong>${homeTeamUrl ? `<a href="${homeTeamUrl}" target="_blank" rel="noreferrer">${homeZh || match.home_team}</a>` : "待补充"} · ${awayTeamUrl ? `<a href="${awayTeamUrl}" target="_blank" rel="noreferrer">${awayZh || match.away_team}</a>` : "待补充"}</strong></div>
        <div class="compare-line"><span>强度评分</span><strong>${match.analysis?.home_rating || "-"} : ${match.analysis?.away_rating || "-"}</strong></div>
        <div class="compare-line"><span>环境</span><strong>${cleanCity(match.host_city)} · 当地 ${localTime || "待补充"} · 海拔 ${venue.elevation || "待补充"}</strong></div>
        ${match.analysis?.environment_note ? `<div class="compare-line"><span>热负荷</span><strong>${match.analysis.environment_note}</strong></div>` : ""}
        <div class="compare-line"><span>临场资料</span><strong>${match.analysis?.pre_match_status || "等待赛前资料"}${match.analysis?.pre_match_updated_at ? ` · ${match.analysis.pre_match_updated_at}` : ""}</strong></div>
        ${match.analysis?.evidence_summary ? `<div class="compare-line"><span>资料摘要</span><strong>${match.analysis.evidence_summary}</strong></div>` : ""}
        ${preMatchSources.length ? `<div class="compare-line"><span>赛前来源</span><strong>${preMatchSources.map((source) => `<a href="${source.url}" target="_blank" rel="noreferrer">${source.name}</a>`).join(" · ")}</strong></div>` : ""}
        ${
          factors.length
            ? `<div class="factor-mini">${factors
                .map((item) => `<span>${item.factor} ${item.value > 0 ? "+" : ""}${item.value}</span>`)
                .join("")}</div>`
            : ""
        }
        ${compareNote}
        <div class="notes-space">赛前资料：首发、伤停、赔率与实时天气会在有来源与时间戳后纳入临场修正；比赛前 1 小时应复核一次。</div>
      </aside>
    </article>
  `;
}

function renderStandings() {
  el("standings").innerHTML = Object.keys(data.standings)
    .sort()
    .map((group) => {
      const rows = data.standings[group];
      return `
        <section class="group-table">
          <h3>${group} 组</h3>
          <table>
            <thead>
              <tr><th>球队</th><th>赛</th><th>胜</th><th>平</th><th>负</th><th>净</th><th>分</th></tr>
            </thead>
            <tbody>
              ${rows
                .map(
                  (row) => `
                  <tr>
                    <td>${row.team}</td>
                    <td>${row.played}</td>
                    <td>${row.wins}</td>
                    <td>${row.draws}</td>
                    <td>${row.losses}</td>
                    <td>${row.goal_difference}</td>
                    <td><strong>${row.points}</strong></td>
                  </tr>`
                )
                .join("")}
            </tbody>
          </table>
        </section>
      `;
    })
    .join("");
}

function renderKnockoutSimulation() {
  const simulation = data.knockout_simulation || {};
  const thirdPlace = simulation.third_place || [];
  const round32 = simulation.round32 || [];
  const path = simulation.path || [];

  el("knockoutNote").textContent =
    simulation.note || "按当前积分榜生成 32 强对阵，随比赛结果刷新。";

  el("thirdPlaceSnapshot").innerHTML = thirdPlace.length
    ? `
      <div class="snapshot-title">最佳小组第三即时排序</div>
      <div class="third-list">
        ${thirdPlace
          .map(
            (row) => `
            <div class="third-item ${row.status === "晋级区" ? "advance" : ""}">
              <strong>${row.rank}. ${row.group}组 ${row.team}</strong>
              <span>${row.points}分 · 净胜${row.goal_difference} · 进${row.goals_for} · ${row.status}</span>
            </div>
          `
          )
          .join("")}
      </div>
    `
    : `<div class="empty-state">暂无第三名排序。</div>`;

  const byRound = path.reduce((acc, match) => {
    acc[match.round] = acc[match.round] || [];
    acc[match.round].push(match);
    return acc;
  }, {});

  const renderBracketMatch = (match, roundClass, isLiveTeams = false) => `
    <article class="bracket-match ${roundClass}">
      <div class="bracket-match-head">
        <span>#${match.match_number}</span>
        <strong>${match.kickoff_beijing ? fmtDate(match.kickoff_beijing) : ""}</strong>
      </div>
      <div class="bracket-team">
        <small>${isLiveTeams ? match.left_source || match.left_rule : "上半区"}</small>
        <b>${match.left_team}</b>
      </div>
      <div class="bracket-team">
        <small>${isLiveTeams ? match.right_source || match.right_rule : "下半区"}</small>
        <b>${match.right_team}</b>
      </div>
      <p>${match.stadium ? `${match.stadium} · ${cleanCity(match.host_city)}` : match.round}</p>
    </article>
  `;

  const pickPath = (numbers) => numbers.map((number) => path.find((match) => Number(match.match_number) === number)).filter(Boolean);
  const finalMatch = (byRound["决赛"] || [])[0];
  const leftRounds = [
    { title: "32强", className: "round-32", matches: round32.slice(0, 8), liveTeams: true },
    { title: "16强", className: "round-16", matches: pickPath([89, 90, 91, 92]) },
    { title: "1/4决赛", className: "round-8", matches: pickPath([97, 99]) },
    { title: "半决赛", className: "round-4", matches: pickPath([101]) },
  ];
  const rightRounds = [
    { title: "半决赛", className: "round-4", matches: pickPath([102]) },
    { title: "1/4决赛", className: "round-8", matches: pickPath([98, 100]) },
    { title: "16强", className: "round-16", matches: pickPath([93, 94, 95, 96]) },
    { title: "32强", className: "round-32", matches: round32.slice(8), liveTeams: true },
  ];

  const renderRound = (round, side) => `
    <section class="bracket-round ${side}-round ${round.className}">
      <h3>${round.title}</h3>
      <div class="bracket-stack">
        ${round.matches
          .map((match) => renderBracketMatch(match, round.className, round.liveTeams))
          .join("")}
      </div>
    </section>
  `;

  const bracketMarkup = round32.length
    ? `
      <div class="bracket-scroll" aria-label="即时淘汰赛树状图">
        <div class="bracket-tree symmetric-tree">
          <div class="bracket-side left-side">
            ${leftRounds.map((round) => renderRound(round, "left")).join("")}
          </div>
          <section class="bracket-center">
            <h3>决赛</h3>
            <div class="bracket-stack">
              ${finalMatch ? renderBracketMatch(finalMatch, "round-final") : ""}
            </div>
          </section>
          <div class="bracket-side right-side">
            ${rightRounds.map((round) => renderRound(round, "right")).join("")}
          </div>
        </div>
      </div>
    `
    : "";

  el("knockoutRound32").innerHTML = round32.length
    ? bracketMarkup
    : `<div class="empty-state">暂无 32 强模拟对阵。</div>`;
  el("bracketFullContent").innerHTML = bracketMarkup;

  const thirdMatch = (byRound["三四名决赛"] || [])[0];
  el("knockoutPath").innerHTML = thirdMatch
    ? `
      <div class="third-place-card">
        <span>#${thirdMatch.match_number} 三四名决赛</span>
        <strong>${thirdMatch.left_team} vs ${thirdMatch.right_team}</strong>
        <em>${thirdMatch.kickoff_beijing ? fmtDate(thirdMatch.kickoff_beijing) : ""} · ${thirdMatch.stadium || ""}</em>
      </div>
    `
    : "";
}

function openBracketFull() {
  const overlay = el("bracketOverlay");
  overlay.classList.add("open");
  overlay.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  const scroller = overlay.querySelector(".bracket-scroll");
  if (scroller) {
    scroller.scrollLeft = Math.max(0, (scroller.scrollWidth - scroller.clientWidth) / 2);
  }
}

function closeBracketFull() {
  const overlay = el("bracketOverlay");
  overlay.classList.remove("open");
  overlay.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function renderVenues() {
  el("venues").innerHTML = data.venues
    .map(
      (venue) => `
      <div class="venue">
        <strong>${venue.stadium}</strong>
        <span>${cleanCity(venue.host_city)} · ${venue.match_count} 场</span>
      </div>
    `
    )
    .join("");
}

function donutGradient(items) {
  let cursor = 0;
  return items
    .map((item) => {
      const start = cursor;
      cursor += item.value;
      return `${item.color} ${start}% ${cursor}%`;
    })
    .join(", ");
}

function renderInfluenceModels() {
  el("influenceModels").innerHTML = influenceModels
    .map(
      (model) => `
      <article class="model-card">
        <div class="model-chart" style="--segments: ${donutGradient(model.items)}">
          <div>
            <strong>100%</strong>
            <span>${model.subtitle}</span>
          </div>
        </div>
        <div class="model-content">
          <h3>${model.title}</h3>
          <p>${model.note}</p>
          <div class="factor-list">
            ${model.items
              .map(
                (item) => `
                <div class="factor">
                  <span class="swatch" style="background:${item.color}"></span>
                  <div>
                    <strong>${item.name}</strong>
                    <small>${item.detail}</small>
                  </div>
                  <b>${item.value}%</b>
                </div>
              `
              )
              .join("")}
          </div>
        </div>
      </article>
    `
    )
    .join("");
}

initMeta();
initFilters();
initBracketOverlay();
renderMatches();
renderInfluenceModels();
renderKnockoutSimulation();
renderStandings();
renderVenues();
