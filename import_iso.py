import os
import pandas as pd
import psycopg2
import psycopg2.extras

from dotenv import load_dotenv

load_dotenv()
CONN_STRING = os.getenv("DATABASE_URL")
DOSSIER     = os.getenv("DOSSIER_ISO")

# ── Statut machine → texte ────────────────────────────────────────────────────
STATUT_MAP = {
    '1': 'Actif',   '1.0': 'Actif',
    '5': 'Deceleration', '5.0': 'Deceleration',
    '9': 'Changement',   '9.0': 'Changement',
    'D': 'Direction',
    '11': 'Fin',    '11.0': 'Fin',   '15': 'Fin',  '15.0': 'Fin',
    '0': 'Termine', '0.0': 'Termine',
}

def convert_statut(raw):
    s = str(raw).strip()
    if s in STATUT_MAP:
        return STATUT_MAP[s]
    try:
        s2 = str(int(float(s)))
        if s2 in STATUT_MAP:
            return STATUT_MAP[s2]
    except:
        pass
    return s

# ── Helpers ───────────────────────────────────────────────────────────────────
def find_col(df, keyword):
    for c in df.columns:
        if keyword.lower() in c.lower():
            return c
    return None

def clean_float(val):
    try:    return float(val)
    except: return None

def parse_filename(filename):
    """
    'BART_ François 03_03_2026 19_39_43 30 10 Right 2.CSV'
    parts = ['BART_', 'François', '03_03_2026', '19_39_43', '30', '10', 'Right', '2']
              [0]       [1]          [2]           [3]        [4]  [5]    [6]     [7]
    """
    clean = filename.replace('.CSV', '').replace('.csv', '')
    parts = clean.split(' ')

    nom    = parts[0].replace('_', '').capitalize()
    prenom = parts[1].capitalize()

    jour, mois, annee = parts[2].split('_')
    date_seance  = f"{annee}-{mois}-{jour}"

    h, m, s = parts[3].split('_')
    heure_seance = f"{h}:{m}:{s}"

    vitesse_cible = int(parts[4])
    nb_reps_cible = int(parts[5])
    cote          = parts[6]
    serie         = int(parts[7]) + 1  # commence à 0 dans le nom → on veut 1

    return nom, prenom, date_seance, heure_seance, vitesse_cible, nb_reps_cible, cote, serie

# ── Main ───────────────────────────────────────────────────────────────────────
conn = psycopg2.connect(CONN_STRING)
cur  = conn.cursor()

print("=== Import isocinétique → NeonDB ===\n")

fichiers = sorted([
    f for f in os.listdir(DOSSIER)
    if f.endswith('.CSV') or f.endswith('.csv')
])
print(f"{len(fichiers)} fichiers trouvés.\n")

for filename in fichiers:
    print(f"📄 {filename}")

    try:
        nom, prenom, date_seance, heure_seance, vitesse_cible, nb_reps_cible, cote, serie = parse_filename(filename)
    except Exception as e:
        print(f"   ⚠️  Nom non parseable : {e}\n")
        continue

    # ── 1. Client ──────────────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO clients (nom, prenom)
        VALUES (%s, %s)
        ON CONFLICT ON CONSTRAINT uq_client DO NOTHING
        RETURNING id
    """, (nom, prenom))
    row = cur.fetchone()
    if row:
        client_id = row[0]
    else:
        cur.execute("SELECT id FROM clients WHERE nom=%s AND prenom=%s", (nom, prenom))
        client_id = cur.fetchone()[0]

    # ── 2. Séance ──────────────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO seances (client_id, date_seance, heure_seance, cote)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT uq_seance DO NOTHING
        RETURNING id
    """, (client_id, date_seance, heure_seance, cote))
    row = cur.fetchone()
    if row:
        seance_id = row[0]
    else:
        cur.execute("""
            SELECT id FROM seances
            WHERE client_id=%s AND date_seance=%s
              AND heure_seance=%s AND cote=%s
        """, (client_id, date_seance, heure_seance, cote))
        seance_id = cur.fetchone()[0]

    # ── 3. Série ───────────────────────────────────────────────────────────
    cur.execute("""
        INSERT INTO series (seance_id, serie, vitesse_cible, nb_reps_cible, nom_fichier)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT uq_serie DO NOTHING
        RETURNING id
    """, (seance_id, serie, vitesse_cible, nb_reps_cible, filename))
    row = cur.fetchone()
    if row:
        serie_id = row[0]
    else:
        print(f"   ⏭️  Série déjà importée, fichier ignoré.\n")
        continue

    # ── 4. Mesures ─────────────────────────────────────────────────────────
    filepath = os.path.join(DOSSIER, filename)
    df = pd.read_csv(filepath, encoding='utf-8', encoding_errors='replace')

    cols = {
        'statut': find_col(df, 'Statut'),
        'temps':  find_col(df, 'Temps'),
        'pos':    find_col(df, 'Position'),
        'couple': find_col(df, 'Couple'),
        'vit':    find_col(df, 'Vitesse') or find_col(df, 'Velocity'),
        'end':    find_col(df, 'End Pnt'),
        'ps':     find_col(df, 'Pos Start'),
        'pe':     find_col(df, 'Pos End'),
        'ts_':    find_col(df, 'Trq Start'),
        'pts':    find_col(df, 'Peak Trq Start'),
        'pte':    find_col(df, 'Peak Trq End'),
        'hpt':    find_col(df, 'Half Peak Trq'),
        'stim':   find_col(df, 'Stim'),
        'rs':     find_col(df, 'Reaction Start'),
        'tf':     find_col(df, 'Target Found'),
        'te':     find_col(df, 'Target End'),
    }

    df = df.dropna(subset=[cols['end']])

    lignes = []
    for _, row in df.iterrows():
        end_pnt = int(float(row[cols['end']]))
        rep     = (end_pnt // 2) + 1
        sens = 'Retour' if end_pnt % 2 == 1 else 'Extension'
        statut  = convert_statut(row[cols['statut']])

        lignes.append((
            serie_id, rep, sens, statut,
            clean_float(row[cols['temps']]),
            clean_float(row[cols['pos']]),
            clean_float(row[cols['couple']]),
            clean_float(row[cols['vit']]),
            float(end_pnt),
            clean_float(row[cols['ps']]),
            clean_float(row[cols['pe']]),
            clean_float(row[cols['ts_']]),
            clean_float(row[cols['pts']]),
            clean_float(row[cols['pte']]),
            clean_float(row[cols['hpt']]),
            clean_float(row[cols['stim']]),
            clean_float(row[cols['rs']]),
            clean_float(row[cols['tf']]),
            clean_float(row[cols['te']]),
        ))

    psycopg2.extras.execute_values(cur, """
        INSERT INTO mesures (
            serie_id, rep, sens, statut,
            temps, position, couple, vitesse, end_pnt_0,
            pos_start, pos_end, trq_start, peak_trq_start, peak_trq_end,
            half_peak_trq, stim, reaction_start, target_found, target_end
        ) VALUES %s
        ON CONFLICT ON CONSTRAINT uq_mesure DO NOTHING
    """, lignes, page_size=10000)

    conn.commit()
    print(f"   ✅ {len(lignes):,} mesures insérées "
          f"(client={nom} {prenom}, seance_id={seance_id}, serie={serie})\n")

cur.close()
conn.close()
print("=== Import terminé ✅ ===")
