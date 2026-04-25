import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math
from styles import *
from db import get_seances_dispo, get_series_seance, get_courbe_serie, get_stats_reps, query

PI = math.pi
ACTIF = ("'Actif'", "'1.0'", "'1'")
ACTIF_SQL = "m.statut IN ('Actif', '1.0', '1')"

def get_recap_seance(seance_id, poids_kg):
    return query(f"""
        SELECT
            sr.serie,
            sr.vitesse_cible,
            sr.nb_reps_cible,
            MAX(m.couple)                                               AS couple_max,
            AVG(m.couple)                                               AS couple_moyen,
            SUM(ABS(m.couple) * (ABS(m.vitesse) * {PI} / 180.0) * 0.01) AS energie_j,
            MAX(m.temps) - MIN(m.temps)                                AS duree_sec,
            COUNT(DISTINCT m.rep)                                       AS nb_reps
        FROM mesures m
        JOIN series sr ON m.serie_id = sr.id
        WHERE sr.seance_id = %s
          AND {ACTIF_SQL}
          AND m.couple IS NOT NULL AND m.vitesse IS NOT NULL
        GROUP BY sr.serie, sr.vitesse_cible, sr.nb_reps_cible
        ORDER BY sr.serie
    """, params=(seance_id,))

def get_stats_reps_local(serie_id):
    return query(f"""
        SELECT
            rep, sens,
            MAX(couple)                                               AS couple_max,
            AVG(couple)                                               AS couple_moyen,
            MAX(position) - MIN(position)                            AS amplitude,
            MAX(temps) - MIN(temps)                                  AS duree_sec,
            SUM(ABS(couple) * (ABS(vitesse) * {PI} / 180.0) * 0.01) AS energie_j
        FROM mesures
        WHERE serie_id = %s
          AND statut IN ('Actif', '1.0', '1')
          AND couple IS NOT NULL AND vitesse IS NOT NULL
        GROUP BY rep, sens ORDER BY rep, sens
    """, params=(serie_id,))

def show(client_id, client_nom, cote, poids_kg):
    cote_label = "Droit" if cote == "Right" else "Gauche"
    st.markdown(f"""<div class="page-header">
        <h1>🔬 Analyse Détaillée</h1>
        <p>{client_nom} · Genou {cote_label} · Vue d'ensemble et zoom rep par rep</p>
    </div>""", unsafe_allow_html=True)

    seances = get_seances_dispo(client_id, cote)
    if seances.empty:
        st.info("Aucune séance disponible.")
        return

    # ── Sélection séance ──────────────────────────────────────────────────────
    section("📅 Sélection séance")
    seance_opts = {}
    for _, r in seances.iterrows():
        date_str = pd.Timestamp(r['date_seance']).strftime('%d/%m/%Y')
        nb = int(r['nb_series'])
        tag = "🧪 TEST" if nb == 3 else "💪 RENFO"
        seance_opts[f"{date_str} — {nb} séries  {tag}"] = r['id']

    col_s1, _ = st.columns([2, 2])
    with col_s1:
        seance_label = st.selectbox("Séance", list(seance_opts.keys()))
    seance_id = int(seance_opts[seance_label])

    # ── Vue d'ensemble séance ─────────────────────────────────────────────────
    section("📋 Vue d'ensemble de la séance")

    df_recap = get_recap_seance(seance_id, poids_kg)
    if not df_recap.empty:
        df_show = df_recap.copy()
        df_show['Protocole'] = df_show.apply(
            lambda r: f"{int(r['vitesse_cible'])}°/s — {int(r['nb_reps_cible'])} reps", axis=1)
        df_show = df_show[['serie','Protocole','couple_max','couple_moyen','energie_j','duree_sec','nb_reps']].copy()
        df_show = df_show.round(1).rename(columns={
            'serie': 'Série', 'couple_max': 'Couple max (Nm)',
            'couple_moyen': 'Couple moy (Nm)', 'energie_j': 'Énergie (J)',
            'duree_sec': 'Durée (s)', 'nb_reps': 'Reps actives'
        })
        st.dataframe(df_show, use_container_width=True, hide_index=True)

        tot_energie = df_recap['energie_j'].sum()
        max_couple  = df_recap['couple_max'].max()
        nb_series   = len(df_recap)
        st.markdown(f"""<div class="kpi-row">
            {kpi("Couple max séance", f"{max_couple:.1f}", "Nm", "", C_ORANGE)}
            {kpi("Énergie totale", f"{tot_energie:.0f}", "J",
                 f'<span class="neu">{tot_energie/poids_kg:.1f} J/kg</span>' if poids_kg else "", C_GREEN)}
            {kpi("Séries réalisées", f"{nb_series}", "", "", C_BLUE)}
        </div>""", unsafe_allow_html=True)

        # Graphique fatigue intra-séance
        col_fat1, col_fat2 = st.columns(2)
        with col_fat1:
            fig_fat = go.Figure()
            colors_bar = [COLORS[i % len(COLORS)] for i in range(len(df_recap))]
            fig_fat.add_trace(go.Bar(
                x=[f"S{int(r['serie'])} {int(r['vitesse_cible'])}°/s" for _, r in df_recap.iterrows()],
                y=df_recap['couple_max'].round(1),
                marker_color=colors_bar, opacity=0.85,
                hovertemplate='%{x}<br>%{y:.1f} Nm<extra></extra>'
            ))
            lf = base_layout(height=280, title="Couple max par série")
            lf['yaxis']['title'] = 'Couple max (Nm)'; lf['showlegend'] = False
            fig_fat.update_layout(**lf)
            st.plotly_chart(fig_fat, use_container_width=True)
        with col_fat2:
            fig_fat2 = go.Figure()
            fig_fat2.add_trace(go.Bar(
                x=[f"S{int(r['serie'])} {int(r['vitesse_cible'])}°/s" for _, r in df_recap.iterrows()],
                y=df_recap['energie_j'].round(0),
                marker_color=colors_bar, opacity=0.85,
                hovertemplate='%{x}<br>%{y:.0f} J<extra></extra>'
            ))
            lf2 = base_layout(height=280, title="Énergie par série (J)")
            lf2['yaxis']['title'] = 'Énergie (J)'; lf2['showlegend'] = False
            fig_fat2.update_layout(**lf2)
            st.plotly_chart(fig_fat2, use_container_width=True)
        st.caption("Une baisse au fil des séries indique une fatigue musculaire intra-séance.")

    # ── Sélection série ───────────────────────────────────────────────────────
    section("🔍 Zoom sur une série")

    series = get_series_seance(seance_id)
    col_sr, _ = st.columns([2, 2])
    with col_sr:
        def serie_label(r):
            nb = int(r['nb_reps_cible']); vit = int(r['vitesse_cible'])
            tag = "🧪" if nb <= 5 else "💪"
            return f"{tag} Série {int(r['serie'])} — {vit}°/s × {nb} reps"
        serie_opts = {serie_label(r): r['id'] for _, r in series.iterrows()}
        serie_sel  = st.selectbox("Série", list(serie_opts.keys()))
        serie_id   = int(serie_opts[serie_sel])

    df_courbe = get_courbe_serie(serie_id)
    df_reps   = get_stats_reps_local(serie_id)

    if df_courbe.empty:
        st.info("Pas de données pour cette série.")
        return

    # Filtre statut actif (texte ET nombre)
    df_actif = df_courbe[df_courbe['statut'].isin(['Actif','1.0','1'])]

    if df_actif.empty:
        st.info("Pas de données actives pour cette série.")
        return

    # KPIs série
    energie = (df_actif['couple'].abs() * (df_actif['vitesse'].abs() * PI / 180) * 0.01).sum()
    nb_reps = df_actif['rep'].nunique()
    duree   = df_courbe['temps'].max() - df_courbe['temps'].min()
    c_max   = df_actif['couple'].max()

    st.markdown(f"""<div class="kpi-row">
        {kpi("Couple max", f"{c_max:.1f}", "Nm",
             f'<span class="neu">{c_max/poids_kg:.2f} Nm/kg</span>' if poids_kg else "", C_ORANGE)}
        {kpi("Énergie", f"{energie:.0f}", "J",
             f'<span class="neu">{energie/poids_kg:.1f} J/kg</span>' if poids_kg else "", C_GREEN)}
        {kpi("Répétitions", f"{nb_reps}", "", "", C_BLUE)}
        {kpi("Durée série", f"{duree:.1f}", "s", "", C_PURPLE)}
    </div>""", unsafe_allow_html=True)

    # Filtres reps
    col_fa, col_fb = st.columns([1, 3])
    reps_dispo = sorted(df_actif['rep'].unique())
    with col_fa:
        st.markdown("**Filtres**")
        show_all = st.checkbox("Toutes les reps", value=True)
        reps_sel = reps_dispo if show_all else st.multiselect(
            "Reps", reps_dispo, default=reps_dispo, format_func=lambda x: f"Rep {x}")
        show_ext = st.checkbox("Extension (Quad)", value=True)
        show_ret = st.checkbox("Retour (IJ)", value=True)

    # ── Couple / Position ─────────────────────────────────────────────────────
    section("📈 Couple / Position")
    col_ext, col_ret = st.columns(2)

    PALETTE_REPS = ['#FF6B35','#0066FF','#00C896','#FF4757','#7B5EA7',
                     '#FFB800','#00BCD4','#E91E63','#4CAF50','#FF9800']

    # ── Reps individuelles ────────────────────────────────────────────────────
    with col_ext:
        fig_ext = go.Figure()
        if show_ext:
            df_e = df_actif[(df_actif['sens'] == 'Extension') & (df_actif['rep'].isin(reps_sel))]
            for i, rep_num in enumerate(sorted(df_e['rep'].unique())):
                sub = df_e[df_e['rep'] == rep_num]
                fig_ext.add_trace(go.Scatter(
                    x=sub['position'], y=sub['couple'],
                    mode='lines', name=f'Rep {rep_num}',
                    line=dict(color=PALETTE_REPS[i % len(PALETTE_REPS)], width=2),
                    hovertemplate=f'Rep {rep_num}<br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
                ))
        l_e = base_layout(height=320, title="Extension — Quadriceps · Reps individuelles")
        l_e['xaxis']['title'] = 'Position (°)'; l_e['yaxis']['title'] = 'Couple (Nm)'
        fig_ext.update_layout(**l_e)
        st.plotly_chart(fig_ext, use_container_width=True)

    with col_ret:
        fig_ret = go.Figure()
        if show_ret:
            df_r = df_actif[(df_actif['sens'] == 'Retour') & (df_actif['rep'].isin(reps_sel))]
            for i, rep_num in enumerate(sorted(df_r['rep'].unique())):
                sub = df_r[df_r['rep'] == rep_num]
                fig_ret.add_trace(go.Scatter(
                    x=sub['position'], y=sub['couple'],
                    mode='lines', name=f'Rep {rep_num}',
                    line=dict(color=PALETTE_REPS[i % len(PALETTE_REPS)], width=2),
                    hovertemplate=f'Rep {rep_num}<br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
                ))
        l_r = base_layout(height=320, title="Retour — Ischios-jambiers · Reps individuelles")
        l_r['xaxis']['title'] = 'Position (°)'; l_r['yaxis']['title'] = 'Couple (Nm)'
        fig_ret.update_layout(**l_r)
        st.plotly_chart(fig_ret, use_container_width=True)

    # ── Meilleure répétition ──────────────────────────────────────────────────
    section("⭐ Meilleure répétition — courbe clinique de référence")
    st.caption("La rep avec le couple max le plus élevé · Correspond à la courbe du rapport officiel")
    col_best_e, col_best_r = st.columns(2)

    for fig_col, sens_val, titre, color in [
        (col_best_e, 'Extension', 'Quadriceps', C_ORANGE),
        (col_best_r, 'Retour', 'Ischios-jambiers', C_BLUE)
    ]:
        fig_b = go.Figure()
        df_s = df_actif[(df_actif['sens'] == sens_val) & (df_actif['rep'].isin(reps_sel))]
        if not df_s.empty:
            best_rep = df_s.groupby('rep')['couple'].max().idxmax()
            sub_best = df_s[df_s['rep'] == best_rep].sort_values('position')
            fig_b.add_trace(go.Scatter(
                x=sub_best['position'], y=sub_best['couple'].round(1),
                mode='lines', name=f'Rep {best_rep} (meilleure)',
                line=dict(color=color, width=3),
                hovertemplate=f'Meilleure rep ({best_rep})<br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
            ))
        lb = base_layout(height=300, title=f"{sens_val} — {titre} · Meilleure rep")
        lb['xaxis']['title'] = 'Position (°)'; lb['yaxis']['title'] = 'Couple (Nm)'
        fig_b.update_layout(**lb)
        with fig_col:
            st.plotly_chart(fig_b, use_container_width=True)

    # ── Couple / Temps ────────────────────────────────────────────────────────
    section("⏱️ Couple / Temps")
    col_te, col_tr = st.columns(2)

    df_ext_t = df_actif[(df_actif['sens'] == 'Extension') & (df_actif['rep'].isin(reps_sel))]
    df_ret_t = df_actif[(df_actif['sens'] == 'Retour')    & (df_actif['rep'].isin(reps_sel))]

    with col_te:
        fig_te = go.Figure()
        for i, rep_num in enumerate(sorted(df_ext_t['rep'].unique())):
            sub = df_ext_t[df_ext_t['rep'] == rep_num]
            fig_te.add_trace(go.Scatter(
                x=sub['temps'], y=sub['couple'], mode='lines', name=f'Rep {rep_num}',
                line=dict(color=COLORS[i % len(COLORS)], width=2),
                hovertemplate=f'Rep {rep_num}<br>t=%{{x:.2f}}s  %{{y:.1f}} Nm<extra></extra>'
            ))
        l_te = base_layout(height=300, title="Extension / Temps (Quadriceps)")
        l_te['xaxis']['title'] = 'Temps (s)'; l_te['yaxis']['title'] = 'Couple (Nm)'
        fig_te.update_layout(**l_te); st.plotly_chart(fig_te, use_container_width=True)

    with col_tr:
        fig_tr = go.Figure()
        for i, rep_num in enumerate(sorted(df_ret_t['rep'].unique())):
            sub = df_ret_t[df_ret_t['rep'] == rep_num]
            fig_tr.add_trace(go.Scatter(
                x=sub['temps'], y=sub['couple'], mode='lines', name=f'Rep {rep_num}',
                line=dict(color=COLORS[i % len(COLORS)], width=2),
                hovertemplate=f'Rep {rep_num}<br>t=%{{x:.2f}}s  %{{y:.1f}} Nm<extra></extra>'
            ))
        l_tr = base_layout(height=300, title="Retour / Temps (Ischios-jambiers)")
        l_tr['xaxis']['title'] = 'Temps (s)'; l_tr['yaxis']['title'] = 'Couple (Nm)'
        fig_tr.update_layout(**l_tr); st.plotly_chart(fig_tr, use_container_width=True)

    # ── Stats par rep ─────────────────────────────────────────────────────────
    if not df_reps.empty:
        section("📋 Stats par répétition")
        col_r1, col_r2, col_r3 = st.columns(3)

        with col_r1:
            fig_d = go.Figure()
            for s, c in [('Extension', C_ORANGE), ('Retour', C_BLUE)]:
                sub = df_reps[df_reps['sens'] == s]
                if sub.empty: continue
                fig_d.add_trace(go.Bar(x=sub['rep'], y=sub['duree_sec'].round(2),
                    name=s, marker_color=c, opacity=0.85,
                    hovertemplate=f'{s} Rep %{{x}}<br>%{{y:.2f}} s<extra></extra>'))
            ld = base_layout(height=260, title="Durée par rep (s)")
            ld['barmode']='group'; ld['xaxis']['tickmode']='linear'; ld['yaxis']['title']='Durée (s)'
            fig_d.update_layout(**ld); st.plotly_chart(fig_d, use_container_width=True)

        with col_r2:
            fig_c = go.Figure()
            for s, c in [('Extension', C_ORANGE), ('Retour', C_BLUE)]:
                sub = df_reps[df_reps['sens'] == s]
                if sub.empty: continue
                fig_c.add_trace(go.Scatter(x=sub['rep'], y=sub['couple_max'].round(1),
                    name=s, mode='lines+markers', line=dict(color=c, width=2),
                    marker=dict(size=8, line=dict(color='white', width=1.5)),
                    hovertemplate=f'{s} Rep %{{x}}<br>%{{y:.1f}} Nm<extra></extra>'))
            lc = base_layout(height=260, title="Couple max par rep (Nm)")
            lc['xaxis']['tickmode']='linear'; lc['yaxis']['title']='Couple max (Nm)'
            fig_c.update_layout(**lc); st.plotly_chart(fig_c, use_container_width=True)

        with col_r3:
            fig_a = go.Figure()
            for s, c in [('Extension', C_ORANGE), ('Retour', C_BLUE)]:
                sub = df_reps[df_reps['sens'] == s]
                if sub.empty: continue
                fig_a.add_trace(go.Bar(x=sub['rep'], y=sub['amplitude'].round(1),
                    name=s, marker_color=c, opacity=0.85,
                    hovertemplate=f'{s} Rep %{{x}}<br>%{{y:.1f}}°<extra></extra>'))
            la = base_layout(height=260, title="Amplitude par rep (°)")
            la['barmode']='group'; la['xaxis']['tickmode']='linear'; la['yaxis']['title']='Amplitude (°)'
            fig_a.update_layout(**la); st.plotly_chart(fig_a, use_container_width=True)

        with st.expander("📄 Tableau complet"):
            st.dataframe(df_reps.copy().round(2).rename(columns={
                'rep':'Rép','sens':'Sens','couple_max':'Couple max (Nm)',
                'couple_moyen':'Couple moy (Nm)','amplitude':'Amplitude (°)',
                'duree_sec':'Durée (s)','energie_j':'Énergie (J)'
            }), use_container_width=True, hide_index=True)
