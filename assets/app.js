const STORAGE_KEY = "clinical-job-direct-v1";
const FEED_URL = "./data/jobs_latest.json";
const REPORT_URL = "./data/fetch_report.json";

const CITY_HINTS = [
  "北京", "上海", "广州", "深圳", "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
  "南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港", "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁",
  "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"
];

const listEl = document.getElementById("job-list");
const countEl = document.getElementById("list-count");
const syncBtn = document.getElementById("sync-jobs-btn");
const syncStatus = document.getElementById("sync-status");

const filterKeyword = document.getElementById("filter-keyword");
const filterDiscipline = document.getElementById("filter-discipline");
const filterDegree = document.getElementById("filter-degree");

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function normalizeText(text) {
  return String(text || "").replace(/\s+/g, " ").trim();
}

function normalizeDate(value) {
  const text = normalizeText(value);
  if (!text) return "";

  const m = text.match(/(20\d{2})[-/.年]\s*(\d{1,2})[-/.月]\s*(\d{1,2})/);
  if (m) {
    return `${m[1]}-${String(Number(m[2])).padStart(2, "0")}-${String(Number(m[3])).padStart(2, "0")}`;
  }

  const d = new Date(text);
  if (!Number.isNaN(d.getTime())) {
    return d.toISOString().slice(0, 10);
  }

  return "";
}

function stableHash(input) {
  let hash = 0;
  const str = String(input || "");
  for (let i = 0; i < str.length; i += 1) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

function isDirectJobLink(link) {
  const text = normalizeText(link);
  if (!text) return false;

  try {
    const u = new URL(text);
    if (!["http:", "https:"].includes(u.protocol)) return false;

    const path = (u.pathname || "/").toLowerCase().replace(/\/+$/, "") || "/";
    const query = (u.search || "").toLowerCase();

    if (path === "/") return false;

    const genericRoots = new Set([
      "/index",
      "/index.html",
      "/home",
      "/work",
      "/jobs",
      "/job",
      "/search",
      "/career",
      "/careers",
      "/zhaopin",
      "/list",
      "/channel"
    ]);
    if (genericRoots.has(path) && !query) return false;

    const detailByPath = /(\d{4,}|\.s?html?$|\.aspx?$|\/detail\/|\/article\/|\/view\/|\/notice\/|\/content\/|\/recruit\/)/.test(path);
    const detailByQuery = /(?:^|[?&])(id|aid|articleid|noticeid|jobid|recruitid)=/.test(query);
    return detailByPath || detailByQuery;
  } catch {
    return false;
  }
}

function isDoctoralOnlyPosting(text) {
  const s = normalizeText(text);
  const doctoral = /博士后|博士|phd|postdoc|post-doc/i.test(s);
  const bachelorOrMaster = /本科|学士|硕士|研究生|专硕|本硕|本科及以上|硕士及以上/.test(s);
  return doctoral && !bachelorOrMaster;
}

function inferDiscipline(text, majorTags) {
  if (Array.isArray(majorTags)) {
    if (majorTags.includes("clinical_lab")) return "临床检验诊断学";
    if (majorTags.includes("pharmacy")) return "药学";
    if (majorTags.includes("biology")) return "生物学";
  }
  if (/临床检验|检验医学|医学检验/.test(text)) return "临床检验诊断学";
  if (/药学|药剂|药物|制药/.test(text)) return "药学";
  return "生物学";
}

function inferDegree(text) {
  if (/本科及以上|本硕/.test(text)) return "本硕不限";
  if (/本科|学士/.test(text)) return "本科";
  if (/硕士|研究生|专硕|硕士及以上/.test(text)) return "硕士";
  return "本硕不限";
}

function inferCity(text) {
  const hit = CITY_HINTS.find((city) => text.includes(city));
  return hit || "待补充";
}

function inferOrganization(title, snippet, sourceName) {
  const text = normalizeText(`${title} ${snippet}`);
  const m = text.match(/([^，。；\s]{2,30}(?:医院|大学|学院|疾控中心|血站|委员会|研究院|学校))/);
  if (m) return m[1];
  return sourceName || "待补充单位";
}

function ensureShape(raw) {
  return {
    id: raw.id,
    title: raw.title,
    discipline: raw.discipline,
    degree: raw.degree,
    organization: raw.organization,
    city: raw.city,
    sourceChannel: raw.sourceChannel,
    applyLink: raw.applyLink,
    publishDate: raw.publishDate,
    notes: raw.notes,
    createdAt: raw.createdAt || todayDate()
  };
}

function loadJobs() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((job) => job && isDirectJobLink(job.applyLink))
      .map(ensureShape);
  } catch {
    return [];
  }
}

function saveJobs(nextJobs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(nextJobs));
}

let jobs = loadJobs();

function escapeHtml(input) {
  return String(input || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setSyncStatus(message) {
  if (syncStatus) syncStatus.textContent = message;
}

function normalizeImportedItem(raw) {
  const title = normalizeText(raw.title);
  const applyLink = normalizeText(raw.link || raw.apply_link || raw.url);
  const snippet = normalizeText(raw.snippet);
  const sourceChannel = normalizeText(raw.source_name || raw.source || "未知来源");
  const mergedText = normalizeText(`${title} ${snippet}`);

  if (!title || !isDirectJobLink(applyLink)) return null;
  if (isDoctoralOnlyPosting(mergedText)) return null;

  return {
    id: `auto-${stableHash(applyLink)}`,
    title,
    discipline: inferDiscipline(mergedText, raw.major_tags),
    degree: inferDegree(mergedText),
    organization: inferOrganization(title, snippet, sourceChannel),
    city: inferCity(mergedText),
    sourceChannel,
    applyLink,
    publishDate: normalizeDate(raw.publish_date || raw.first_seen_at) || "待补充",
    notes: snippet.slice(0, 220),
    createdAt: todayDate()
  };
}

function filteredJobs() {
  const keyword = normalizeText(filterKeyword?.value).toLowerCase();
  const discipline = filterDiscipline?.value || "全部";
  const degree = filterDegree?.value || "全部";

  return jobs
    .filter((job) => {
      const text = `${job.title} ${job.organization} ${job.city} ${job.notes} ${job.sourceChannel}`.toLowerCase();
      const keywordMatch = !keyword || text.includes(keyword);
      const disciplineMatch = discipline === "全部" || job.discipline === discipline;
      const degreeMatch = degree === "全部" || job.degree === degree;
      return keywordMatch && disciplineMatch && degreeMatch;
    })
    .sort((a, b) => String(b.publishDate).localeCompare(String(a.publishDate)));
}

function renderList() {
  if (!listEl || !countEl) return;

  const rows = filteredJobs();
  countEl.textContent = `${rows.length} 条`;

  if (!rows.length) {
    listEl.innerHTML = '<div class="empty">暂无可直达岗位。请先运行采集并点击“同步最新岗位”。</div>';
    return;
  }

  listEl.innerHTML = rows
    .map(
      (job) => `
      <article class="job-card">
        <div class="job-title-row">
          <h3 class="job-title">${escapeHtml(job.title)}</h3>
          <span class="badge ${job.discipline === "临床检验诊断学" ? "lab" : job.discipline === "药学" ? "pharma" : "bio"}">${escapeHtml(job.discipline)}</span>
        </div>
        <div class="meta-grid">
          <div><span>单位：</span>${escapeHtml(job.organization)}</div>
          <div><span>城市：</span>${escapeHtml(job.city)}</div>
          <div><span>学历：</span>${escapeHtml(job.degree)}</div>
          <div><span>来源：</span>${escapeHtml(job.sourceChannel)}</div>
          <div><span>发布日期：</span>${escapeHtml(job.publishDate)}</div>
        </div>
        <div class="card-actions">
          <a class="btn-mini" href="${escapeHtml(job.applyLink)}" target="_blank" rel="noreferrer">报名链接</a>
        </div>
      </article>`
    )
    .join("");
}

function mergeImportedJobs(items) {
  let inserted = 0;
  let updated = 0;
  let skipped = 0;

  for (const raw of items) {
    const item = normalizeImportedItem(raw);
    if (!item) {
      skipped += 1;
      continue;
    }

    const idx = jobs.findIndex((job) => job.applyLink === item.applyLink);
    if (idx < 0) {
      jobs.push(item);
      inserted += 1;
    } else {
      jobs[idx] = { ...jobs[idx], ...item, id: jobs[idx].id };
      updated += 1;
    }
  }

  saveJobs(jobs);
  renderList();
  return { inserted, updated, skipped };
}

async function loadCollectorReport() {
  try {
    const resp = await fetch(`${REPORT_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!resp.ok) return;

    const report = await resp.json();
    const finished = normalizeDate(report.finished_at || "");
    if (!finished) return;

    const accepted = Number(report.accepted || 0);
    const rejectedNonDirect = Number(report.rejected_non_direct || 0);
    const rejectedUnreachable = Number(report.rejected_unreachable || 0);
    setSyncStatus(`最近采集：${finished}；直达候选 ${accepted}，过滤首页 ${rejectedNonDirect}，过滤不可达 ${rejectedUnreachable}`);
  } catch {
    // Ignore report errors.
  }
}

async function syncJobsFromFeed() {
  if (!syncBtn) return;

  syncBtn.disabled = true;
  setSyncStatus("正在同步最新岗位...");

  try {
    const resp = await fetch(`${FEED_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!resp.ok) {
      throw new Error("未找到采集数据，请先运行更新脚本");
    }

    const payload = await resp.json();
    const items = Array.isArray(payload.items) ? payload.items : [];
    const result = mergeImportedJobs(items);
    setSyncStatus(`同步完成：新增 ${result.inserted} 条，更新 ${result.updated} 条，跳过 ${result.skipped} 条无效链接`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "未知错误";
    setSyncStatus(`同步失败：${msg}`);
  } finally {
    syncBtn.disabled = false;
  }
}

[filterKeyword, filterDiscipline, filterDegree].forEach((el) => {
  if (!el) return;
  el.addEventListener("input", renderList);
  el.addEventListener("change", renderList);
});

if (syncBtn) {
  syncBtn.addEventListener("click", syncJobsFromFeed);
}

renderList();
loadCollectorReport();
