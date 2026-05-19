import psycopg2
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import os
import math

load_dotenv()

try:
    CONN_STRING = st.secrets["DATABASE_URL"]
except:
    CONN_STRING = os.getenv("DATABASE_URL")

PI = math.pi


@st.cache_resource
def get_conn():
    return psycopg2.connect(CONN_STRING)

@st.cache_data(ttl=300)
def query(sql, params=None):
    conn = get_conn()
    # Reconnexion si la connexion est fermée
    if conn.closed:
        st.cache_resource.clear()
        conn = get_conn()
    try:
        return pd.read_sql(sql, conn, params=params)
    except Exception:
        # Forcer une nouvelle connexion en cas d'erreur
        st.cache_resource.clear()
        conn = get_conn()
        return pd.read_sql(sql, conn, params=params)

# ── Clients ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_clients():
    return query("SELECT id, nom, prenom, poids_kg FROM clients ORDER BY nom, prenom")

# ── Détection test ISO = séance avec exactement 3 séries ─────────────────────
@st.cache_data(ttl=300)
def get_seances_test(client_id):
    """Séances qui contiennent exactement 3 séries = test ISO."""
    return query("""
        SELECT s.id AS seance_id, s.date_seance, s.cote,
               COUNT(sr.id) AS nb_series
        FROM seances s
        JOIN series sr ON sr.seance_id = s.id
        WHERE s.client_id = %s
        GROUP BY s.id, s.date_seance, s.cote
        HAVING COUNT(sr.id) = 3
        ORDER BY s.date_seance, s.cote
    """, params=(client_id,))

@st.cache_data(ttl=300)
def get_seances_renfo(client_id):
    """Séances qui NE sont PAS des tests (nb séries != 3)."""
    return query("""
        SELECT s.id AS seance_id, s.date_seance, s.cote,
               COUNT(sr.id) AS nb_series
        FROM seances s
        JOIN series sr ON sr.seance_id = s.id
        WHERE s.client_id = %s
        GROUP BY s.id, s.date_seance, s.cote
        HAVING COUNT(sr.id) != 3
        ORDER BY s.date_seance, s.cote
    """, params=(client_id,))

# ── Stats test ISO par séance ─────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stats_test(seance_id, poids_kg=None):
    """Stats complètes pour une séance de test (3 séries)."""
    df = query("""
        SELECT
            sr.id AS serie_id,
            sr.serie,
            sr.vitesse_cible,
            sr.nb_reps_cible,
            m.rep,
            m.sens,
            MAX(m.couple)                                               AS couple_max,
            AVG(m.couple)                                               AS couple_moyen,
            MAX(m.position) - MIN(m.position)                          AS amplitude,
            MAX(m.temps) - MIN(m.temps)                                AS duree_sec,
            -- Travail = aire sous courbe couple/position (méthode trapèzes approchée)
            SUM(ABS(m.couple) * (ABS(m.vitesse) * %s / 180.0) * 0.01) AS travail_j
        FROM mesures m
        JOIN series sr ON m.serie_id = sr.id
        WHERE sr.seance_id = %s
          AND m.statut IN ('Actif', '1.0', '1')
          AND m.couple IS NOT NULL AND m.vitesse IS NOT NULL
        GROUP BY sr.id, sr.serie, sr.vitesse_cible, sr.nb_reps_cible, m.rep, m.sens
        ORDER BY sr.serie, m.rep, m.sens
    """, params=(PI, seance_id))

    if poids_kg and poids_kg > 0:
        df['couple_max_kg']  = df['couple_max']  / poids_kg
        df['travail_j_kg']   = df['travail_j']   / poids_kg

    return df

@st.cache_data(ttl=300)
def get_meilleure_rep(seance_id, poids_kg=None):
    """Meilleure répétition par série et sens (pic de couple max)."""
    df = query("""
        SELECT
            sr.serie,
            sr.vitesse_cible,
            m.sens,
            MAX(m.couple)                                               AS pic_couple,
            SUM(ABS(m.couple) * (ABS(m.vitesse) * %s / 180.0) * 0.01) AS travail_j
        FROM mesures m
        JOIN series sr ON m.serie_id = sr.id
        WHERE sr.seance_id = %s
          AND m.statut IN ('Actif', '1.0', '1')
          AND m.couple IS NOT NULL AND m.vitesse IS NOT NULL
        GROUP BY sr.serie, sr.vitesse_cible, m.sens
        ORDER BY sr.serie, m.sens
    """, params=(PI, seance_id))

    if poids_kg and poids_kg > 0:
        df['pic_couple_kg'] = df['pic_couple'] / poids_kg
        df['travail_j_kg']  = df['travail_j']  / poids_kg

    return df

@st.cache_data(ttl=300)
def get_courbe_serie(serie_id):
    return query("""
        SELECT temps, position, couple, vitesse, rep, sens, statut
        FROM mesures WHERE serie_id = %s ORDER BY temps
    """, params=(serie_id,))

@st.cache_data(ttl=300)
def get_series_seance(seance_id):
    return query("""
        SELECT sr.id, sr.serie, sr.vitesse_cible, sr.nb_reps_cible
        FROM series sr WHERE sr.seance_id = %s ORDER BY sr.serie
    """, params=(seance_id,))

# ── Evolution tests dans le temps ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_evolution_tests(client_id, cote):
    """Evolution des pics de couple test ISO par date."""
    return query("""
        SELECT
            s.date_seance,
            s.cote,
            sr.vitesse_cible,
            m.sens,
            MAX(m.couple) AS pic_couple
        FROM mesures m
        JOIN series sr ON m.serie_id = sr.id
        JOIN seances s ON sr.seance_id = s.id
        WHERE s.client_id = %s AND s.cote = %s
          AND m.statut IN ('Actif', '1.0', '1') AND m.couple IS NOT NULL
          AND s.id IN (
              SELECT seance_id FROM (
                  SELECT seance_id, COUNT(*) AS nb
                  FROM series GROUP BY seance_id HAVING COUNT(*) = 3
              ) t
          )
        GROUP BY s.date_seance, s.cote, sr.vitesse_cible, m.sens
        ORDER BY s.date_seance, sr.vitesse_cible, m.sens
    """, params=(client_id, cote))

# ── Renforcement ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_protocoles_renfo(client_id, cote):
    return query("""
        SELECT DISTINCT sr.vitesse_cible, sr.nb_reps_cible
        FROM series sr
        JOIN seances s ON sr.seance_id = s.id
        WHERE s.client_id = %s AND s.cote = %s
          AND s.id IN (
              SELECT seance_id FROM (
                  SELECT seance_id, COUNT(*) AS nb
                  FROM series GROUP BY seance_id HAVING COUNT(*) != 3
              ) t
          )
        ORDER BY sr.vitesse_cible, sr.nb_reps_cible
    """, params=(client_id, cote))

@st.cache_data(ttl=300)
def get_evolution_renfo(client_id, cote):
    """Toutes les séries de renfo (séances != 3 séries), par date et numéro de série."""
    return query("""
        SELECT
            s.date_seance,
            sr.serie,
            sr.vitesse_cible,
            sr.nb_reps_cible,
            MAX(m.couple)                                               AS couple_max,
            AVG(m.couple)                                               AS couple_moyen,
            SUM(ABS(m.couple) * (ABS(m.vitesse) * %s / 180.0) * 0.01) AS energie_j,
            MAX(m.temps) - MIN(m.temps)                                AS duree_sec
        FROM mesures m
        JOIN series sr ON m.serie_id = sr.id
        JOIN seances s ON sr.seance_id = s.id
        WHERE s.client_id = %s AND s.cote = %s
          AND m.statut IN ('Actif', '1.0', '1')
          AND m.couple IS NOT NULL AND m.vitesse IS NOT NULL
          AND s.id IN (
              SELECT seance_id FROM (
                  SELECT seance_id, COUNT(*) AS nb
                  FROM series GROUP BY seance_id HAVING COUNT(*) != 3
              ) t
          )
        GROUP BY s.date_seance, sr.serie, sr.vitesse_cible, sr.nb_reps_cible
        ORDER BY s.date_seance, sr.serie
    """, params=(PI, client_id, cote))

# ── Stats par répétition (analyse détaillée) ──────────────────────────────────
@st.cache_data(ttl=300)
def get_stats_reps(serie_id):
    return query("""
        SELECT
            rep, sens,
            MAX(couple)                                             AS couple_max,
            AVG(couple)                                             AS couple_moyen,
            MAX(position) - MIN(position)                          AS amplitude,
            MAX(temps) - MIN(temps)                                AS duree_sec,
            SUM(ABS(couple) * (ABS(vitesse) * %s / 180.0) * 0.01) AS energie_j
        FROM mesures
        WHERE serie_id = %s AND statut IN ('Actif', '1.0', '1')
          AND couple IS NOT NULL AND vitesse IS NOT NULL
        GROUP BY rep, sens ORDER BY rep, sens
    """, params=(PI, serie_id))

# ── Séances dispo (pour page analyse) ────────────────────────────────────────
@st.cache_data(ttl=300)
def get_seances_dispo(client_id, cote):
    return query("""
        SELECT s.id, s.date_seance,
               COUNT(sr.id) AS nb_series
        FROM seances s
        JOIN series sr ON sr.seance_id = s.id
        WHERE s.client_id = %s AND s.cote = %s
        GROUP BY s.id, s.date_seance
        ORDER BY s.date_seance DESC
    """, params=(client_id, cote))

# ── Patient summary ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_patient_summary(client_id):
    return query("""
        SELECT
            COUNT(DISTINCT s.id)                                        AS nb_seances,
            COUNT(DISTINCT CASE WHEN cnt.nb = 3 THEN s.id END)         AS nb_tests,
            COUNT(DISTINCT CASE WHEN cnt.nb != 3 THEN s.id END)        AS nb_renfo,
            MIN(s.date_seance)                                          AS premiere_seance,
            MAX(s.date_seance)                                          AS derniere_seance
        FROM seances s
        JOIN (
            SELECT seance_id, COUNT(*) AS nb FROM series GROUP BY seance_id
        ) cnt ON cnt.seance_id = s.id
        WHERE s.client_id = %s
    """, params=(client_id,))
