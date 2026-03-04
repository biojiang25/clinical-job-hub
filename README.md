# 临床检验 / 药学 / 生物学求职信息站

参考 `APICompare` 的简洁 CRUD 信息架构，改造为医学相关岗位信息站，当前以本科/硕士可报名岗位为主（默认过滤博士/博士后导向岗位）。

## 功能

- 首页概览：岗位总数与学科分布
- 岗位直达清单：只展示可直达详情/报名页面的链接
- 轻量筛选：关键词、学科方向、学历（本科/硕士）
- 自动更新：采集脚本输出 `data/jobs_latest.json`，前端一键同步
- 渠道雷达：高频岗位渠道面板（医院、卫健委、事业编、疾控、血站、高校等）

## 本地运行

```bash
cd /Users/jianglan/clinical-job-hub
python3 -m http.server 8080
```

访问：`http://127.0.0.1:8080`

## 岗位更新（本地）

1. 执行采集：

```bash
cd /Users/jianglan/clinical-job-hub
bash scripts/update_jobs.sh
```

2. 在网页 `jobs.html` 点击“同步最新岗位”。
3. 页面会自动跳过无效链接（如站点首页、泛列表页、不可达链接）。

## GitHub 直接部署

本仓库已包含两个工作流：

- `collect-jobs.yml`：每日定时采集并提交 `data/*.json`
- `deploy-pages.yml`：推送到 `main` 后自动部署 GitHub Pages

### 启用步骤

1. 推送仓库到 GitHub（默认分支 `main`）。
2. 在仓库 `Settings -> Pages` 里将 `Source` 设为 `GitHub Actions`。
3. 在 `Actions` 页面手动运行一次：
   - `Collect Jobs Data`
   - `Deploy Static Site`

完成后即可获得在线站点，且每天自动更新岗位数据。

## 目录

```text
clinical-job-hub/
  index.html
  jobs.html
  channels.html
  assets/
    styles.css
    app.js
  collector/
    fetch_daily_jobs.py
    sources.json
    keywords.json
  scripts/
    update_jobs.sh
  data/
    jobs_latest.json
    jobs_today.json
    fetch_report.json
  .github/workflows/
    collect-jobs.yml
    deploy-pages.yml
```
