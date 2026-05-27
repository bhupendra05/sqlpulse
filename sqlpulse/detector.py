"""Core N+1 detection logic."""
from __future__ import annotations
import re, time, threading, functools
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

_local = threading.local()

@dataclass
class QueryRecord:
    sql: str
    normalized: str
    duration_ms: float
    stack: str

@dataclass 
class PulseReport:
    total_queries: int = 0
    total_ms: float = 0.0
    n_plus_one: list[dict] = field(default_factory=list)
    slow_queries: list[dict] = field(default_factory=list)
    all_queries: list[QueryRecord] = field(default_factory=list)

    def __str__(self):
        lines = [f"sqlpulse: {self.total_queries} queries in {self.total_ms:.1f}ms"]
        if self.n_plus_one:
            lines.append(f"  ⚠ N+1 detected ({len(self.n_plus_one)} pattern(s)):")
            for n in self.n_plus_one:
                lines.append(f"    • '{n['pattern']}' ran {n['count']}x")
        if self.slow_queries:
            lines.append(f"  🐢 Slow queries ({len(self.slow_queries)}):")
            for q in self.slow_queries:
                lines.append(f"    • {q['duration_ms']:.0f}ms: {q['sql'][:80]}")
        if not self.n_plus_one and not self.slow_queries:
            lines.append("  ✓ No issues detected")
        return "\n".join(lines)

def _normalize(sql: str) -> str:
    """Strip literals to get query shape."""
    sql = re.sub(r"'[^']*'", "?", sql)
    sql = re.sub(r"\b\d+\b", "?", sql)
    sql = re.sub(r"\s+", " ", sql).strip().upper()
    return sql

def _record_query(sql: str, duration_ms: float):
    if not hasattr(_local, "active") or not _local.active:
        return
    import traceback
    rec = QueryRecord(
        sql=sql, 
        normalized=_normalize(sql),
        duration_ms=duration_ms,
        stack="".join(traceback.format_stack()[:-2])
    )
    _local.queries.append(rec)

def _build_report(queries: list[QueryRecord], slow_threshold_ms: float) -> PulseReport:
    report = PulseReport(
        total_queries=len(queries),
        total_ms=sum(q.duration_ms for q in queries),
        all_queries=queries,
    )
    # N+1: same normalized query appears > n_threshold times
    counts: dict[str, list] = defaultdict(list)
    for q in queries:
        counts[q.normalized].append(q)
    for norm, qs in counts.items():
        if len(qs) >= 3:
            report.n_plus_one.append({"pattern": norm[:80], "count": len(qs), "queries": qs})
    # Slow queries
    for q in queries:
        if q.duration_ms >= slow_threshold_ms:
            report.slow_queries.append({"sql": q.sql, "duration_ms": q.duration_ms})
    return report

@contextmanager
def sqlpulse(slow_ms: float = 100.0, raise_on_n_plus_one: bool = False, print_report: bool = True):
    """
    Context manager that detects N+1 SQL patterns and slow queries.

    Usage::

        from sqlpulse import sqlpulse

        with sqlpulse() as report:
            users = db.execute("SELECT * FROM users").fetchall()
            for user in users:
                db.execute(f"SELECT * FROM posts WHERE user_id = {user.id}")

        # → sqlpulse: 101 queries in 340ms
        #   ⚠ N+1 detected: 'SELECT * FROM POSTS WHERE USER_ID = ?' ran 100x
    """
    _local.active = True
    _local.queries = []
    try:
        yield None  # report filled in after
    finally:
        queries = list(_local.queries)
        _local.active = False
        _local.queries = []

    report = _build_report(queries, slow_ms)
    # Patch yield value — return by modifying the var
    _sqlpulse_last_report._report = report
    if print_report:
        print(report)
    if raise_on_n_plus_one and report.n_plus_one:
        raise RuntimeError(f"N+1 detected: {report.n_plus_one[0]['pattern']} ran {report.n_plus_one[0]['count']}x")

class _LastReport:
    _report: PulseReport | None = None
_sqlpulse_last_report = _LastReport()

def get_last_report() -> PulseReport | None:
    return _sqlpulse_last_report._report

# ── Monkey-patching hooks ───────────────────────────────────────────────────

def patch_sqlite3():
    """Patch sqlite3.Cursor to auto-record queries."""
    import sqlite3
    _orig_execute = sqlite3.Cursor.execute
    def _patched(self, sql, params=()):
        t = time.perf_counter()
        result = _orig_execute(self, sql, params)
        _record_query(sql, (time.perf_counter() - t) * 1000)
        return result
    sqlite3.Cursor.execute = _patched

def patch_sqlalchemy():
    """Patch SQLAlchemy engine to auto-record queries."""
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        @event.listens_for(Engine, "before_cursor_execute")
        def _before(conn, cursor, statement, params, context, executemany):
            context._sqlpulse_start = time.perf_counter()
        @event.listens_for(Engine, "after_cursor_execute")
        def _after(conn, cursor, statement, params, context, executemany):
            ms = (time.perf_counter() - context._sqlpulse_start) * 1000
            _record_query(statement, ms)
    except ImportError:
        pass

class SQLPulseMiddleware:
    """ASGI/WSGI middleware — wraps every request in a sqlpulse context."""
    def __init__(self, app, slow_ms: float = 100.0, log_fn=None):
        self.app = app
        self.slow_ms = slow_ms
        self.log_fn = log_fn or print

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with sqlpulse(slow_ms=self.slow_ms, print_report=False):
            await self.app(scope, receive, send)
        r = get_last_report()
        if r and (r.n_plus_one or r.slow_queries):
            self.log_fn(str(r))
