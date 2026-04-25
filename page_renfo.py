import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math
from styles import *
from db import get_evolution_renfo, get_series_seance, get_courbe_serie, get_stats_reps, query

PI = math.pi

def get_recap_seance(seance_id, poids_kg):
    return query("""
        SELECT
            sr.serie,
            sr.vitesse_cible,
            sr.nb_reps_cible,
            MAX(m.couple)                                               AS couple_max,
            AVG(m.couple)                                               AS couple_moyen,
            SUM(ABS(m.couple) * (ABS(m.vitesse) * %s / 180.0) * 0.01) AS energie_j,
            MAX(m.temps) - MIN(m.temps)                                AS duree_sec,
            COUNT(DISTINCT m.rep)                                       AS nb_reps
        FROM mesures m
        JOIN series sr ON m.serie_id = sr.id
        WHERE sr.seance_id = %s AND m.statut = 'Actif'
          AND m.couple IS NOT NULL AND m.vitesse IS NOT NULL
        GROUP BY sr.serie, sr.vitesse_cible, sr.nb_reps_cible
        ORDER BY sr.serie
    """, params=(PI, seance_id))

def get_seances_renfo_list(client_id, cote):
    return query("""
        SELECT s.id AS seance_id, s.date_seance, COUNT(sr.id) AS nb_series
        FROM seances s JOIN series sr ON sr.seance_id = s.id
        WHERE s.client_id = %s AND s.cote = %s
        GROUP BY s.id, s.date_seance
        HAVING COUNT(sr.id) != 3
        ORDER BY s.date_seance DESC
    """, params=(client_id, cote))

def show(client_id, client_nom, cote, poids_kg):
    cote_label = "Droit" if cote == "Right" else "Gauche"
    st.markdown(f"""<div class="page-header">
        <h1>💪 Renforcement Isocinétique</h1>
        <p>{client_nom} · Genou {cote_label}</p>
    </div>""", unsafe_allow_html=True)

    seances_renfo = get_seances_renfo_list(client_id, cote)
    if seances_renfo.empty:
        st.info("Aucune séance de renforcement trouvée.")
        return

    seances_renfo['date_seance'] = pd.to_datetime(seances_renfo['date_seance'])

    # Chargement de toutes les données renfo
    df_all = get_evolution_renfo(client_id, cote)
    if df_all.empty:
        st.info("Pas de données disponibles.")
        return
    df_all['date_seance'] = pd.to_datetime(df_all['date_seance'])

    series_uniques = sorted(df_all['serie'].unique())

    # ── Sélection séances et séries ───────────────────────────────────────────
    section("⚙️ Filtres")
    col_f1, col_f2 = st.columns([2, 2])

    with col_f1:
        dates_dispo = sorted(df_all['date_seance'].unique())
        dates_sel = st.multiselect(
            "Séances à comparer",
            options=dates_dispo,
            default=dates_dispo,
            format_func=lambda d: pd.Timestamp(d).strftime('%d/%m/%Y')
        )

    with col_f2:
        # Label avec protocole pour chaque série
        def serie_label_opt(s):
            row = df_all[df_all['serie'] == s].iloc[0]
            return f"Série {s} — {int(row['vitesse_cible'])}°/s × {int(row['nb_reps_cible'])} reps"

        series_sel = st.multiselect(
            "Séries à afficher",
            options=series_uniques,
            default=series_uniques,
            format_func=serie_label_opt
        )

    if not dates_sel or not series_sel:
        st.info("Sélectionne au moins une séance et une série.")
        return

    df_filt = df_all[
        (df_all['date_seance'].isin(dates_sel)) &
        (df_all['serie'].isin(series_sel))
    ]

    # ── KPIs globaux ──────────────────────────────────────────────────────────
    df_global = df_filt.groupby('date_seance').agg(
        couple_max=('couple_max','max'),
        energie_j=('energie_j','sum')
    ).reset_index().sort_values('date_seance')

    if len(df_global) >= 1:
        d = df_global.iloc[-1]
        p = df_global.iloc[0]
        st.markdown(f"""<div class="kpi-row">
            {kpi("Couple max (dernière séance)", f"{d['couple_max']:.1f}", "Nm",
                 delta_html(d['couple_max'], p['couple_max']), C_ORANGE)}
            {kpi("Énergie totale (dernière)", f"{d['energie_j']:.0f}", "J",
                 f'{delta_html(d["energie_j"], p["energie_j"])} · <span class="neu">{d["energie_j"]/poids_kg:.1f} J/kg</span>' if poids_kg else delta_html(d['energie_j'], p['energie_j']), C_GREEN)}
            {kpi("Record couple", f"{df_global['couple_max'].max():.1f}", "Nm",
                 f'<span class="up">⭐ {df_global.loc[df_global["couple_max"].idxmax(), "date_seance"].strftime("%d/%m/%Y")}</span>', C_BLUE)}
            {kpi("Séances", f"{len(df_global)}", "",
                 f'<span class="neu">{p["date_seance"].strftime("%d/%m")} → {d["date_seance"].strftime("%d/%m/%Y")}</span>', C_PURPLE)}
        </div>""", unsafe_allow_html=True)

    # ── Évolution globale par séance ─────────────────────────────────────────
    section("📈 Évolution globale par séance")
    col_g1, col_g2 = st.columns(2)
    import numpy as np

    with col_g1:
        fig_g1 = go.Figure()
        fig_g1.add_trace(go.Scatter(
            x=df_global['date_seance'], y=df_global['energie_j'].round(0),
            mode='lines+markers', name='Énergie totale',
            line=dict(color=C_GREEN, width=2.5),
            marker=dict(size=9, color=C_GREEN, line=dict(color='white', width=2)),
            fill='tozeroy', fillcolor='rgba(0,200,150,0.07)',
            hovertemplate='<b>%{x|%d/%m/%Y}</b><br>%{y:.0f} J<extra></extra>'
        ))
        if len(df_global) > 2:
            x_num = (df_global['date_seance'] - df_global['date_seance'].min()).dt.days.values
            z = np.polyfit(x_num, df_global['energie_j'].values, 1)
            fig_g1.add_trace(go.Scatter(
                x=df_global['date_seance'], y=np.poly1d(z)(x_num),
                mode='lines', name='Tendance',
                line=dict(color=C_PURPLE, width=1.5, dash='dot'), hoverinfo='skip'
            ))
        lg1 = base_layout(title="Énergie totale par séance (J)")
        lg1['yaxis']['title'] = 'Énergie (J)'; lg1['xaxis']['tickformat'] = '%d/%m/%Y'
        fig_g1.update_layout(**lg1); st.plotly_chart(fig_g1, use_container_width=True)

    with col_g2:
        fig_g2 = go.Figure()
        fig_g2.add_trace(go.Scatter(
            x=df_global['date_seance'], y=df_global['couple_max'].round(1),
            mode='lines+markers', name='Couple max',
            line=dict(color=C_ORANGE, width=2.5),
            marker=dict(size=9, color=C_ORANGE, line=dict(color='white', width=2)),
            fill='tozeroy', fillcolor='rgba(255,107,53,0.07)',
            hovertemplate='<b>%{x|%d/%m/%Y}</b><br>%{y:.1f} Nm<extra></extra>'
        ))
        idx_max = df_global['couple_max'].idxmax()
        fig_g2.add_trace(go.Scatter(
            x=[df_global.loc[idx_max,'date_seance']],
            y=[df_global.loc[idx_max,'couple_max']],
            mode='markers', name='Record',
            marker=dict(color=C_YELLOW, size=14, symbol='star', line=dict(color='white', width=2)),
            hovertemplate=f'<b>⭐ Record</b><br>{df_global.loc[idx_max,"date_seance"].strftime("%d/%m/%Y")}<br>%{{y:.1f}} Nm<extra></extra>'
        ))
        lg2 = base_layout(title="Couple max par séance (Nm)")
        lg2['yaxis']['title'] = 'Couple max (Nm)'; lg2['xaxis']['tickformat'] = '%d/%m/%Y'
        fig_g2.update_layout(**lg2); st.plotly_chart(fig_g2, use_container_width=True)

    # ── Graphique Power BI : axe X = série, une ligne par séance ─────────────
    section("📊 Série par série — une ligne par séance")
    col1, col2 = st.columns(2)

    with col1:
        fig1 = go.Figure()
        for i, date in enumerate(sorted(dates_sel)):
            sub = df_filt[df_filt['date_seance'] == date].sort_values('serie')
            if sub.empty: continue
            label = pd.Timestamp(date).strftime('%d/%m/%Y')
            # Texte personnalisé avec protocole au hover
            custom = [f"Série {int(r['serie'])} — {int(r['vitesse_cible'])}°/s × {int(r['nb_reps_cible'])} reps"
                      for _, r in sub.iterrows()]
            fig1.add_trace(go.Scatter(
                x=sub['serie'], y=sub['couple_max'].round(1),
                mode='lines+markers', name=label,
                line=dict(color=COLORS[i % len(COLORS)], width=2),
                marker=dict(size=8, line=dict(color='white', width=1.5)),
                customdata=custom,
                hovertemplate=f'<b>{label}</b><br>%{{customdata}}<br>Couple max : %{{y:.1f}} Nm<extra></extra>'
            ))
        l1 = base_layout(title="Couple max par série")
        l1['xaxis']['title'] = 'Numéro de série'
        l1['xaxis']['tickmode'] = 'linear'
        l1['yaxis']['title'] = 'Couple max (Nm)'
        fig1.update_layout(**l1)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = go.Figure()
        for i, date in enumerate(sorted(dates_sel)):
            sub = df_filt[df_filt['date_seance'] == date].sort_values('serie')
            if sub.empty: continue
            label = pd.Timestamp(date).strftime('%d/%m/%Y')
            custom = [f"Série {int(r['serie'])} — {int(r['vitesse_cible'])}°/s × {int(r['nb_reps_cible'])} reps"
                      for _, r in sub.iterrows()]
            fig2.add_trace(go.Scatter(
                x=sub['serie'], y=sub['energie_j'].round(0),
                mode='lines+markers', name=label,
                line=dict(color=COLORS[i % len(COLORS)], width=2),
                marker=dict(size=8, line=dict(color='white', width=1.5)),
                customdata=custom,
                hovertemplate=f'<b>{label}</b><br>%{{customdata}}<br>Énergie : %{{y:.0f}} J<extra></extra>'
            ))
        l2 = base_layout(title="Énergie par série (J)")
        l2['xaxis']['title'] = 'Numéro de série'
        l2['xaxis']['tickmode'] = 'linear'
        l2['yaxis']['title'] = 'Énergie (J)'
        fig2.update_layout(**l2)
        st.plotly_chart(fig2, use_container_width=True)

    st.caption("Chaque ligne = une séance · Axe X = numéro de série · Survoler pour voir le protocole")

    # ── Évolution dans le temps par série ─────────────────────────────────────
    section("📈 Évolution dans le temps — série par série")
    col3, col4 = st.columns(2)

    with col3:
        fig3 = go.Figure()
        for i, s in enumerate(series_sel):
            sub = df_filt[df_filt['serie'] == s].sort_values('date_seance')
            if sub.empty: continue
            row0 = sub.iloc[0]
            label = f"Série {s} — {int(row0['vitesse_cible'])}°/s × {int(row0['nb_reps_cible'])} reps"
            fig3.add_trace(go.Scatter(
                x=sub['date_seance'], y=sub['couple_max'].round(1),
                mode='lines+markers', name=label,
                line=dict(color=COLORS[i % len(COLORS)], width=2),
                marker=dict(size=8, line=dict(color='white', width=1.5)),
                hovertemplate=f'<b>{label}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:.1f}} Nm<extra></extra>'
            ))
        l3 = base_layout(title="Évolution couple max par série dans le temps")
        l3['xaxis']['title'] = 'Date'
        l3['xaxis']['tickformat'] = '%d/%m/%Y'
        l3['yaxis']['title'] = 'Couple max (Nm)'
        fig3.update_layout(**l3)
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        fig4 = go.Figure()
        for i, s in enumerate(series_sel):
            sub = df_filt[df_filt['serie'] == s].sort_values('date_seance')
            if sub.empty: continue
            row0 = sub.iloc[0]
            label = f"Série {s} — {int(row0['vitesse_cible'])}°/s × {int(row0['nb_reps_cible'])} reps"
            fig4.add_trace(go.Scatter(
                x=sub['date_seance'], y=sub['energie_j'].round(0),
                mode='lines+markers', name=label,
                line=dict(color=COLORS[i % len(COLORS)], width=2),
                marker=dict(size=8, line=dict(color='white', width=1.5)),
                hovertemplate=f'<b>{label}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:.0f}} J<extra></extra>'
            ))
        l4 = base_layout(title="Évolution énergie par série dans le temps (J)")
        l4['xaxis']['title'] = 'Date'
        l4['xaxis']['tickformat'] = '%d/%m/%Y'
        l4['yaxis']['title'] = 'Énergie (J)'
        fig4.update_layout(**l4)
        st.plotly_chart(fig4, use_container_width=True)

    # ── Tableau comparatif ────────────────────────────────────────────────────
    section("📋 Tableau comparatif")
    pivot = df_filt.copy()
    pivot['serie_label'] = pivot.apply(
        lambda r: f"S{int(r['serie'])} {int(r['vitesse_cible'])}°/s×{int(r['nb_reps_cible'])}reps", axis=1
    )
    pivot_table = pivot.pivot_table(
        index='date_seance', columns='serie_label',
        values=['couple_max','energie_j'], aggfunc='first'
    ).round(1)
    pivot_table.index = pd.to_datetime(pivot_table.index).strftime('%d/%m/%Y')
    st.dataframe(pivot_table, use_container_width=True)
