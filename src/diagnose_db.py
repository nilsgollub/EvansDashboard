import sqlite3


def main():
    db_path = "../switzerland_roads.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    print("=== Database Diagnostics ===")

    # 1. Search for all Route de Marly segments
    c.execute(
        "SELECT name, maxspeed, highway, min_lat, min_lon, max_lat, max_lon FROM road_segments WHERE name = 'Route de Marly' LIMIT 10"
    )
    rows = c.fetchall()
    print(f"\nRoute de Marly Segmente in DB (Gefunden: {len(rows)}):")
    for row in rows:
        print(
            f"  Speed: {row[1]}, Typ: {row[2]}, Koordinaten: ({row[3]:.4f}, {row[4]:.4f}) bis ({row[5]:.4f}, {row[6]:.4f})"
        )

    conn.close()


if __name__ == "__main__":
    main()
