#!/usr/bin/env python3
"""Collect WeChat public-account job leads.

This collector is intentionally conservative:
- Keeps only direct article links on mp.weixin.qq.com.
- Stores lead metadata (title/date/source/snippet/link), not full article content.
- Runs as an auxiliary pipeline and should not block the core job collector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from lxml import etree
from lxml import html as lxml_html


DEFAULT_TIMEOUT = 12
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36 WechatLeadCollector/1.0"
)


@dataclass
class LeadCandidate:
    source_id: str
    source_name: str
    source_category: str
    title: str
    link: str
    snippet: str
    publish_date: Optional[str]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_date(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"(20\d{2})[-/.年]\s*(\d{1,2})[-/.月]\s*(\d{1,2})", text.strip())
    if not m:
        return None
    year, month, day = m.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def parse_rss_datetime(value: str) -> Optional[str]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        return dt.date().isoformat()
    except Exception:
        return extract_date(value)


def is_wechat_article_link(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").split(":")[0].lower()
    if host != "mp.weixin.qq.com":
        return False
    path = (parsed.path or "").lower()
    query = (parsed.query or "").lower()
    if not path:
        return False
    # WeChat article links are usually /s?... or /mp/appmsg...
    path_ok = path.startswith("/s") or "appmsg" in path
    query_ok = "__biz=" in query or "mid=" in query or "sn=" in query
    return path_ok and query_ok


def unwrap_redirect_url(url: str) -> str:
    """Unwrap possible redirect wrappers and keep direct mp.weixin.qq.com links only."""
    current = normalize_text(url)
    if not current:
        return current

    if is_wechat_article_link(current):
        return current

    try:
        parsed = urlparse(current)
    except Exception:
        return current

    qs = parse_qs(parsed.query or "", keep_blank_values=True)
    for key in ("url", "target", "target_url", "u"):
        values = qs.get(key, [])
        for value in values:
            candidate = value
            # Some wrappers are URL-encoded multiple times.
            for _ in range(2):
                candidate = unquote(candidate)
            if is_wechat_article_link(candidate):
                return candidate
    return current


def fetch_text(session: requests.Session, url: str, timeout: int, retries: int = 2) -> str:
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as err:  # noqa: BLE001
            last_err = err
            time.sleep(0.8)
    raise RuntimeError(f"fetch failed: {url}, error={last_err}")


def verify_reachable_link(
    session: requests.Session,
    url: str,
    timeout: int,
    retries: int = 1,
) -> Tuple[bool, str, Optional[int], str]:
    last_err = ""
    for _ in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            status = resp.status_code
            final_url = resp.url
            if status < 400:
                return True, final_url, status, ""
            last_err = f"status={status}"
        except Exception as err:  # noqa: BLE001
            last_err = str(err)
        time.sleep(0.4)
    return False, url, None, last_err


def parse_rss(source: Dict[str, Any], content: str, max_links: int) -> List[LeadCandidate]:
    out: List[LeadCandidate] = []
    root = etree.fromstring(content.encode("utf-8", errors="ignore"))
    items = root.xpath("//item") or root.xpath("//*[local-name()='entry']")

    for item in items[:max_links]:
        title = normalize_text("".join(item.xpath("./title//text()")))
        link = normalize_text("".join(item.xpath("./link/@href"))) or normalize_text(
            "".join(item.xpath("./link//text()"))
        )
        snippet = normalize_text("".join(item.xpath("./description//text()"))) or normalize_text(
            "".join(item.xpath("./summary//text()"))
        )
        pub_raw = normalize_text("".join(item.xpath("./pubDate//text()"))) or normalize_text(
            "".join(item.xpath("./updated//text()"))
        )
        publish_date = parse_rss_datetime(pub_raw)

        if not title or not link:
            continue

        full_link = unwrap_redirect_url(urljoin(source["url"], link))
        if not is_wechat_article_link(full_link):
            continue

        out.append(
            LeadCandidate(
                source_id=source["id"],
                source_name=source["name"],
                source_category=source.get("category", ""),
                title=title,
                link=full_link,
                snippet=snippet,
                publish_date=publish_date,
            )
        )
    return out


def parse_html(source: Dict[str, Any], content: str, max_links: int) -> List[LeadCandidate]:
    out: List[LeadCandidate] = []
    tree = lxml_html.fromstring(content)
    anchors = tree.xpath("//a[@href]")

    for a in anchors[: max_links * 5]:
        href = normalize_text(a.get("href", ""))
        if not href or href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        full_link = unwrap_redirect_url(urljoin(source["url"], href))
        if not is_wechat_article_link(full_link):
            continue

        title = normalize_text(a.get("title", "")) or normalize_text("".join(a.xpath(".//text()")))
        if len(title) < 6:
            continue

        context_node = a.xpath("ancestor::li[1] | ancestor::article[1] | ancestor::div[1] | ancestor::tr[1]")
        context_text = normalize_text(" ".join(context_node[0].xpath(".//text()"))) if context_node else title
        publish_date = extract_date(f"{title} {context_text}")

        out.append(
            LeadCandidate(
                source_id=source["id"],
                source_name=source["name"],
                source_category=source.get("category", ""),
                title=title,
                link=full_link,
                snippet=context_text[:500],
                publish_date=publish_date,
            )
        )
        if len(out) >= max_links:
            break

    return out


def flatten_major_terms(keyword_cfg: Dict[str, Any]) -> List[str]:
    major_keywords = keyword_cfg.get("major_keywords", {})
    terms: List[str] = []
    if isinstance(major_keywords, dict):
        for _, tokens in major_keywords.items():
            if isinstance(tokens, list):
                terms.extend([normalize_text(str(t)) for t in tokens if normalize_text(str(t))])
    if not terms:
        terms = [
            "临床检验",
            "检验医学",
            "医学检验",
            "临床检验诊断学",
            "病理",
            "药学",
            "药剂",
            "药物",
            "生物学",
            "生物技术",
            "生物工程",
        ]
    return list(dict.fromkeys(terms))


def score_candidate(candidate: LeadCandidate, source: Dict[str, Any], major_terms: List[str]) -> Tuple[int, Dict[str, Any]]:
    text = normalize_text(f"{candidate.title} {candidate.snippet}").lower()

    major_hits = [term for term in major_terms if term.lower() in text]
    if not major_hits:
        return 0, {"major_hits": []}

    doctoral = bool(re.search(r"博士后|博士|phd|postdoc|post-doc", text, re.IGNORECASE))
    bachelor_or_master = bool(re.search(r"本科|学士|硕士|研究生|专硕|本硕|本科及以上|硕士及以上", text))
    if doctoral and not bachelor_or_master:
        return 0, {"major_hits": major_hits, "doctoral_only": True}

    source_include_hits = [
        token
        for token in source.get("include_any", [])
        if normalize_text(str(token)).lower() in text
    ]

    score = 2  # major hits are mandatory in this pipeline
    if bachelor_or_master:
        score += 1
    if source_include_hits:
        score += 1
    return score, {
        "major_hits": major_hits,
        "bachelor_or_master": bachelor_or_master,
        "source_include_hits": source_include_hits,
    }


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wechat_leads (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_category TEXT,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            snippet TEXT,
            publish_date TEXT,
            score INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wechat_seen ON wechat_leads(last_seen_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wechat_pub ON wechat_leads(publish_date)")
    conn.commit()
    return conn


def make_id(source_id: str, title: str, link: str) -> str:
    text = f"{source_id}|{normalize_text(title)}|{normalize_text(link)}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def upsert_lead(conn: sqlite3.Connection, candidate: LeadCandidate, score: int, ts: str) -> bool:
    lid = make_id(candidate.source_id, candidate.title, candidate.link)
    exists = conn.execute("SELECT id FROM wechat_leads WHERE id = ?", (lid,)).fetchone()
    if exists:
        conn.execute(
            """
            UPDATE wechat_leads
            SET snippet = ?, publish_date = COALESCE(?, publish_date), score = ?, last_seen_at = ?
            WHERE id = ?
            """,
            (candidate.snippet, candidate.publish_date, score, ts, lid),
        )
        return False

    conn.execute(
        """
        INSERT INTO wechat_leads (
            id, source_id, source_name, source_category, title, link, snippet,
            publish_date, score, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lid,
            candidate.source_id,
            candidate.source_name,
            candidate.source_category,
            candidate.title,
            candidate.link,
            candidate.snippet,
            candidate.publish_date,
            score,
            ts,
            ts,
        ),
    )
    return True


def export_snapshots(conn: sqlite3.Connection, latest_limit: int) -> Dict[str, Any]:
    latest_rows = conn.execute(
        """
        SELECT title, link, source_name, source_category, publish_date,
               first_seen_at, last_seen_at, score, snippet
        FROM wechat_leads
        ORDER BY COALESCE(publish_date, substr(first_seen_at, 1, 10)) DESC, last_seen_at DESC
        LIMIT ?
        """,
        (latest_limit,),
    ).fetchall()

    today = datetime.now().date().isoformat()
    today_rows = conn.execute(
        """
        SELECT title, link, source_name, source_category, publish_date,
               first_seen_at, last_seen_at, score, snippet
        FROM wechat_leads
        WHERE substr(first_seen_at, 1, 10) = ?
        ORDER BY last_seen_at DESC
        """,
        (today,),
    ).fetchall()

    cols = [
        "title",
        "link",
        "source_name",
        "source_category",
        "publish_date",
        "first_seen_at",
        "last_seen_at",
        "score",
        "snippet",
    ]

    def to_dict(rows: Iterable[Tuple[Any, ...]]) -> List[Dict[str, Any]]:
        return [dict(zip(cols, row)) for row in rows]

    return {
        "latest": to_dict(latest_rows),
        "today": to_dict(today_rows),
    }


def collect(args: argparse.Namespace) -> int:
    sources = load_json(Path(args.sources))
    keyword_cfg = load_json(Path(args.keywords))
    major_terms = flatten_major_terms(keyword_cfg)

    session = requests.Session()
    session.trust_env = args.use_env_proxy
    session.headers.update({"User-Agent": USER_AGENT})

    conn = open_db(Path(args.db))
    started_at = now_iso()

    inserted = 0
    updated = 0
    scanned = 0
    accepted = 0
    skipped_non_wechat = 0
    rejected_unreachable = 0
    errors: List[Dict[str, str]] = []

    enabled_sources = [s for s in sources if s.get("enabled", True)]

    for source in enabled_sources:
        source_id = source["id"]
        url = source["url"]
        try:
            content = fetch_text(session, url, timeout=args.timeout)
            parser = source.get("parser", "rss")
            if parser == "html":
                candidates = parse_html(source, content, args.max_links_per_source)
            else:
                candidates = parse_rss(source, content, args.max_links_per_source)

            for candidate in candidates:
                scanned += 1

                if not is_wechat_article_link(candidate.link):
                    skipped_non_wechat += 1
                    continue

                score, _details = score_candidate(candidate, source, major_terms)
                if score <= 0:
                    continue

                if args.enable_link_verify:
                    ok, final_link, _, _ = verify_reachable_link(session, candidate.link, timeout=args.timeout)
                    if not ok:
                        rejected_unreachable += 1
                        continue
                    if final_link and is_wechat_article_link(final_link):
                        candidate.link = final_link

                accepted += 1
                if args.dry_run:
                    continue

                ts = now_iso()
                is_new = upsert_lead(conn, candidate, score, ts)
                if is_new:
                    inserted += 1
                else:
                    updated += 1

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000)
        except Exception as err:  # noqa: BLE001
            errors.append({"source": source_id, "url": url, "error": str(err)})

    if not args.dry_run:
        conn.commit()

    snapshots = export_snapshots(conn, latest_limit=args.latest_limit)
    latest_payload = {
        "generated_at": now_iso(),
        "total": len(snapshots["latest"]),
        "items": snapshots["latest"],
    }
    today_payload = {
        "generated_at": now_iso(),
        "total": len(snapshots["today"]),
        "items": snapshots["today"],
    }
    report_payload = {
        "started_at": started_at,
        "finished_at": now_iso(),
        "sources": len(sources),
        "enabled_sources": len(enabled_sources),
        "scanned": scanned,
        "accepted": accepted,
        "skipped_non_wechat": skipped_non_wechat,
        "rejected_unreachable": rejected_unreachable,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "dry_run": args.dry_run,
        "enable_link_verify": args.enable_link_verify,
    }

    dump_json(Path(args.latest_json), latest_payload)
    dump_json(Path(args.today_json), today_payload)
    dump_json(Path(args.report_json), report_payload)

    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    if args.strict and errors:
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect WeChat public-account job leads")
    parser.add_argument("--sources", default="collector/wechat_sources.json")
    parser.add_argument("--keywords", default="collector/keywords.json")
    parser.add_argument("--db", default="data/wechat_leads.db")
    parser.add_argument("--latest-json", default="data/wechat_leads_latest.json")
    parser.add_argument("--today-json", default="data/wechat_leads_today.json")
    parser.add_argument("--report-json", default="data/wechat_fetch_report.json")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-links-per-source", type=int, default=120)
    parser.add_argument("--latest-limit", type=int, default=200)
    parser.add_argument("--sleep-ms", type=int, default=300)
    parser.add_argument("--use-env-proxy", action="store_true")
    parser.add_argument("--enable-link-verify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return collect(args)


if __name__ == "__main__":
    sys.exit(main())
