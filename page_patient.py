import streamlit as st
import pandas as pd
from styles import *
from db import get_patient_summary, query

def get_seances_detail(client_id):
    return query("""
        SELECT
            s.date_seance,
            s.cote,
            COUNT(sr.id) AS nb_series,
            CASE WHEN COUNT(sr.id) = 3 THEN 'Test ISO' ELSE 'Renforcement' END AS type_seance
        FROM seances s
        JOIN series sr ON sr.seance_id = s.id
        WHERE s.client_id = %s
        GROUP BY s.id, s.date_seance, s.cote
        ORDER BY s.date_seance DESC, s.cote
    """, params=(client_id,))

def show(client_id, client_nom, cote, poids_kg):
    st.markdown(f"""<div class="page-header">
        <h1>👤 Fiche Patient</h1>
        <p>{client_nom} · Résumé du protocole de rééducation</p>
    </div>""", unsafe_allow_html=True)

    summary = get_patient_summary(client_id)
    seances = get_seances_detail(client_id)

    if summary.empty:
        st.info("Aucune donnée trouvée.")
        return

    s = summary.iloc[0]
    nb_seances  = int(s['nb_seances'])  if s['nb_seances']  else 0
    nb_tests    = int(s['nb_tests'])    if s['nb_tests']    else 0
    nb_renfo    = int(s['nb_renfo'])    if s['nb_renfo']    else 0
    date_debut  = pd.Timestamp(s['premiere_seance']).strftime('%d/%m/%Y') if s['premiere_seance'] else '—'
    date_fin    = pd.Timestamp(s['derniere_seance']).strftime('%d/%m/%Y') if s['derniere_seance'] else '—'

    # KPIs
    st.markdown(f"""<div class="kpi-row">
        {kpi("Séances totales", f"{nb_seances}", "", f'<span class="neu">{date_debut} → {date_fin}</span>', C_BLUE)}
        {kpi("Tests ISO", f"{nb_tests}", "", "", C_GREEN)}
        {kpi("Renforcement", f"{nb_renfo}", "", "", C_ORANGE)}
        {kpi("Poids", f"{int(poids_kg) if poids_kg else '—'}", "kg", "", C_PURPLE)}
    </div>""", unsafe_allow_html=True)

    # Tableau séances
    section("📋 Historique des séances")

    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        filtre_type = st.multiselect(
            "Type de séance",
            options=["Test ISO", "Renforcement"],
            default=["Test ISO", "Renforcement"]
        )
    with col_f2:
        filtre_cote = st.multiselect(
            "Genou",
            options=["Right", "Left"],
            default=["Right", "Left"],
            format_func=lambda x: "Droit" if x == "Right" else "Gauche"
        )

    df_show = seances.copy()
    df_show = df_show[df_show['type_seance'].isin(filtre_type)]
    df_show = df_show[df_show['cote'].isin(filtre_cote)]

    df_show['date_seance'] = pd.to_datetime(df_show['date_seance']).dt.strftime('%d/%m/%Y')
    df_show['cote'] = df_show['cote'].map({'Right': 'Droit', 'Left': 'Gauche'})
    df_show = df_show.rename(columns={
        'date_seance': 'Date', 'cote': 'Genou',
        'nb_series': 'Nb séries', 'type_seance': 'Type'
    })

    st.dataframe(df_show, use_container_width=True, hide_index=True)
    st.caption(f"{len(df_show)} séances affichées")
