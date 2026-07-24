#!/usr/bin/env python3
"""Rebuild a local SQLite DB from all hourly mat-details JSON snapshots.

The snapshots in data/mat-details/*.json are the source of truth (committed
to git). This script is safe to re-run at any time - it always rebuilds
gt.db from scratch off whatever snapshots currently exist on disk.
"""
import json
import re
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "mat-details"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gt.db"

SNAPSHOT_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)\.json$")

SCHEMA = """
CREATE TABLE snapshots (
    snapshot_time TEXT PRIMARY KEY
);

CREATE TABLE materials (
    mat_id INTEGER PRIMARY KEY,
    mat_name TEXT
);

CREATE TABLE material_snapshot (
    snapshot_time TEXT,
    mat_id INTEGER,
    current_price INTEGER,
    avg_price INTEGER,
    total_qty_available INTEGER,
    avg_qty_sold_daily INTEGER,
    PRIMARY KEY (snapshot_time, mat_id)
);

CREATE TABLE orders (
    snapshot_time TEXT,
    mat_id INTEGER,
    order_id INTEGER,
    c_id INTEGER,
    c_name TEXT,
    unit_price INTEGER,
    qty INTEGER,
    PRIMARY KEY (snapshot_time, order_id)
);

CREATE TABLE price_history (
    mat_id INTEGER,
    date TEXT,
    avg_price INTEGER,
    qty_sold INTEGER,
    qty_remaining INTEGER,
    qty_c INTEGER,
    PRIMARY KEY (mat_id, date)
);

CREATE INDEX idx_orders_cname ON orders (c_name);
CREATE INDEX idx_orders_matid ON orders (mat_id);
"""


def snapshot_time_from_filename(path: Path) -> str | None:
    m = SNAPSHOT_FILENAME_RE.match(path.name)
    if not m:
        return None
    raw = m.group(1)  # 2026-07-24T20-50-29Z
    date_part, time_part = raw[:10], raw[11:]
    h, mi, s = time_part[:-1].split("-")
    return f"{date_part}T{h}:{mi}:{s}Z"


def main() -> int:
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        print(f"No snapshot files found in {DATA_DIR}")
        return 1

    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    for path in files:
        snapshot_time = snapshot_time_from_filename(path)
        if snapshot_time is None:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR IGNORE INTO snapshots (snapshot_time) VALUES (?)",
            (snapshot_time,),
        )
        for mat in data.get("materials", []):
            mat_id = mat["matId"]
            conn.execute(
                "INSERT OR IGNORE INTO materials (mat_id, mat_name) VALUES (?, ?)",
                (mat_id, mat.get("matName")),
            )
            conn.execute(
                """INSERT OR REPLACE INTO material_snapshot
                   (snapshot_time, mat_id, current_price, avg_price,
                    total_qty_available, avg_qty_sold_daily)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_time,
                    mat_id,
                    mat.get("currentPrice"),
                    mat.get("avgPrice"),
                    mat.get("totalQtyAvailable"),
                    mat.get("avgQtySoldDaily"),
                ),
            )
            for order in mat.get("orders", []):
                conn.execute(
                    """INSERT OR REPLACE INTO orders
                       (snapshot_time, mat_id, order_id, c_id, c_name, unit_price, qty)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        snapshot_time,
                        mat_id,
                        order.get("id"),
                        order.get("cId"),
                        order.get("cName"),
                        order.get("unitPrice"),
                        order.get("qty"),
                    ),
                )
            for ph in mat.get("priceHistory", []):
                conn.execute(
                    """INSERT OR REPLACE INTO price_history
                       (mat_id, date, avg_price, qty_sold, qty_remaining, qty_c)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        mat_id,
                        ph.get("date"),
                        ph.get("avgPrice"),
                        ph.get("qtySold"),
                        ph.get("qtyRemaining"),
                        ph.get("qtyC"),
                    ),
                )

    conn.commit()
    n_snapshots = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    n_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    print(f"Built {DB_PATH} from {n_snapshots} snapshots ({n_orders} order rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
