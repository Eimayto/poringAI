import os
import sys
import argparse
import csv
from datetime import datetime
from typing import List, Dict, Any, Set

import psycopg2
import psycopg2.extras

DDL = """
CREATE TABLE IF NOT EXISTS hubs (
    id          INTEGER PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    region      TEXT,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    geom_wkb    TEXT, -- keep as text; if PostGIS is available, you may later convert to geometry
    capacity    INTEGER NOT NULL DEFAULT 12,
    occupied    INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hubs_region ON hubs(region);
CREATE INDEX IF NOT EXISTS idx_hubs_active ON hubs(is_active);
"""

UPSERT_SQL = """
INSERT INTO hubs (id, code, name, region, lat, lng, geom_wkb, capacity, is_active, updated_at)
VALUES (%(id)s, %(code)s, %(name)s, %(region)s, %(lat)s, %(lng)s, %(geom_wkb)s, %(capacity)s, TRUE, NOW())
ON CONFLICT (id) DO UPDATE SET
    code      = EXCLUDED.code,
    name      = EXCLUDED.name,
    region    = EXCLUDED.region,
    lat       = EXCLUDED.lat,
    lng       = EXCLUDED.lng,
    geom_wkb  = EXCLUDED.geom_wkb,
    capacity  = EXCLUDED.capacity,
    is_active = TRUE,
    updated_at = NOW();
"""

DEACTIVATE_MISSING_SQL = """
UPDATE hubs
SET is_active = FALSE, updated_at = NOW()
WHERE id <> ALL(%s) AND is_active = TRUE;
"""

def parse_args():
    p = argparse.ArgumentParser(description="Seed/Sync hubs table from CSV.")
    p.add_argument("--csv", required=True, help="Path to CSV file (expects headers: hub_id, hub_code, hub_name, region, latitude, longitude, geom)")
    p.add_argument("--default-capacity", type=int, default=12, help="Default capacity to set for hubs (if capacity not present in CSV).")
    p.add_argument("--deactivate-missing", action="store_true", help="Mark hubs not present in CSV as inactive.")
    return p.parse_args()

def get_db_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL env var is not set.", file=sys.stderr)
        sys.exit(2)
    return psycopg2.connect(url)

def ensure_schema(cur):
    cur.execute(DDL)

def load_csv(path: str, default_capacity: int) -> List[Dict[str, Any]]:
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        required = ["hub_id", "hub_code", "hub_name", "region", "latitude", "longitude", "geom"]
        missing = [c for c in required if c not in reader.fieldnames]
        if missing:
            raise RuntimeError(f"CSV missing required columns: {missing}. Found: {reader.fieldnames}")
        for r in reader:
            rows.append({
                "id": int(r["hub_id"]),
                "code": r["hub_code"],
                "name": r["hub_name"],
                "region": r.get("region"),
                "lat": float(r["latitude"]) if r.get("latitude") not in (None, "",) else None,
                "lng": float(r["longitude"]) if r.get("longitude") not in (None, "",) else None,
                "geom_wkb": r.get("geom"),
                "capacity": default_capacity,
            })
    return rows

def upsert_hubs(cur, hubs: List[Dict[str, Any]]):
    psycopg2.extras.execute_batch(cur, UPSERT_SQL, hubs, page_size=200)

def deactivate_missing(cur, present_ids: List[int]):
    if not present_ids:
        return
    cur.execute(DEACTIVATE_MISSING_SQL, (present_ids,))

def main():
    args = parse_args()
    hubs = load_csv(args.csv, args.default_capacity)
    present_ids = [h["id"] for h in hubs]

    with get_db_conn() as conn:
        with conn.cursor() as cur:
            ensure_schema(cur)
            upsert_hubs(cur, hubs)
            if args.deactivate_missing:
                deactivate_missing(cur, present_ids)
        conn.commit()

    print(f"Upserted {len(hubs)} hubs from {args.csv}.")
    if args.deactivate_missing:
        print("Hubs not present in CSV were deactivated (is_active=false).")

if __name__ == "__main__":
    main()
