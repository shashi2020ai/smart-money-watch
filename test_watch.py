import sys; sys.path.insert(0, ".")
from datetime import date
import watch

def test_window():
    cases = {date(2026,10,25): False, date(2026,10,30): True, date(2026,11,16): True, date(2026,11,17): False,
             date(2026,12,1): False, date(2027,2,1): True}
    for d, exp in cases.items():
        assert watch.in_window(d) == exp, d

def test_schedule():
    assert watch.should_run(date(2026,10,26))            # Monday outside the window: weekly check
    assert not watch.should_run(date(2026,10,27))        # Tuesday outside the window: skip
    assert watch.should_run(date(2026,10,27), force=True)
    assert watch.should_run(date(2026,11,3))             # Tuesday inside the window: daily

def test_build_status():
    def fake(cik, since, ua):
        return {"0000000001": [{"cik": cik, "accession": "A1", "form": "13F-HR", "filed": "2026-08-14", "period": "2026-06-30"}],
                "0000000002": [{"cik": cik, "accession": "B1", "form": "13F-NT", "filed": "2026-08-14", "period": "2026-06-30"}],
                "0000000003": [{"cik": cik, "accession": "C1", "form": "13F-HR", "filed": "2026-08-14", "period": "2026-06-30"}]}.get(cik, [])
    mg = [{"id": "X", "name": "X Mgr", "cik": "0000000001", "alias_ciks": [], "active": True},
          {"id": "Y", "name": "Y Mgr", "cik": "0000000002", "alias_ciks": ["0000000003"], "active": True},
          {"id": "Z", "name": "Z Mgr", "cik": "0000000004", "alias_ciks": [], "active": True},
          {"id": "W", "name": "W off", "cik": "0000000005", "alias_ciks": [], "active": False}]
    s = watch.build_status(mg, date(2026,10,25), "ua", fake)
    q = [x for x in s["quarters"] if x["period"] == "2026-06-30"][0]
    assert (q["received"], q["total"], q["missing"]) == (2, 3, ["Z Mgr"]), q     # NT alone does not count; alias HR does
    assert s["quarters"][0]["period"] == "2026-09-30" and s["quarters"][0]["received"] == 0

def test_hash_ignores_timestamps():
    a = {"managers": {"X": 1}, "quarters": [1], "checked_at": "t1"}
    b = {"managers": {"X": 1}, "quarters": [1], "checked_at": "t2"}
    assert watch.stable_hash(a) == watch.stable_hash(b)
    assert watch.stable_hash(a) != watch.stable_hash({"managers": {"X": 2}, "quarters": [1]})

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("  PASS ", n)
