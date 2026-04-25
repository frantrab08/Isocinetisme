import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
    SELECT sens, MAX(couple) as couple_max, AVG(position) as pos_moy
    FROM mesures
    WHERE serie_id = 41 AND statut IN ('Actif','1.0','1')
    GROUP BY sens
""")
for r in cur.fetchall():
    print(f"sens={r[0]} | couple_max={r[1]:.1f} | position_moyenne={r[2]:.1f}°")

cur.close()
conn.close()
