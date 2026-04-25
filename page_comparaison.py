import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from styles import *
from db import get_seances_test, get_meilleure_rep, get_courbe_serie, get_series_seance, get_stats_reps

PALETTE = ['#FF6B35','#0066FF','#00C896','#FF4757','#7B5EA7','#FFB800','#00BCD4','#E91E63']

def get_courbe_meilleure_rep_local(serie_id, sens_val):
    from db import query
    df = query("""
        SELECT rep, position, couple
        FROM mesures
        WHERE serie_id = %s AND statut IN ('Actif','1.0','1')
          AND sens = %s AND couple IS NOT NULL
        ORDER BY rep, position
    """, params=(serie_id, sens_val))
    if df.empty: return pd.DataFrame()
    best_rep = df.groupby('rep')['couple'].max().idxmax()
    return df[df['rep'] == best_rep].sort_values('position')

def show(client_id, client_nom, cote, poids_kg):
    st.markdown(f"""<div class="page-header">
        <h1>📊 Comparaison Tests Isocinétiques</h1>
        <p>{client_nom} · Comparer plusieurs tests — côtés et dates au choix</p>
    </div>""", unsafe_allow_html=True)

    tous_tests = get_seances_test(client_id)
    tests_right = tous_tests[tous_tests['cote'] == 'Right'].copy()
    tests_left  = tous_tests[tous_tests['cote'] == 'Left'].copy()

    if tous_tests.empty:
        st.info("Aucun test isocinétique trouvé.")
        return

    # ── Construction liste tous les tests dispo ───────────────────────────────
    options_tests = {}
    for _, row in tests_right.iterrows():
        d = pd.to_datetime(row['date_seance'])
        label = f"🔴 Droit — {d.strftime('%d/%m/%Y')}"
        options_tests[label] = {'seance_id': int(row['seance_id']), 'cote': 'Droit', 'date': d}
    for _, row in tests_left.iterrows():
        d = pd.to_datetime(row['date_seance'])
        label = f"🟢 Gauche — {d.strftime('%d/%m/%Y')}"
        options_tests[label] = {'seance_id': int(row['seance_id']), 'cote': 'Gauche', 'date': d}

    # ── Sélection tests à comparer ────────────────────────────────────────────
    section("⚙️ Sélection des tests à comparer")
    tests_sel = st.multiselect(
        "Tests à comparer (côté + date)",
        options=list(options_tests.keys()),
        default=list(options_tests.keys()),
    )
    if not tests_sel:
        st.info("Sélectionne au moins un test.")
        return

    # ── Tableau comparatif métriques ──────────────────────────────────────────
    section("📋 Tableau comparatif")

    rows = []
    for label in tests_sel:
        t = options_tests[label]
        df_m = get_meilleure_rep(t['seance_id'], poids_kg)
        if df_m.empty: continue
        ext = df_m[df_m['sens'] == 'Extension']
        ret = df_m[df_m['sens'] == 'Retour']
        pic_quad = float(ext['pic_couple'].max()) if not ext.empty else None
        pic_ij   = float(ret['pic_couple'].max()) if not ret.empty else None
        ratio    = round(pic_ij / pic_quad * 100, 1) if pic_quad and pic_ij else None
        rows.append({
            'Test': label,
            'Pic Quad (Nm)': round(pic_quad, 1) if pic_quad else None,
            'Quad/Poids (Nm/kg)': round(pic_quad/poids_kg, 2) if pic_quad and poids_kg else None,
            'Pic IJ (Nm)': round(pic_ij, 1) if pic_ij else None,
            'IJ/Poids (Nm/kg)': round(pic_ij/poids_kg, 2) if pic_ij and poids_kg else None,
            'Ratio IJ/Q (%)': ratio,
        })

    if rows:
        df_comp = pd.DataFrame(rows)
        st.dataframe(df_comp, use_container_width=True, hide_index=True)

    # ── Graphiques par série ──────────────────────────────────────────────────
    SERIES_INFO = [
        (1, "Série 1 — 60°/s × 3 reps"),
        (2, "Série 2 — 30°/s × 3 reps"),
        (3, "Série 3 — 240°/s × 20 reps"),
    ]

    for serie_num, serie_label in SERIES_INFO:
        section(f"📈 {serie_label}")

        # Préparer données par test
        data_par_test = {}
        for label in tests_sel:
            t = options_tests[label]
            series = get_series_seance(t['seance_id'])
            sr_match = series[series['serie'] == serie_num]
            if sr_match.empty: continue
            serie_id = int(sr_match.iloc[0]['id'])
            df_courbe = get_courbe_serie(serie_id)
            df_actif  = df_courbe[df_courbe['statut'].isin(['Actif','1.0','1'])]
            data_par_test[label] = {'serie_id': serie_id, 'df': df_actif}

        if not data_par_test:
            st.caption("Pas de données pour cette série.")
            continue

        # ── Meilleure rep ─────────────────────────────────────────────────────
        st.markdown("**Meilleure répétition**")
        col_best_e, col_best_r = st.columns(2)

        for fig_col, sens_val, titre in [
            (col_best_e, 'Extension', 'Extenseurs — Quadriceps'),
            (col_best_r, 'Retour',    'Fléchisseurs — Ischios')
        ]:
            fig = go.Figure()
            for ci, (label, data) in enumerate(data_par_test.items()):
                df_best = get_courbe_meilleure_rep_local(data['serie_id'], sens_val)
                if df_best.empty: continue
                fig.add_trace(go.Scatter(
                    x=df_best['position'], y=df_best['couple'].round(1),
                    mode='lines', name=label,
                    line=dict(color=PALETTE[ci % len(PALETTE)], width=2.5),
                    hovertemplate=f'<b>{label}</b><br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
                ))
            l = base_layout(height=300, title=titre)
            l['xaxis']['title'] = 'Position (°)'; l['yaxis']['title'] = 'Couple (Nm)'
            fig.update_layout(**l)
            with fig_col:
                st.plotly_chart(fig, use_container_width=True)

        # ── Reps individuelles ────────────────────────────────────────────────
        st.markdown("**Toutes les répétitions**")
        col_re, col_rr = st.columns(2)
        for fig_col, sens_val, titre in [
            (col_re, 'Extension', 'Extenseurs — Quadriceps — toutes reps'),
            (col_rr, 'Retour',    'Fléchisseurs — Ischios — toutes reps')
        ]:
            fig_ri = go.Figure()
            for ci, (label, data) in enumerate(data_par_test.items()):
                df_s = data['df'][data['df']['sens'] == sens_val]
                base_color = PALETTE[ci % len(PALETTE)]
                reps = sorted(df_s['rep'].unique())
                for i, rep_num in enumerate(reps):
                    sub = df_s[df_s['rep'] == rep_num]
                    fig_ri.add_trace(go.Scatter(
                        x=sub['position'], y=sub['couple'],
                        mode='lines',
                        name=f'{label}' if i == 0 else f'_{label}_rep{rep_num}',
                        showlegend=(i == 0),
                        line=dict(color=base_color, width=1.5),
                        opacity=0.35 + (i / max(len(reps)-1, 1)) * 0.65,
                        hovertemplate=f'{label}<br>Rep {rep_num}<br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
                    ))
            lr = base_layout(height=300, title=titre)
            lr['xaxis']['title'] = 'Position (°)'; lr['yaxis']['title'] = 'Couple (Nm)'
            fig_ri.update_layout(**lr)
            with fig_col:
                st.plotly_chart(fig_ri, use_container_width=True)

        # ── Stats par rep du premier test ─────────────────────────────────────
        first_label = list(data_par_test.keys())[0]
        first_serie_id = data_par_test[first_label]['serie_id']
        df_reps = get_stats_reps(first_serie_id)

        if not df_reps.empty:
            with st.expander(f"📋 Stats par rep — {first_label}"):
                col_r1, col_r2, col_r3 = st.columns(3)
                for col, y_col, titre_r, y_label in [
                    (col_r1, 'duree_sec',  'Durée par rep (s)',        'Durée (s)'),
                    (col_r2, 'couple_max', 'Couple max par rep (Nm)',  'Couple max (Nm)'),
                    (col_r3, 'amplitude',  'Amplitude par rep (°)',    'Amplitude (°)'),
                ]:
                    fig_s = go.Figure()
                    for s_val, color in [('Extension', C_ORANGE), ('Retour', C_GREEN)]:
                        sub = df_reps[df_reps['sens'] == s_val]
                        if sub.empty: continue
                        if y_col == 'couple_max':
                            fig_s.add_trace(go.Scatter(
                                x=sub['rep'], y=sub[y_col].round(2),
                                name=s_val, mode='lines+markers',
                                line=dict(color=color, width=2),
                                marker=dict(size=7, line=dict(color='white', width=1.5)),
                                hovertemplate=f'{s_val} Rep %{{x}}<br>%{{y:.1f}}<extra></extra>'
                            ))
                        else:
                            fig_s.add_trace(go.Bar(
                                x=sub['rep'], y=sub[y_col].round(2),
                                name=s_val, marker_color=color, opacity=0.85,
                                hovertemplate=f'{s_val} Rep %{{x}}<br>%{{y:.2f}}<extra></extra>'
                            ))
                    ls = base_layout(height=240, title=titre_r)
                    ls['barmode'] = 'group'; ls['xaxis']['tickmode'] = 'linear'
                    ls['yaxis']['title'] = y_label
                    fig_s.update_layout(**ls)
                    with col:
                        st.plotly_chart(fig_s, use_container_width=True)

    # ── Déficit D/G dans le temps ─────────────────────────────────────────────
    tests_right_sel = {l: options_tests[l] for l in tests_sel if '🔴 Droit' in l}
    tests_left_sel  = {l: options_tests[l] for l in tests_sel if '🟢 Gauche' in l}

    if tests_right_sel and tests_left_sel:
        section("⚖️ Déficit Droit vs Gauche")

        def peak_par_date(tests_dict):
            rows = []
            for label, t in tests_dict.items():
                df_m = get_meilleure_rep(t['seance_id'], poids_kg)
                if df_m.empty: continue
                ext = df_m[df_m['sens'] == 'Extension']
                ret = df_m[df_m['sens'] == 'Retour']
                rows.append({
                    'date': t['date'],
                    'pic_quad': float(ext['pic_couple'].max()) if not ext.empty else None,
                    'pic_ij':   float(ret['pic_couple'].max()) if not ret.empty else None,
                })
            return pd.DataFrame(rows).sort_values('date') if rows else pd.DataFrame()

        df_r = peak_par_date(tests_right_sel)
        df_l = peak_par_date(tests_left_sel)

        if not df_r.empty and not df_l.empty:
            merged = df_r[['date','pic_quad']].merge(
                df_l[['date','pic_quad']], on='date', suffixes=('_r','_l')).dropna()
            if not merged.empty:
                merged['deficit'] = ((merged['pic_quad_r'] - merged['pic_quad_l'])
                                     / merged['pic_quad_l'] * 100).round(1)
                fig_def = go.Figure()
                bar_colors = [C_RED if v < -10 else C_YELLOW if v < 0 else C_GREEN
                              for v in merged['deficit']]
                fig_def.add_trace(go.Bar(
                    x=merged['date'], y=merged['deficit'],
                    marker_color=bar_colors,
                    hovertemplate='%{x|%d/%m/%Y}<br>Déficit : %{y:.1f}%<extra></extra>'
                ))
                fig_def.add_hline(y=-10, line_color=C_RED, line_width=1.5, line_dash='dot',
                                  annotation_text='Seuil clinique -10%',
                                  annotation_font_color=C_RED)
                fig_def.add_hline(y=0, line_color='#E2E8F0', line_width=1)
                l_def = base_layout(height=280, title="Déficit Quadriceps Droit vs Gauche (%)")
                l_def['xaxis']['tickformat'] = '%d/%m/%Y'
                l_def['yaxis']['title'] = 'Déficit (%)'
                l_def['showlegend'] = False
                fig_def.update_layout(**l_def)
                st.plotly_chart(fig_def, use_container_width=True)
                st.caption("Rouge = déficit cliniquement significatif (> 10%)")
