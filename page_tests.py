import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math, io, os, tempfile
from styles import *
from db import get_seances_test, get_courbe_serie, get_series_seance, get_stats_reps, query

PI = math.pi
PALETTE = ['#FF6B35','#0066FF','#00C896','#FF4757','#7B5EA7','#FFB800','#00BCD4','#E91E63']

# ── Requêtes spécifiques test ─────────────────────────────────────────────────
def get_metriques_serie(serie_id, poids_kg):
    """Calcule toutes les métriques cliniques pour une série."""
    df = query(f"""
        SELECT rep, sens,
            MAX(couple)                                               AS couple_max,
            SUM(ABS(couple) * (ABS(vitesse) * {PI} / 180.0) * 0.01) AS travail_j,
            MAX(position) - MIN(position)                            AS amplitude
        FROM mesures
        WHERE serie_id = %s AND statut IN ('Actif','1.0','1')
          AND couple IS NOT NULL AND vitesse IS NOT NULL
        GROUP BY rep, sens ORDER BY rep, sens
    """, params=(serie_id,))
    return df

def get_courbe_meilleure_rep(serie_id, sens_val):
    """Retourne la courbe de la meilleure répétition pour un sens donné."""
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

def calc_indice_fatigue(df_metriques, sens_val, nb_reps=20):
    """Indice de fatigue : travail premiers tiers vs derniers tiers."""
    sub = df_metriques[df_metriques['sens'] == sens_val].sort_values('rep')
    if len(sub) < 6: return None
    tiers = max(1, len(sub) // 3)
    travail_debut = sub.head(tiers)['travail_j'].mean()
    travail_fin   = sub.tail(tiers)['travail_j'].mean()
    if travail_debut == 0: return None
    return round((travail_fin - travail_debut) / travail_debut * 100, 1)

def calc_stats_cliniques(df_metriques, sens_val, poids_kg):
    """Pic couple, travail meilleure rep, amplitude."""
    sub = df_metriques[df_metriques['sens'] == sens_val]
    if sub.empty:
        return {'pic': None, 'pic_kg': None, 'travail': None, 'travail_kg': None, 'amplitude': None}
    best_idx = sub['couple_max'].idxmax()
    best = sub.loc[best_idx]
    pic = round(float(best['couple_max']), 1)
    trav = round(float(best['travail_j']), 1)
    amp  = round(float(best['amplitude']), 1)
    return {
        'pic': pic,
        'pic_kg': round(pic / poids_kg, 2) if poids_kg else None,
        'travail': trav,
        'travail_kg': round(trav / poids_kg, 2) if poids_kg else None,
        'amplitude': amp
    }

def build_rapport_data(seance_right_id, seance_left_id, poids_kg):
    """Construit toutes les données du rapport pour les deux genoux."""
    rapport = {}
    for cote, seance_id in [('Droit', seance_right_id), ('Gauche', seance_left_id)]:
        if seance_id is None: continue
        series = get_series_seance(seance_id)
        rapport[cote] = {}
        for _, sr in series.iterrows():
            serie_num = int(sr['serie'])
            serie_id  = int(sr['id'])
            vit       = int(sr['vitesse_cible'])
            nb_reps   = int(sr['nb_reps_cible'])
            df_met    = get_metriques_serie(serie_id, poids_kg)
            rapport[cote][serie_num] = {
                'serie_id':  serie_id,
                'vitesse':   vit,
                'nb_reps':   nb_reps,
                'metriques': df_met,
                'ext': calc_stats_cliniques(df_met, 'Extension', poids_kg),
                'ret': calc_stats_cliniques(df_met, 'Retour', poids_kg),
                'fatigue_ext': calc_indice_fatigue(df_met, 'Extension'),
                'fatigue_ret': calc_indice_fatigue(df_met, 'Retour'),
                'travail_total_ext': round(float(df_met[df_met['sens']=='Extension']['travail_j'].sum()), 1) if not df_met.empty else None,
                'travail_total_ret': round(float(df_met[df_met['sens']=='Retour']['travail_j'].sum()), 1) if not df_met.empty else None,
            }
    return rapport

def deficit(val_d, val_g):
    if val_d is None or val_g is None or val_g == 0: return None
    return round((val_d - val_g) / val_g * 100, 1)

def fmt(v, unit=""):
    if v is None: return "—"
    return f"{v}{unit}"

def badge_deficit(d):
    if d is None: return ""
    if d < -10: return f'<span class="badge badge-warn">{d}%</span>'
    elif d < 0: return f'<span style="color:#FFB800;font-weight:600">{d}%</span>'
    else: return f'<span class="badge badge-ok">+{d}%</span>'

def tableau_serie(serie_num, rapport, label_ext, label_ret, show_fatigue=False):
    """Affiche le tableau clinique d'une série."""
    d = rapport.get('Droit', {}).get(serie_num)
    g = rapport.get('Gauche', {}).get(serie_num)

    rows = []
    # Extenseurs
    rows.append({'Métrique': f'**{label_ext}**', 'Droit': '', 'Gauche': '', 'Déficit': ''})
    if d and g:
        def_pic = deficit(d['ext']['pic'], g['ext']['pic'])
        def_trav = deficit(d['ext']['travail'], g['ext']['travail'])
        rows.append({'Métrique': 'Pic de couple (Nm)', 'Droit': fmt(d['ext']['pic']), 'Gauche': fmt(g['ext']['pic']), 'Déficit': fmt(def_pic, '%')})
        rows.append({'Métrique': 'Couple/Poids (Nm/kg)', 'Droit': fmt(d['ext']['pic_kg']), 'Gauche': fmt(g['ext']['pic_kg']), 'Déficit': ''})
        rows.append({'Métrique': 'Travail/rep (J)', 'Droit': fmt(d['ext']['travail']), 'Gauche': fmt(g['ext']['travail']), 'Déficit': fmt(def_trav, '%')})
        rows.append({'Métrique': 'Travail/Poids (J/kg)', 'Droit': fmt(d['ext']['travail_kg']), 'Gauche': fmt(g['ext']['travail_kg']), 'Déficit': ''})
        rows.append({'Métrique': 'Amplitude (°)', 'Droit': fmt(d['ext']['amplitude']), 'Gauche': fmt(g['ext']['amplitude']), 'Déficit': ''})
    elif d:
        rows.append({'Métrique': 'Pic de couple (Nm)', 'Droit': fmt(d['ext']['pic']), 'Gauche': '—', 'Déficit': '—'})
        rows.append({'Métrique': 'Couple/Poids (Nm/kg)', 'Droit': fmt(d['ext']['pic_kg']), 'Gauche': '—', 'Déficit': ''})
        rows.append({'Métrique': 'Travail/rep (J)', 'Droit': fmt(d['ext']['travail']), 'Gauche': '—', 'Déficit': '—'})
        rows.append({'Métrique': 'Amplitude (°)', 'Droit': fmt(d['ext']['amplitude']), 'Gauche': '—', 'Déficit': ''})

    # Ratio IJ/Q
    if d and g:
        ratio_d = round(d['ret']['pic'] / d['ext']['pic'] * 100, 1) if d['ext']['pic'] and d['ret']['pic'] else None
        ratio_g = round(g['ret']['pic'] / g['ext']['pic'] * 100, 1) if g['ext']['pic'] and g['ret']['pic'] else None
        rows.append({'Métrique': 'Ratio IJ/Q (%)', 'Droit': fmt(ratio_d), 'Gauche': fmt(ratio_g), 'Déficit': ''})

    # Fléchisseurs
    rows.append({'Métrique': f'**{label_ret}**', 'Droit': '', 'Gauche': '', 'Déficit': ''})
    if d and g:
        def_pic_r = deficit(d['ret']['pic'], g['ret']['pic'])
        def_trav_r = deficit(d['ret']['travail'], g['ret']['travail'])
        rows.append({'Métrique': 'Pic de couple (Nm)', 'Droit': fmt(d['ret']['pic']), 'Gauche': fmt(g['ret']['pic']), 'Déficit': fmt(def_pic_r, '%')})
        rows.append({'Métrique': 'Couple/Poids (Nm/kg)', 'Droit': fmt(d['ret']['pic_kg']), 'Gauche': fmt(g['ret']['pic_kg']), 'Déficit': ''})
        rows.append({'Métrique': 'Travail/rep (J)', 'Droit': fmt(d['ret']['travail']), 'Gauche': fmt(g['ret']['travail']), 'Déficit': fmt(def_trav_r, '%')})
        rows.append({'Métrique': 'Travail/Poids (J/kg)', 'Droit': fmt(d['ret']['travail_kg']), 'Gauche': fmt(g['ret']['travail_kg']), 'Déficit': ''})
        rows.append({'Métrique': 'Amplitude (°)', 'Droit': fmt(d['ret']['amplitude']), 'Gauche': fmt(g['ret']['amplitude']), 'Déficit': ''})
    elif d:
        rows.append({'Métrique': 'Pic de couple (Nm)', 'Droit': fmt(d['ret']['pic']), 'Gauche': '—', 'Déficit': '—'})

    # Fatigue + Travail total (série 3 seulement)
    if show_fatigue:
        rows.append({'Métrique': '**Indice de fatigue**', 'Droit': '', 'Gauche': '', 'Déficit': ''})
        fat_ext_d = d['fatigue_ext'] if d else None
        fat_ext_g = g['fatigue_ext'] if g else None
        fat_ret_d = d['fatigue_ret'] if d else None
        fat_ret_g = g['fatigue_ret'] if g else None
        rows.append({'Métrique': 'Fatigue Extenseurs (%)', 'Droit': fmt(fat_ext_d), 'Gauche': fmt(fat_ext_g), 'Déficit': ''})
        rows.append({'Métrique': 'Fatigue Fléchisseurs (%)', 'Droit': fmt(fat_ret_d), 'Gauche': fmt(fat_ret_g), 'Déficit': ''})
        rows.append({'Métrique': '**Travail total (J)**', 'Droit': '', 'Gauche': '', 'Déficit': ''})
        rows.append({'Métrique': 'Extenseurs', 'Droit': fmt(d['travail_total_ext'] if d else None), 'Gauche': fmt(g['travail_total_ext'] if g else None), 'Déficit': ''})
        rows.append({'Métrique': 'Fléchisseurs', 'Droit': fmt(d['travail_total_ret'] if d else None), 'Gauche': fmt(g['travail_total_ret'] if g else None), 'Déficit': ''})

    return pd.DataFrame(rows)

def graphique_courbes(rapport, serie_num, sens_val, titre, color_d, color_g):
    """Graphique meilleure rep Droit vs Gauche."""
    fig = go.Figure()
    for cote, color in [('Droit', color_d), ('Gauche', color_g)]:
        data = rapport.get(cote, {}).get(serie_num)
        if not data: continue
        df_c = get_courbe_meilleure_rep(data['serie_id'], sens_val)
        if df_c.empty: continue
        fig.add_trace(go.Scatter(
            x=df_c['position'], y=df_c['couple'].round(1),
            mode='lines', name=cote,
            line=dict(color=color, width=2.5),
            hovertemplate=f'<b>{cote}</b><br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
        ))
    l = base_layout(height=300, title=titre)
    l['xaxis']['title'] = 'Position (°)'; l['yaxis']['title'] = 'Couple (Nm)'
    fig.update_layout(**l)
    return fig

# ── Export PDF ────────────────────────────────────────────────────────────────
def export_pdf(rapport, client_nom, date_test, poids_kg, figs_data):
    """Génère un PDF clinique avec reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, Image, HRFlowable)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import plotly.io as pio

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                rightMargin=1.5*cm, leftMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)

        styles = getSampleStyleSheet()
        style_title   = ParagraphStyle('T', fontSize=16, fontName='Helvetica-Bold',
                                        alignment=TA_CENTER, spaceAfter=4)
        style_sub     = ParagraphStyle('S', fontSize=10, fontName='Helvetica',
                                        alignment=TA_CENTER, spaceAfter=12, textColor=colors.grey)
        style_h2      = ParagraphStyle('H2', fontSize=12, fontName='Helvetica-Bold',
                                        spaceBefore=12, spaceAfter=6, textColor=colors.HexColor('#0066FF'))
        style_caption = ParagraphStyle('C', fontSize=8, fontName='Helvetica',
                                        textColor=colors.grey, spaceAfter=4)
        style_normal  = styles['Normal']

        story = []

        # En-tête
        story.append(Paragraph("RAPPORT TEST ISOCINÉTIQUE", style_title))
        story.append(Paragraph(f"{client_nom}  ·  {date_test}  ·  Poids : {int(poids_kg) if poids_kg else '—'} kg", style_sub))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0066FF')))
        story.append(Spacer(1, 0.3*cm))

        SERIES_INFO = [
            (1, "Série 1 — 60°/s × 3 reps", "Extenseurs (Con)", "Fléchisseurs (Con)", False),
            (2, "Série 2 — 30°/s × 3 reps", "Fléchisseurs (Con)", "Fléchisseurs (Ecc)", False),
            (3, "Série 3 — 240°/s × 20 reps", "Extenseurs (Con)", "Fléchisseurs (Con)", True),
        ]

        for serie_num, serie_label, label_ext, label_ret, show_fat in SERIES_INFO:
            story.append(Paragraph(serie_label, style_h2))

            # Tableau métriques
            df_tab = tableau_serie(serie_num, rapport, label_ext, label_ret, show_fatigue=show_fat)
            table_data = [['Métrique', 'Droit', 'Gauche', 'Déficit']]
            for _, row in df_tab.iterrows():
                metrique = str(row['Métrique']).replace('**','')
                is_header = '**' in str(row['Métrique'])
                table_data.append([
                    Paragraph(f"<b>{metrique}</b>" if is_header else metrique, style_normal),
                    Paragraph(f"<b>{row['Droit']}</b>" if is_header else str(row['Droit']), style_normal),
                    Paragraph(f"<b>{row['Gauche']}</b>" if is_header else str(row['Gauche']), style_normal),
                    Paragraph(str(row['Déficit']), style_normal),
                ])

            col_widths = [8*cm, 3*cm, 3*cm, 3*cm]
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0066FF')),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0,0), (-1,-1), 9),
                ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7F9FC')]),
                ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.3*cm))

            # Graphiques pour cette série
            key_ext = f"{serie_num}_ext"
            key_ret = f"{serie_num}_ret"
            if key_ext in figs_data and key_ret in figs_data:
                img_row = []
                for key in [key_ext, key_ret]:
                    fig = figs_data[key]
                    img_bytes = pio.to_image(fig, format='png', width=480, height=280, scale=2)
                    img_buf = io.BytesIO(img_bytes)
                    img_row.append(Image(img_buf, width=8.5*cm, height=5*cm))
                t_img = Table([img_row], colWidths=[8.5*cm, 8.5*cm])
                story.append(t_img)

            story.append(Spacer(1, 0.4*cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0')))

        doc.build(story)
        buf.seek(0)
        return buf
    except Exception as e:
        st.error(f"Erreur PDF : {e}")
        return None

# ── PAGE PRINCIPALE ───────────────────────────────────────────────────────────
def show(client_id, client_nom, cote, poids_kg):
    st.markdown(f"""<div class="page-header">
        <h1>🏥 Tests Isocinétiques</h1>
        <p>{client_nom} · Rapport clinique complet · Droit vs Gauche</p>
    </div>""", unsafe_allow_html=True)

    tous_tests = get_seances_test(client_id)
    tests_right = tous_tests[tous_tests['cote'] == 'Right'].copy()
    tests_left  = tous_tests[tous_tests['cote'] == 'Left'].copy()

    if tous_tests.empty:
        st.info("Aucun test isocinétique trouvé.")
        return

    # ── Sélection date ────────────────────────────────────────────────────────
    section("📅 Sélection du test")
    dates_right = {pd.to_datetime(r['date_seance']).date(): int(r['seance_id'])
                   for _, r in tests_right.iterrows()}
    dates_left  = {pd.to_datetime(r['date_seance']).date(): int(r['seance_id'])
                   for _, r in tests_left.iterrows()}
    all_dates = sorted(set(dates_right) | set(dates_left))

    col_d, col_opts = st.columns([2, 2])
    with col_d:
        date_sel = st.selectbox("Date du test", all_dates,
                                format_func=lambda d: d.strftime('%d/%m/%Y'))
    with col_opts:
        show_reps = st.checkbox("Afficher les reps individuelles", value=True)

    seance_right_id = dates_right.get(date_sel)
    seance_left_id  = dates_left.get(date_sel)

    if not seance_right_id and not seance_left_id:
        st.info("Pas de données pour cette date.")
        return

    # ── Construire les données rapport ────────────────────────────────────────
    rapport = build_rapport_data(seance_right_id, seance_left_id, poids_kg)

    # ── KPIs globaux ──────────────────────────────────────────────────────────
    section("📊 Résumé")
    d1 = rapport.get('Droit', {}).get(1, {})
    g1 = rapport.get('Gauche', {}).get(1, {})
    pic_quad_d = d1.get('ext', {}).get('pic') if d1 else None
    pic_quad_g = g1.get('ext', {}).get('pic') if g1 else None
    pic_ij_d   = d1.get('ret', {}).get('pic') if d1 else None
    pic_ij_g   = g1.get('ret', {}).get('pic') if g1 else None
    ratio_d    = round(pic_ij_d / pic_quad_d * 100, 1) if pic_quad_d and pic_ij_d else None
    ratio_g    = round(pic_ij_g / pic_quad_g * 100, 1) if pic_quad_g and pic_ij_g else None
    def_quad   = deficit(pic_quad_d, pic_quad_g)

    ratio_d_ok = 55 <= ratio_d <= 80 if ratio_d else False
    ratio_g_ok = 55 <= ratio_g <= 80 if ratio_g else False
    def_ok     = def_quad is not None and def_quad > -10

    st.markdown(f"""<div class="kpi-row">
        {kpi("Pic Quad Droit (S1)", fmt(pic_quad_d, " Nm"), "",
             f'<span class="neu">{fmt(d1.get("ext",{}).get("pic_kg"), " Nm/kg")}</span>' if d1 else "", C_ORANGE)}
        {kpi("Pic Quad Gauche (S1)", fmt(pic_quad_g, " Nm"), "",
             f'<span class="neu">{fmt(g1.get("ext",{}).get("pic_kg"), " Nm/kg")}</span>' if g1 else "", C_GREEN)}
        {kpi("Déficit D/G Quad", fmt(def_quad, "%"), "",
             f'<span class="{"up" if def_ok else "down"}">{"✓ Normal" if def_ok else "⚠ Déficit > 10%"}</span>' if def_quad is not None else "", C_RED if not def_ok and def_quad is not None else C_GREEN)}
        {kpi("Ratio IJ/Q Droit", fmt(ratio_d, "%"), "",
             f'<span class="{"up" if ratio_d_ok else "down"}">{"✓ Normal (55-80%)" if ratio_d_ok else "⚠ À surveiller"}</span>' if ratio_d else "", C_GREEN if ratio_d_ok else C_RED)}
        {kpi("Ratio IJ/Q Gauche", fmt(ratio_g, "%"), "",
             f'<span class="{"up" if ratio_g_ok else "down"}">{"✓ Normal (55-80%)" if ratio_g_ok else "⚠ À surveiller"}</span>' if ratio_g else "", C_GREEN if ratio_g_ok else C_RED)}
    </div>""", unsafe_allow_html=True)

    # ── Rapport par série ─────────────────────────────────────────────────────
    SERIES_INFO = [
        (1, "Série 1 — 60°/s × 3 reps — Con/Con", "Extenseurs (Con)", "Fléchisseurs (Con)", False),
        (2, "Série 2 — 30°/s × 3 reps — Con/Ecc", "Fléchisseurs (Con)", "Fléchisseurs (Ecc)", False),
        (3, "Série 3 — 240°/s × 20 reps — Con/Con", "Extenseurs (Con)", "Fléchisseurs (Con)", True),
    ]

    figs_data = {}

    for serie_num, serie_label, label_ext, label_ret, show_fat in SERIES_INFO:
        d_data = rapport.get('Droit', {}).get(serie_num)
        g_data = rapport.get('Gauche', {}).get(serie_num)
        if not d_data and not g_data: continue

        section(f"📋 {serie_label}")

        # Tableau métriques
        df_tab = tableau_serie(serie_num, rapport, label_ext, label_ret, show_fatigue=show_fat)

        # Affichage stylisé du tableau
        col_tab, col_info = st.columns([3, 1])
        with col_tab:
            # Mise en forme : lignes header en gras/bleu
            def style_row(row):
                if str(row['Métrique']).startswith('**'):
                    return ['background-color:#EBF3FF; font-weight:bold']*4
                d_val = str(row.get('Déficit',''))
                try:
                    v = float(d_val.replace('%',''))
                    if v < -10: return ['','','','color:red;font-weight:bold']
                    elif v < 0: return ['','','','color:orange;font-weight:bold']
                except: pass
                return ['']*4

            df_display = df_tab.copy()
            df_display['Métrique'] = df_display['Métrique'].str.replace('**','')
            st.dataframe(
                df_display.style.apply(style_row, axis=1),
                use_container_width=True, hide_index=True
            )

        with col_info:
            if show_fat and d_data:
                fat_e = d_data.get('fatigue_ext')
                fat_r = d_data.get('fatigue_ret')
                if fat_e is not None:
                    color = "down" if fat_e < -20 else "neu"
                    st.markdown(f'<div style="margin-top:8px"><div class="kpi-label">Fatigue Ext Droit</div><div class="kpi-value" style="font-size:20px">{fat_e}<span class="kpi-unit">%</span></div><div class="kpi-delta"><span class="{color}">{"⚠ Élevée" if fat_e < -20 else "Normal"}</span></div></div>', unsafe_allow_html=True)
                if fat_r is not None:
                    color = "down" if fat_r < -20 else "neu"
                    st.markdown(f'<div style="margin-top:12px"><div class="kpi-label">Fatigue Fl Droit</div><div class="kpi-value" style="font-size:20px">{fat_r}<span class="kpi-unit">%</span></div><div class="kpi-delta"><span class="{color}">{"⚠ Élevée" if fat_r < -20 else "Normal"}</span></div></div>', unsafe_allow_html=True)

        # Graphiques meilleure rep
        st.markdown("**Courbes — Meilleure répétition**")
        col_g1, col_g2 = st.columns(2)

        fig_ext = graphique_courbes(rapport, serie_num, 'Extension',
                                     f"Extenseurs — {label_ext}", C_ORANGE, C_GREEN)
        fig_ret = graphique_courbes(rapport, serie_num, 'Retour',
                                     f"Fléchisseurs — {label_ret}", C_ORANGE, C_GREEN)
        figs_data[f"{serie_num}_ext"] = fig_ext
        figs_data[f"{serie_num}_ret"] = fig_ret

        with col_g1:
            st.plotly_chart(fig_ext, use_container_width=True)
        with col_g2:
            st.plotly_chart(fig_ret, use_container_width=True)
        st.caption("🟠 Droit · 🟢 Gauche · Meilleure répétition uniquement (comme sur le rapport clinique officiel)")

        # Reps individuelles (optionnel)
        if show_reps:
            with st.expander(f"📈 Reps individuelles — Série {serie_num}"):
                col_re, col_rr = st.columns(2)
                for fig_col, cote_val, sens_val, titre_r, color_r in [
                    (col_re, 'Droit',  'Extension', f"Extenseurs Droit", C_ORANGE),
                    (col_rr, 'Gauche', 'Extension', f"Extenseurs Gauche", C_GREEN),
                ]:
                    data_c = rapport.get(cote_val, {}).get(serie_num)
                    if not data_c: continue
                    df_c = get_courbe_serie(data_c['serie_id'])
                    df_a = df_c[df_c['statut'].isin(['Actif','1.0','1'])]
                    df_s = df_a[df_a['sens'] == sens_val]
                    fig_ri = go.Figure()
                    for i, rep_num in enumerate(sorted(df_s['rep'].unique())):
                        sub = df_s[df_s['rep'] == rep_num]
                        fig_ri.add_trace(go.Scatter(
                            x=sub['position'], y=sub['couple'], mode='lines',
                            name=f'Rep {rep_num}',
                            line=dict(color=PALETTE[i % len(PALETTE)], width=1.5),
                            hovertemplate=f'Rep {rep_num}<br>%{{x:.1f}}°  %{{y:.1f}} Nm<extra></extra>'
                        ))
                    lr = base_layout(height=260, title=f"{titre_r} — toutes reps")
                    lr['xaxis']['title'] = 'Position (°)'; lr['yaxis']['title'] = 'Couple (Nm)'
                    fig_ri.update_layout(**lr)
                    with fig_col:
                        st.plotly_chart(fig_ri, use_container_width=True)

    # ── Export PDF ────────────────────────────────────────────────────────────
    section("📄 Export PDF")
    st.markdown("Génère un rapport PDF clinique complet avec tableaux et graphiques.")

    if st.button("📥 Générer le rapport PDF", type="primary"):
        with st.spinner("Génération du PDF en cours..."):
            # Vérifier kaleido
            try:
                import plotly.io as pio
                pdf_buf = export_pdf(rapport, client_nom, date_sel.strftime('%d/%m/%Y'), poids_kg, figs_data)
                if pdf_buf:
                    st.download_button(
                        label="⬇️ Télécharger le rapport PDF",
                        data=pdf_buf,
                        file_name=f"rapport_iso_{client_nom.replace(' ','_')}_{date_sel}.pdf",
                        mime="application/pdf"
                    )
            except ImportError:
                st.warning("Pour l'export avec graphiques, installe kaleido : `pip install kaleido`")
                pdf_buf = export_pdf(rapport, client_nom, date_sel.strftime('%d/%m/%Y'), poids_kg, {})
                if pdf_buf:
                    st.download_button(
                        label="⬇️ Télécharger le rapport PDF (sans graphiques)",
                        data=pdf_buf,
                        file_name=f"rapport_iso_{client_nom.replace(' ','_')}_{date_sel}.pdf",
                        mime="application/pdf"
                    )

    # ── Évolution dans le temps ───────────────────────────────────────────────
    if len(all_dates) > 1:
        section("📈 Évolution des tests dans le temps")

        dates_right_sorted = sorted(dates_right.keys())
        ev_rows = []
        for d in dates_right_sorted:
            sid = dates_right[d]
            r = build_rapport_data(sid, dates_left.get(d), poids_kg)
            s1d = r.get('Droit', {}).get(1, {})
            s1g = r.get('Gauche', {}).get(1, {})
            ev_rows.append({
                'date': d,
                'pic_quad_d': s1d.get('ext', {}).get('pic') if s1d else None,
                'pic_quad_g': s1g.get('ext', {}).get('pic') if s1g else None,
                'pic_ij_d':   s1d.get('ret', {}).get('pic') if s1d else None,
                'pic_ij_g':   s1g.get('ret', {}).get('pic') if s1g else None,
            })
        df_ev = pd.DataFrame(ev_rows)

        col_ev1, col_ev2 = st.columns(2)
        with col_ev1:
            fig_ev = go.Figure()
            fig_ev.add_trace(go.Scatter(x=df_ev['date'], y=df_ev['pic_quad_d'],
                mode='lines+markers', name='Quad Droit',
                line=dict(color=C_ORANGE, width=2.5),
                marker=dict(size=9, color=C_ORANGE, line=dict(color='white', width=2)),
                hovertemplate='<b>Quad Droit</b><br>%{x|%d/%m/%Y}<br>%{y:.1f} Nm<extra></extra>'))
            fig_ev.add_trace(go.Scatter(x=df_ev['date'], y=df_ev['pic_quad_g'],
                mode='lines+markers', name='Quad Gauche',
                line=dict(color=C_GREEN, width=2.5),
                marker=dict(size=9, color=C_GREEN, line=dict(color='white', width=2)),
                hovertemplate='<b>Quad Gauche</b><br>%{x|%d/%m/%Y}<br>%{y:.1f} Nm<extra></extra>'))
            lev = base_layout(title="Évolution Pic Quadriceps (Nm)")
            lev['xaxis']['tickformat'] = '%d/%m/%Y'; lev['yaxis']['title'] = 'Pic couple (Nm)'
            fig_ev.update_layout(**lev); st.plotly_chart(fig_ev, use_container_width=True)
        with col_ev2:
            fig_ev2 = go.Figure()
            fig_ev2.add_trace(go.Scatter(x=df_ev['date'], y=df_ev['pic_ij_d'],
                mode='lines+markers', name='IJ Droit',
                line=dict(color=C_ORANGE, width=2, dash='dot'),
                marker=dict(size=9, symbol='diamond', color=C_ORANGE, line=dict(color='white', width=2)),
                hovertemplate='<b>IJ Droit</b><br>%{x|%d/%m/%Y}<br>%{y:.1f} Nm<extra></extra>'))
            fig_ev2.add_trace(go.Scatter(x=df_ev['date'], y=df_ev['pic_ij_g'],
                mode='lines+markers', name='IJ Gauche',
                line=dict(color=C_GREEN, width=2, dash='dot'),
                marker=dict(size=9, symbol='diamond', color=C_GREEN, line=dict(color='white', width=2)),
                hovertemplate='<b>IJ Gauche</b><br>%{x|%d/%m/%Y}<br>%{y:.1f} Nm<extra></extra>'))
            lev2 = base_layout(title="Évolution Pic Ischios-jambiers (Nm)")
            lev2['xaxis']['tickformat'] = '%d/%m/%Y'; lev2['yaxis']['title'] = 'Pic couple (Nm)'
            fig_ev2.update_layout(**lev2); st.plotly_chart(fig_ev2, use_container_width=True)
