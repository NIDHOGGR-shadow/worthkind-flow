"""Read-only SQLite cutover inventory. No user data is printed or modified."""
import argparse
import json
from pathlib import Path
import sqlite3

SYNTHETIC = ("demo-hotel","demo-hotel-two")

def inventory(path):
    source=Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError("SQLite source does not exist")
    with sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=5) as conn:
        conn.execute("BEGIN")
        if conn.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise ValueError("SQLite integrity check failed")
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if "properties" not in tables:
            raise ValueError("Not a Flow database")
        counts={}
        for table in tables:
            quoted='"'+table.replace('"','""')+'"'
            total=conn.execute("SELECT count(*) FROM "+quoted).fetchone()[0]
            counts[table]=total
        real=conn.execute("SELECT count(*) FROM properties WHERE slug NOT IN (?,?)",SYNTHETIC).fetchone()[0]
        # A synthetic property slug is not proof that its cases are synthetic.
        # Any operational rows must be reviewed rather than silently discarded.
        allowed={"properties","public_facts"}
        operational=sum(count for name,count in counts.items() if name not in allowed)
        facts=0
        if "public_facts" in tables:
            facts=conn.execute("SELECT count(*) FROM public_facts WHERE source IS NULL OR source <> 'synthetic_demo_fixture'").fetchone()[0]
        ready=real==0 and operational==0 and facts==0
        return {"table_counts":counts,"non_fixture_properties":real,"operational_rows":operational,"non_fixture_facts":facts,"empty_cutover_eligible":ready}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source")
    args=p.parse_args()
    try:
        report=inventory(args.source)
    except (OSError,sqlite3.Error,ValueError):
        print(json.dumps({"error":"Source unavailable or invalid"}))
        return 2
    print(json.dumps(report,indent=2))
    return 0 if report["empty_cutover_eligible"] else 1

if __name__=="__main__":
    raise SystemExit(main())
