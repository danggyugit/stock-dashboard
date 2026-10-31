"""S&P 500 / 400 / 600 membership history from Wikipedia.

Backtests need to know which names were in each index on a past date;
using today's constituents back-fills winners that were added after their
run and drops everything that was removed (survivorship bias).

Sources, per index:
  1. The "Selected changes" table on the Wikipedia constituents page
     (date, added ticker, removed ticker). The S&P 400 and 600 pages still
     carry it; the S&P 500 page dropped it in mid-2026, so for that index
     the table is taken from the last page revision that still had it.
  2. For the period after that table ends, monthly revision snapshots of
     the constituents table are diffed to synthesize add/remove rows
     (month precision — the backtests rebalance monthly anyway), and the
     live page is diffed against the last stored snapshot on every run.

Output per index (in the backtest_data cache dir):
  <idx>_changes.pkl.gz     DataFrame[date, added_ticker, removed_ticker]
  membership/<idx>_*       parser state (stored table, snapshot, synthetic rows)

Nothing here ever overwrites a good file with an empty one: on any fetch
or parse failure the previously saved history is returned unchanged.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import pickle
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
_HEADERS = {"User-Agent": "Mozilla/5.0 (aiquantlab research; github.com/danggyugit/stock-dashboard)"}

INDEXES: dict[str, dict] = {
    "sp500": {"title": "List of S&P 500 companies", "cap_tier": "Large Cap"},
    "sp400": {"title": "List of S&P 400 companies", "cap_tier": "Mid Cap"},
    "sp600": {"title": "List of S&P 600 companies", "cap_tier": "Small Cap"},
}
TIER_TO_INDEX = {v["cap_tier"]: k for k, v in INDEXES.items()}

# How far back to look for a revision that still has the changes table.
_MAX_LOOKBACK_MONTHS = 36
_EMPTY = pd.DataFrame(columns=["date", "added_ticker", "removed_ticker"])


# ── Wikipedia access ───────────────────────────────────────────────


def _get(url: str, params: dict | None = None) -> requests.Response:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=30)
            r.raise_for_status()
            return r
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unreachable")


def _page_tables(title: str, revid: int | None = None) -> list[pd.DataFrame]:
    url = "https://en.wikipedia.org/w/index.php"
    params = {"title": title.replace(" ", "_")}
    if revid:
        params["oldid"] = str(revid)
    html = _get(url, params).text
    return pd.read_html(io.StringIO(html))


def _revision_at(title: str, when: datetime) -> tuple[int, datetime] | None:
    """Latest revision at or before `when` → (revid, timestamp)."""
    r = _get(WIKI_API, {
        "action": "query", "prop": "revisions", "titles": title, "rvlimit": 1,
        "rvstart": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "rvdir": "older",
        "rvprop": "ids|timestamp", "format": "json",
    }).json()
    page = next(iter(r["query"]["pages"].values()))
    revs = page.get("revisions") or []
    if not revs:
        return None
    ts = datetime.strptime(revs[0]["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
    return int(revs[0]["revid"]), ts


# ── Parsing ─────────────────────────────────────────────────────────


def normalize_ticker(t) -> str:
    """Wikipedia 'BRK.B' → yfinance 'BRK-B'; drops footnote markers."""
    if t is None or (isinstance(t, float) and t != t):
        return ""
    s = str(t).strip().upper()
    if not s or s == "NAN":
        return ""
    if "[" in s:
        s = s.split("[", 1)[0].strip()
    return s.replace(".", "-")


def _flat_cols(df: pd.DataFrame) -> list[str]:
    if isinstance(df.columns, pd.MultiIndex):
        return [" ".join(str(c) for c in col if str(c) != "nan").strip().lower() for col in df.columns]
    return [str(c).strip().lower() for c in df.columns]


def parse_changes_table(tables: list[pd.DataFrame]) -> pd.DataFrame | None:
    """The add/remove table, or None if the page has none."""
    for raw in tables:
        cols = _flat_cols(raw)
        added = next((i for i, c in enumerate(cols) if c.startswith("added") and "ticker" in c), None)
        removed = next((i for i, c in enumerate(cols) if c.startswith("removed") and "ticker" in c), None)
        date_i = next((i for i, c in enumerate(cols) if "date" in c), None)
        if added is None or removed is None or date_i is None:
            continue
        rows = []
        for _, r in raw.iterrows():
            d = pd.to_datetime(r.iloc[date_i], format="mixed", errors="coerce")
            if pd.isna(d):
                continue
            a, rm = normalize_ticker(r.iloc[added]), normalize_ticker(r.iloc[removed])
            if not a and not rm:
                continue
            rows.append({"date": d.normalize(), "added_ticker": a, "removed_ticker": rm})
        return pd.DataFrame(rows, columns=_EMPTY.columns).sort_values("date").reset_index(drop=True)
    return None


def parse_constituents(tables: list[pd.DataFrame]) -> set[str] | None:
    for raw in tables:
        cols = _flat_cols(raw)
        sym = next((i for i, c in enumerate(cols) if c in ("symbol", "ticker", "ticker symbol")), None)
        if sym is None or len(raw) < 100:
            continue
        return {normalize_ticker(v) for v in raw.iloc[:, sym] if normalize_ticker(v)}
    return None


def _snapshot_diff(prev: set[str], cur: set[str], when: pd.Timestamp) -> list[dict]:
    rows = [{"date": when, "added_ticker": t, "removed_ticker": ""} for t in sorted(cur - prev)]
    rows += [{"date": when, "added_ticker": "", "removed_ticker": t} for t in sorted(prev - cur)]
    return rows


# ── State files ─────────────────────────────────────────────────────


def _pkl_load(path: Path):
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning("Could not read %s: %s", path.name, e)
        return None


def _pkl_save(obj, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def _json_load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _json_save(obj: dict, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ── Public API ──────────────────────────────────────────────────────


def load_index_changes(idx: str, cache_dir: Path) -> pd.DataFrame:
    """Previously saved history for `idx` (empty frame if none)."""
    df = _pkl_load(cache_dir / f"{idx}_changes.pkl.gz")
    return df if isinstance(df, pd.DataFrame) else _EMPTY.copy()


def update_index_changes(idx: str, cache_dir: Path) -> pd.DataFrame:
    """Refresh and save the membership history for one index.

    Returns the combined history (table rows + synthesized snapshot rows).
    Falls back to the saved history when Wikipedia can't be read.
    """
    info = INDEXES[idx]
    title = info["title"]
    state_dir = cache_dir / "membership"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{idx}_state.json"
    state = _json_load(state_path)
    previous = load_index_changes(idx, cache_dir)
    today = pd.Timestamp(date.today())

    try:
        tables = _page_tables(title)
        table = parse_changes_table(tables)
        members_now = parse_constituents(tables)
        if members_now is None:
            raise RuntimeError("constituents table not found on live page")

        # 1. Changes table: live page if it still has one, else the stored
        #    copy from the last revision that did (found once, then kept).
        if table is not None and not table.empty:
            table_as_of = today
            _pkl_save(table, state_dir / f"{idx}_table.pkl.gz")
            state["table_as_of"] = today.date().isoformat()
            state["table_source"] = "live"
        else:
            table = _pkl_load(state_dir / f"{idx}_table.pkl.gz")
            if table is None:
                table, table_as_of = _recover_table_from_history(title)
                _pkl_save(table, state_dir / f"{idx}_table.pkl.gz")
                state["table_as_of"] = table_as_of.date().isoformat()
                state["table_source"] = "revision"
                logger.info("%s: changes table recovered from revision as of %s (%d rows)",
                            idx, table_as_of.date(), len(table))
            table_as_of = pd.Timestamp(state["table_as_of"])

        # 2. Snapshot diffs cover the stretch after the table ends.
        synthetic = _pkl_load(state_dir / f"{idx}_synthetic.pkl.gz")
        synthetic = synthetic if isinstance(synthetic, pd.DataFrame) else _EMPTY.copy()
        if state.get("table_source") == "live":
            # Table is current — no gap to fill; drop stale synthetic rows.
            synthetic = _EMPTY.copy()
            state["snapshot_as_of"] = today.date().isoformat()
            state["snapshot_members"] = sorted(members_now)
        else:
            if "snapshot_members" not in state:
                rows, last_members, last_ts = _bootstrap_snapshots(title, table_as_of)
                synthetic = pd.DataFrame(rows, columns=_EMPTY.columns)
                state["snapshot_as_of"] = last_ts.date().isoformat()
                state["snapshot_members"] = sorted(last_members)
            prev_members = set(state["snapshot_members"])
            if prev_members != members_now:
                rows = _snapshot_diff(prev_members, members_now, today)
                synthetic = pd.concat([synthetic, pd.DataFrame(rows, columns=_EMPTY.columns)],
                                      ignore_index=True)
                logger.info("%s: %d membership change(s) since %s", idx, len(rows),
                            state.get("snapshot_as_of"))
            state["snapshot_as_of"] = today.date().isoformat()
            state["snapshot_members"] = sorted(members_now)
        _pkl_save(synthetic, state_dir / f"{idx}_synthetic.pkl.gz")

        combined = (pd.concat([table, synthetic], ignore_index=True)
                    .drop_duplicates()
                    .sort_values("date")
                    .reset_index(drop=True))
        if combined.empty:
            raise RuntimeError("combined history is empty")
        _pkl_save(combined, cache_dir / f"{idx}_changes.pkl.gz")
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["rows"] = int(len(combined))
        _json_save(state, state_path)
        logger.info("%s: %d change rows, %s → %s", idx, len(combined),
                    combined["date"].min().date(), combined["date"].max().date())
        return combined
    except Exception as e:
        logger.warning("%s: membership refresh failed (%s) — keeping %d saved rows",
                       idx, e, len(previous))
        return previous


def _recover_table_from_history(title: str) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Walk back month by month to the last revision that had the table."""
    when = datetime.now(timezone.utc).replace(tzinfo=None)
    for _ in range(_MAX_LOOKBACK_MONTHS):
        rev = _revision_at(title, when)
        if rev is None:
            break
        revid, ts = rev
        table = parse_changes_table(_page_tables(title, revid))
        if table is not None and not table.empty:
            return table, pd.Timestamp(ts).normalize()
        when = (pd.Timestamp(ts) - pd.DateOffset(months=1)).to_pydatetime()
        time.sleep(0.5)
    raise RuntimeError(f"no revision with a changes table within {_MAX_LOOKBACK_MONTHS} months")


def _bootstrap_snapshots(title: str, since: pd.Timestamp) -> tuple[list[dict], set[str], pd.Timestamp]:
    """Monthly constituent snapshots from `since` to now, diffed in sequence."""
    rows: list[dict] = []
    prev: set[str] | None = None
    prev_ts = since
    when = since
    now = pd.Timestamp(date.today())
    while when <= now:
        rev = _revision_at(title, when.to_pydatetime().replace(hour=23, minute=59))
        if rev is not None:
            revid, ts = rev
            members = parse_constituents(_page_tables(title, revid))
            if members:
                if prev is not None:
                    rows += _snapshot_diff(prev, members, pd.Timestamp(ts).normalize())
                prev, prev_ts = members, pd.Timestamp(ts).normalize()
            time.sleep(0.5)
        when = when + pd.DateOffset(months=1)
    if prev is None:
        raise RuntimeError("no constituent snapshots could be read")
    return rows, prev, prev_ts


def reconstruct_members(current: list[str] | set[str], changes: pd.DataFrame,
                        target_date: pd.Timestamp) -> set[str]:
    """Membership on `target_date`: start from today's list and undo every
    change that happened after that date (newest first)."""
    members = set(current)
    if changes is None or changes.empty:
        return members
    future = changes[changes["date"] > target_date].sort_values("date", ascending=False)
    for _, row in future.iterrows():
        if row["added_ticker"]:
            members.discard(row["added_ticker"])
        if row["removed_ticker"]:
            members.add(row["removed_ticker"])
    return members


def removed_since(changes: pd.DataFrame, since: pd.Timestamp) -> list[str]:
    if changes is None or changes.empty:
        return []
    sub = changes[(changes["date"] >= since) & (changes["removed_ticker"] != "")]
    return sorted(set(sub["removed_ticker"]))
