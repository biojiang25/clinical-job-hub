#!/usr/bin/env python3
"""Daily job collector for clinical lab and pharmacy graduate positions.

Features:
- Multi-source HTML/RSS crawling with retry
- Keyword-based relevance scoring
- Idempotent upsert into SQLite
- Daily/latest JSON export for frontend consumption
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
from urllib.parse import urljoin, urlparse

import requests
from lxml import etree
from lxml import html as lxml_html


DEFAULT_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36 JobCollector/1.0"
)


@dataclass
class JobCandidate:
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


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_date(text: str) -> Optional[str]:
    if not text:
        return None

    normalized = text.strip()

    # 2026-03-04 / 2026/03/04 / 2026.03.04
    m = re.search(r"(20\d{2})[-/.年]\s*(\d{1,2})[-/.月]\s*(\d{1,2})", normalized)
    if m:
        year, month, day = m.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return None


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


def looks_like_direct_job_link(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    path = (parsed.path or "/").lower().rstrip("/")
    query = parsed.query.lower()
    segments = [seg for seg in path.split("/") if seg]

    if not segments:
        return False

    generic_single = {
        "index",
        "home",
        "search",
        "jobs",
        "job",
        "work",
        "career",
        "careers",
        "list",
        "channel",
        "zhaopin",
    }
    if len(segments) == 1 and segments[0] in generic_single and not query:
        return False

    detail_pattern = bool(
        re.search(r"\d{4,}|\.s?html?$|\.aspx?$|/detail/|/article/|/view/|/notice/|/content/|/recruit/", path)
        or re.search(r"(?:^|&)(?:id|aid|articleid|noticeid|jobid|recruitid)=", query)
    )
    return detail_pattern


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


def fetch_text(session: requests.Session, url: str, timeout: int, retries: int = 2) -> str:
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as err:  # noqa: BLE001
            last_err = err
            time.sleep(1)
    raise RuntimeError(f"fetch failed: {url}, error={last_err}")


def parse_rss(source: Dict[str, Any], content: str, max_links: int) -> List[JobCandidate]:
    out: List[JobCandidate] = []
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

        full_link = urljoin(source["url"], link)
        if not looks_like_direct_job_link(full_link):
            continue

        out.append(
            JobCandidate(
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


def parse_html(source: Dict[str, Any], content: str, max_links: int) -> List[JobCandidate]:
    out: List[JobCandidate] = []
    tree = lxml_html.fromstring(content)
    anchors = tree.xpath("//a[@href]")
    must_contain = source.get("link_must_contain", [])

    for a in anchors[: max_links * 3]:
        href = normalize_text(a.get("href", ""))
        if not href or href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        full_link = urljoin(source["url"], href)
        if must_contain and not any(token in full_link for token in must_contain):
            continue
        if not looks_like_direct_job_link(full_link):
            continue

        title = normalize_text("".join(a.xpath(".//text()")))
        if len(title) < 6:
            continue

        context_node = a.xpath("ancestor::li[1] | ancestor::tr[1] | ancestor::article[1] | ancestor::div[1]")
        context_text = normalize_text(" ".join(context_node[0].xpath(".//text()"))) if context_node else title
        publish_date = extract_date(f"{title} {context_text}")

        out.append(
            JobCandidate(
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


def score_candidate(candidate: JobCandidate, source: Dict[str, Any], keyword_cfg: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    text = normalize_text(f"{candidate.title} {candidate.snippet}").lower()

    exclude_hits = [k for k in keyword_cfg.get("exclude_keywords", []) if k.lower() in text]
    if exclude_hits:
        return 0, {"exclude_hits": exclude_hits}

    # Doctoral-only postings are excluded in the current phase.
    exclude_degree_hits = [k for k in keyword_cfg.get("exclude_degree_keywords", []) if k.lower() in text]
    degree_include_hits = [k for k in keyword_cfg.get("degree_keywords", []) if k.lower() in text]
    has_doctoral_signal = bool(exclude_degree_hits)
    has_bachelor_or_master_signal = bool(degree_include_hits)
    if has_doctoral_signal and not has_bachelor_or_master_signal:
        return 0, {
            "exclude_degree_hits": exclude_degree_hits,
            "degree_include_hits": degree_include_hits,
        }

    major_hits: List[str] = []
    for major, tokens in keyword_cfg.get("major_keywords", {}).items():
        if any(token.lower() in text for token in tokens):
            major_hits.append(major)

    degree_hit = has_bachelor_or_master_signal
    institution_hits = [
        token
        for token in keyword_cfg.get("institution_keywords", [])
        if token.lower() in text
    ]
    source_include_hits = [
        token
        for token in source.get("include_any", [])
        if token.lower() in text
    ]

    score = 0
    if major_hits:
        score += 2
    if degree_hit:
        score += 1
    if institution_hits:
        score += 1
    if source_include_hits:
        score += 1

    # Keep only signals that match graduate-relevant openings.
    accepted = bool(major_hits) and (bool(institution_hits) or bool(source_include_hits)) and score >= 3

    if not accepted:
        return 0, {
            "major_hits": major_hits,
            "degree_hit": degree_hit,
            "exclude_degree_hits": exclude_degree_hits,
            "institution_hits": institution_hits,
            "source_include_hits": source_include_hits,
        }

    return score, {
        "major_hits": major_hits,
        "degree_hit": degree_hit,
        "exclude_degree_hits": exclude_degree_hits,
        "institution_hits": institution_hits,
        "source_include_hits": source_include_hits,
    }


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS postings (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_category TEXT,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            snippet TEXT,
            publish_date TEXT,
            major_tags TEXT,
            institution_tags TEXT,
            degree_match INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_postings_seen ON postings(last_seen_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_postings_pub ON postings(publish_date)")
    conn.commit()
    return conn


def make_id(source_id: str, title: str, link: str) -> str:
    text = f"{source_id}|{normalize_text(title)}|{normalize_text(link)}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def upsert_posting(conn: sqlite3.Connection, candidate: JobCandidate, details: Dict[str, Any], score: int, ts: str) -> bool:
    pid = make_id(candidate.source_id, candidate.title, candidate.link)

    row = conn.execute("SELECT id FROM postings WHERE id = ?", (pid,)).fetchone()
    if row:
        conn.execute(
            """
            UPDATE postings
            SET snippet = ?, publish_date = COALESCE(?, publish_date),
                major_tags = ?, institution_tags = ?, degree_match = ?, score = ?, last_seen_at = ?
            WHERE id = ?
            """,
            (
                candidate.snippet,
                candidate.publish_date,
                json.dumps(details.get("major_hits", []), ensure_ascii=False),
                json.dumps(details.get("institution_hits", []), ensure_ascii=False),
                1 if details.get("degree_hit") else 0,
                score,
                ts,
                pid,
            ),
        )
        return False

    conn.execute(
        """
        INSERT INTO postings (
            id, source_id, source_name, source_category, title, link, snippet,
            publish_date, major_tags, institution_tags, degree_match, score,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid,
            candidate.source_id,
            candidate.source_name,
            candidate.source_category,
            candidate.title,
            candidate.link,
            candidate.snippet,
            candidate.publish_date,
            json.dumps(details.get("major_hits", []), ensure_ascii=False),
            json.dumps(details.get("institution_hits", []), ensure_ascii=False),
            1 if details.get("degree_hit") else 0,
            score,
            ts,
            ts,
        ),
    )
    return True


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def export_snapshots(conn: sqlite3.Connection, latest_limit: int) -> Dict[str, Any]:
    latest_rows = conn.execute(
        """
        SELECT title, link, source_name, source_category, publish_date, first_seen_at,
               last_seen_at, major_tags, institution_tags, degree_match, score, snippet
        FROM postings
        ORDER BY COALESCE(publish_date, substr(first_seen_at, 1, 10)) DESC, last_seen_at DESC
        LIMIT ?
        """,
        (latest_limit,),
    ).fetchall()

    today = datetime.now().date().isoformat()
    today_rows = conn.execute(
        """
        SELECT title, link, source_name, source_category, publish_date, first_seen_at,
               last_seen_at, major_tags, institution_tags, degree_match, score, snippet
        FROM postings
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
        "major_tags",
        "institution_tags",
        "degree_match",
        "score",
        "snippet",
    ]

    def to_dict(rows: Iterable[Tuple[Any, ...]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            obj = dict(zip(cols, row))
            obj["major_tags"] = json.loads(obj["major_tags"] or "[]")
            obj["institution_tags"] = json.loads(obj["institution_tags"] or "[]")
            out.append(obj)
        return out

    return {
        "latest": to_dict(latest_rows),
        "today": to_dict(today_rows),
    }


def collect(args: argparse.Namespace) -> int:
    sources = load_json(Path(args.sources))
    keyword_cfg = load_json(Path(args.keywords))

    session = requests.Session()
    # Default behavior avoids broken local proxy settings.
    session.trust_env = args.use_env_proxy
    session.headers.update({"User-Agent": USER_AGENT})

    conn = open_db(Path(args.db))
    started_at = now_iso()
    inserted = 0
    updated = 0
    scanned = 0
    accepted = 0
    rejected_non_direct = 0
    rejected_unreachable = 0
    errors: List[Dict[str, str]] = []

    for source in sources:
        source_id = source["id"]
        url = source["url"]

        try:
            content = fetch_text(session, url, timeout=args.timeout)

            if source.get("parser") == "rss":
                candidates = parse_rss(source, content, args.max_links_per_source)
            else:
                candidates = parse_html(source, content, args.max_links_per_source)

            for candidate in candidates:
                scanned += 1
                score, details = score_candidate(candidate, source, keyword_cfg)
                if score <= 0:
                    continue

                if not looks_like_direct_job_link(candidate.link):
                    rejected_non_direct += 1
                    continue

                if not args.disable_link_verify:
                    ok, final_link, _, reason = verify_reachable_link(session, candidate.link, timeout=args.timeout)
                    if not ok:
                        rejected_unreachable += 1
                        continue
                    if final_link and looks_like_direct_job_link(final_link):
                        candidate.link = final_link

                accepted += 1
                ts = now_iso()

                if args.dry_run:
                    continue

                is_new = upsert_posting(conn, candidate, details, score, ts)
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
        "scanned": scanned,
        "accepted": accepted,
        "rejected_non_direct": rejected_non_direct,
        "rejected_unreachable": rejected_unreachable,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "dry_run": args.dry_run,
    }

    dump_json(Path(args.latest_json), latest_payload)
    dump_json(Path(args.today_json), today_payload)
    dump_json(Path(args.report_json), report_payload)

    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect daily latest job postings for medical graduates")
    parser.add_argument("--sources", default="collector/sources.json")
    parser.add_argument("--keywords", default="collector/keywords.json")
    parser.add_argument("--db", default="data/jobs.db")
    parser.add_argument("--latest-json", default="data/jobs_latest.json")
    parser.add_argument("--today-json", default="data/jobs_today.json")
    parser.add_argument("--report-json", default="data/fetch_report.json")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-links-per-source", type=int, default=240)
    parser.add_argument("--latest-limit", type=int, default=500)
    parser.add_argument("--sleep-ms", type=int, default=300)
    parser.add_argument("--use-env-proxy", action="store_true")
    parser.add_argument("--disable-link-verify", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return collect(args)


if __name__ == "__main__":
    sys.exit(main())
