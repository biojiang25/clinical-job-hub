const STORAGE_KEY = "clinical-job-hub-data-v1";
const FEED_URL = "./data/jobs_latest.json";
const REPORT_URL = "./data/fetch_report.json";

const seedJobs = [
  {
    id: "job-001",
    title: "临床检验技术员（科研协作岗）",
    discipline: "临床检验诊断学",
    degree: "硕士",
    organization: "上海某三甲医院检验科",
    city: "上海",
    sourceChannel: "丁香人才网",
    salary: "14k-22k/月",
    deadline: "2026-04-15",
    source: "https://www.jobmd.cn/work/",
    notes: "优先考虑有流式细胞术与PCR实验经验。",
    createdAt: "2026-03-01",
    recordType: "manual"
  },
  {
    id: "job-002",
    title: "药物分析研究员",
    discipline: "药学",
    degree: "硕士",
    organization: "广州某创新药企业",
    city: "广州",
    sourceChannel: "医药英才网",
    salary: "16k-28k/月",
    deadline: "2026-03-28",
    source: "https://www.healthr.com/",
    notes: "LC-MS/MS方法开发经验加分。",
    createdAt: "2026-03-02",
    recordType: "manual"
  },
  {
    id: "job-003",
    title: "分子生物学研发助理",
    discipline: "生物学",
    degree: "本科",
    organization: "苏州某生物技术平台",
    city: "苏州",
    sourceChannel: "BOSS直聘",
    salary: "13k-20k/月",
    deadline: "2026-04-05",
    source: "https://www.zhipin.com/",
    notes: "需熟悉慢病毒包装、qPCR和细胞培养。",
    createdAt: "2026-03-03",
    recordType: "manual"
  }
];

const CITY_HINTS = [
  "北京",
  "上海",
  "广州",
  "深圳",
  "杭州",
  "宁波",
  "温州",
  "嘉兴",
  "湖州",
  "绍兴",
  "金华",
  "衢州",
  "舟山",
  "台州",
  "丽水",
  "南京",
  "无锡",
  "徐州",
  "常州",
  "苏州",
  "南通",
  "连云港",
  "淮安",
  "盐城",
  "扬州",
  "镇江",
  "泰州",
  "宿迁",
  "合肥",
  "芜湖",
  "蚌埠",
  "淮南",
  "马鞍山",
  "淮北",
  "铜陵",
  "安庆",
  "黄山",
  "滁州",
  "阜阳",
  "宿州",
  "六安",
  "亳州",
  "池州",
  "宣城"
];

const form = document.getElementById("job-form");
const listEl = document.getElementById("job-list");
const countEl = document.getElementById("list-count");
const resetBtn = document.getElementById("reset-btn");
const syncBtn = document.getElementById("sync-jobs-btn");
const syncStatus = document.getElementById("sync-status");

const filterKeyword = document.getElementById("filter-keyword");
const filterDiscipline = document.getElementById("filter-discipline");
const filterChannel = document.getElementById("filter-channel");
const filterCity = document.getElementById("filter-city");

const fields = {
  id: document.getElementById("job-id"),
  title: document.getElementById("title"),
  discipline: document.getElementById("discipline"),
  degree: document.getElementById("degree"),
  organization: document.getElementById("organization"),
  city: document.getElementById("city"),
  salary: document.getElementById("salary"),
  deadline: document.getElementById("deadline"),
  sourceChannel: document.getElementById("source-channel"),
  source: document.getElementById("source"),
  notes: document.getElementById("notes")
};

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function normalizeText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeDate(value) {
  if (!value) return "";
  const text = String(value).trim();

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

function ensureJobShape(raw) {
  return {
    id: raw.id || `job-${Date.now()}`,
    title: raw.title || "未命名岗位",
    discipline: raw.discipline || "生物学",
    degree: raw.degree || "本硕不限",
    organization: raw.organization || "待补充单位",
    city: raw.city || "待补充",
    sourceChannel: raw.sourceChannel || "其他",
    salary: raw.salary || "",
    deadline: raw.deadline || "",
    source: raw.source || "",
    notes: raw.notes || "",
    createdAt: normalizeDate(raw.createdAt) || todayDate(),
    recordType: raw.recordType || "manual"
  };
}

function loadJobs() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const seeded = seedJobs.map(ensureJobShape);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(seeded));
    return seeded;
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length === 0) {
      const seeded = seedJobs.map(ensureJobShape);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(seeded));
      return seeded;
    }
    return parsed.map(ensureJobShape);
  } catch {
    const seeded = seedJobs.map(ensureJobShape);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(seeded));
    return seeded;
  }
}

function saveJobs(nextJobs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(nextJobs));
}

let jobs = loadJobs();

function stableHash(input) {
  let hash = 0;
  const str = String(input || "");
  for (let i = 0; i < str.length; i += 1) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
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

function isDoctoralOnlyPosting(text) {
  const doctoral = /博士后|博士|phd|postdoc|post-doc/i.test(text);
  const bachelorOrMaster = /本科|学士|硕士|研究生|专硕|本硕|本科及以上/.test(text);
  return doctoral && !bachelorOrMaster;
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

function setSyncStatus(message) {
  if (!syncStatus) return;
  syncStatus.textContent = message;
}

function escapeHtml(input) {
  return String(input || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function disciplineClass(value) {
  if (value === "临床检验诊断学") return "lab";
  if (value === "药学") return "pharma";
  return "bio";
}

function filteredJobs() {
  const keyword = filterKeyword.value.trim().toLowerCase();
  const discipline = filterDiscipline.value;
  const channel = filterChannel.value;
  const city = filterCity.value.trim().toLowerCase();

  return jobs
    .filter((job) => {
      const text = [job.title, job.organization, job.notes, job.city, job.sourceChannel].join(" ").toLowerCase();
      const keywordMatch = !keyword || text.includes(keyword);
      const disciplineMatch = discipline === "全部" || job.discipline === discipline;
      const channelMatch = channel === "全部" || job.sourceChannel === channel;
      const cityMatch = !city || (job.city || "").toLowerCase().includes(city);
      return keywordMatch && disciplineMatch && channelMatch && cityMatch;
    })
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

function renderList() {
  const rows = filteredJobs();
  countEl.textContent = `${rows.length} 条`;

  if (!rows.length) {
    listEl.innerHTML = '<div class="empty">当前筛选条件下暂无职位，试试放宽筛选或先发布一条新职位。</div>';
    return;
  }

  listEl.innerHTML = rows
    .map((job) => {
      const sourceHtml = job.source
        ? `<a class="btn-mini" href="${escapeHtml(job.source)}" target="_blank" rel="noreferrer">来源链接</a>`
        : "";

      return `
      <article class="job-card">
        <div class="job-title-row">
          <h3 class="job-title">${escapeHtml(job.title)}</h3>
          <span class="badge ${disciplineClass(job.discipline)}">${escapeHtml(job.discipline)}</span>
        </div>

        <div class="meta-grid">
          <div><span>单位：</span>${escapeHtml(job.organization)}</div>
          <div><span>城市：</span>${escapeHtml(job.city)}</div>
          <div><span>学历：</span>${escapeHtml(job.degree)}</div>
          <div><span>渠道：</span>${escapeHtml(job.sourceChannel || "未填写")}</div>
          <div><span>薪资：</span>${escapeHtml(job.salary || "未填写")}</div>
          <div><span>截止：</span>${escapeHtml(job.deadline || "未填写")}</div>
          <div><span>发布时间：</span>${escapeHtml(job.createdAt || "-")}</div>
          <div><span>类型：</span>${job.recordType === "auto" ? "自动采集" : "手动维护"}</div>
        </div>

        <p class="note">${escapeHtml(job.notes || "暂无备注")}</p>

        <div class="card-actions">
          <button class="btn-mini" data-action="edit" data-id="${escapeHtml(job.id)}">编辑</button>
          <button class="btn-mini delete" data-action="delete" data-id="${escapeHtml(job.id)}">删除</button>
          ${sourceHtml}
        </div>
      </article>`;
    })
    .join("");
}

function clearForm() {
  fields.id.value = "";
  fields.title.value = "";
  fields.discipline.value = "";
  fields.degree.value = "";
  fields.organization.value = "";
  fields.city.value = "";
  fields.salary.value = "";
  fields.deadline.value = "";
  fields.sourceChannel.value = "";
  fields.source.value = "";
  fields.notes.value = "";
}

function fillForm(job) {
  fields.id.value = job.id;
  fields.title.value = job.title;
  fields.discipline.value = job.discipline;
  fields.degree.value = job.degree;
  fields.organization.value = job.organization;
  fields.city.value = job.city;
  fields.salary.value = job.salary || "";
  fields.deadline.value = job.deadline || "";
  fields.sourceChannel.value = job.sourceChannel || "";
  fields.source.value = job.source || "";
  fields.notes.value = job.notes || "";
  fields.title.focus();
}

function toAutoJob(raw) {
  const title = normalizeText(raw.title);
  if (!title) return null;

  const link = normalizeText(raw.link || "");
  const snippet = normalizeText(raw.snippet || "");
  const sourceName = normalizeText(raw.source_name || "自动采集");
  const mergedText = `${title} ${snippet}`;
  if (isDoctoralOnlyPosting(mergedText)) return null;

  return ensureJobShape({
    id: `auto-${stableHash(link || `${sourceName}-${title}`)}`,
    title,
    discipline: inferDiscipline(mergedText, raw.major_tags),
    degree: inferDegree(mergedText),
    organization: inferOrganization(title, snippet, sourceName),
    city: inferCity(mergedText),
    sourceChannel: sourceName,
    salary: "",
    deadline: "",
    source: link,
    notes: snippet.slice(0, 220),
    createdAt: normalizeDate(raw.publish_date || raw.first_seen_at) || todayDate(),
    recordType: "auto"
  });
}

function mergeCollectedJobs(items) {
  let inserted = 0;
  let updated = 0;

  for (const raw of items) {
    const next = toAutoJob(raw);
    if (!next) continue;

    const idx = jobs.findIndex((job) => {
      if (next.source && job.source) return job.source === next.source;
      return job.id === next.id;
    });

    if (idx === -1) {
      jobs.push(next);
      inserted += 1;
      continue;
    }

    const current = jobs[idx];
    jobs[idx] = ensureJobShape({
      ...current,
      ...next,
      id: current.id,
      salary: current.salary || next.salary,
      deadline: current.deadline || next.deadline,
      notes: current.recordType === "manual" ? current.notes : next.notes,
      createdAt: current.createdAt || next.createdAt,
      recordType: current.recordType === "manual" ? "manual" : "auto"
    });
    updated += 1;
  }

  saveJobs(jobs);
  renderList();
  return { inserted, updated };
}

async function loadCollectorReport() {
  try {
    const resp = await fetch(`${REPORT_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!resp.ok) return;

    const report = await resp.json();
    if (!report || typeof report !== "object") return;

    const finished = normalizeDate(report.finished_at || report.generated_at || "");
    const accepted = Number(report.accepted || 0);
    const inserted = Number(report.inserted || 0);

    if (finished) {
      setSyncStatus(`最近采集：${finished}，候选 ${accepted} 条，入库 ${inserted} 条`);
    }
  } catch {
    // Keep default status when report is unavailable.
  }
}

async function syncJobsFromFeed() {
  if (!syncBtn) return;

  syncBtn.disabled = true;
  setSyncStatus("正在同步最新岗位...");

  try {
    const resp = await fetch(`${FEED_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!resp.ok) {
      throw new Error(`无法读取 ${FEED_URL}，请先执行采集脚本`);
    }

    const payload = await resp.json();
    const items = Array.isArray(payload.items) ? payload.items : [];

    if (!items.length) {
      setSyncStatus("同步完成：采集结果为空（请先运行每日抓取脚本）");
      return;
    }

    const result = mergeCollectedJobs(items);
    setSyncStatus(`同步完成：新增 ${result.inserted} 条，更新 ${result.updated} 条`);
  } catch (err) {
    setSyncStatus(`同步失败：${err instanceof Error ? err.message : "未知错误"}`);
  } finally {
    syncBtn.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();

  const payload = ensureJobShape({
    id: fields.id.value || `job-${Date.now()}`,
    title: fields.title.value.trim(),
    discipline: fields.discipline.value,
    degree: fields.degree.value,
    organization: fields.organization.value.trim(),
    city: fields.city.value.trim(),
    salary: fields.salary.value.trim(),
    deadline: fields.deadline.value,
    sourceChannel: fields.sourceChannel.value,
    source: fields.source.value.trim(),
    notes: fields.notes.value.trim(),
    createdAt: fields.id.value ? undefined : todayDate(),
    recordType: "manual"
  });

  if (fields.id.value) {
    jobs = jobs.map((job) => {
      if (job.id !== payload.id) return job;
      return ensureJobShape({
        ...job,
        ...payload,
        createdAt: job.createdAt,
        recordType: "manual"
      });
    });
  } else {
    jobs.push(payload);
  }

  saveJobs(jobs);
  clearForm();
  renderList();
});

resetBtn.addEventListener("click", clearForm);

[filterKeyword, filterDiscipline, filterChannel, filterCity].forEach((el) => {
  el.addEventListener("input", renderList);
  el.addEventListener("change", renderList);
});

if (syncBtn) {
  syncBtn.addEventListener("click", syncJobsFromFeed);
}

listEl.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const action = target.dataset.action;
  const id = target.dataset.id;
  if (!action || !id) return;

  const targetJob = jobs.find((job) => job.id === id);
  if (!targetJob) return;

  if (action === "edit") {
    fillForm(targetJob);
    window.location.hash = "job-form";
  }

  if (action === "delete") {
    const confirmed = window.confirm(`确认删除职位：${targetJob.title} ?`);
    if (!confirmed) return;
    jobs = jobs.filter((job) => job.id !== id);
    saveJobs(jobs);
    if (fields.id.value === id) clearForm();
    renderList();
  }
});

renderList();
loadCollectorReport();
