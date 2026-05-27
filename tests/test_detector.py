import time
from sqlpulse import sqlpulse, get_last_report

def test_manual_query_recording():
    """Test that queries recorded manually are detected as N+1."""
    from sqlpulse.detector import _record_query, _local
    _local.active = True
    _local.queries = []
    
    # Simulate N+1: same query shape 5 times
    for i in range(5):
        _record_query(f"SELECT * FROM posts WHERE user_id = {i}", 2.0)
    
    from sqlpulse.detector import _build_report
    queries = list(_local.queries)
    _local.active = False
    _local.queries = []
    
    report = _build_report(queries, slow_threshold_ms=100.0)
    assert report.total_queries == 5
    assert len(report.n_plus_one) >= 1

def test_slow_query_flagged():
    from sqlpulse.detector import _record_query, _local, _build_report
    _local.active = True
    _local.queries = []
    _record_query("SELECT * FROM big_table", 250.0)
    queries = list(_local.queries)
    _local.active = False
    _local.queries = []
    report = _build_report(queries, slow_threshold_ms=100.0)
    assert len(report.slow_queries) == 1

def test_no_n_plus_one_single_query():
    from sqlpulse.detector import _record_query, _local, _build_report
    _local.active = True
    _local.queries = []
    _record_query("SELECT * FROM users", 5.0)
    queries = list(_local.queries)
    _local.active = False
    _local.queries = []
    report = _build_report(queries, slow_threshold_ms=100.0)
    assert report.n_plus_one == []
