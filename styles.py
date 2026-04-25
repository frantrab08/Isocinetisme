import plotly.graph_objects as go

# ── Palette ───────────────────────────────────────────────────────────────────
C_BLUE   = '#0066FF'
C_GREEN  = '#00C896'
C_ORANGE = '#FF6B35'
C_PURPLE = '#7B5EA7'
C_RED    = '#FF4757'
C_YELLOW = '#FFB800'
C_GRAY   = '#8C95A6'
COLORS   = [C_BLUE, C_ORANGE, C_GREEN, C_PURPLE, C_RED, C_YELLOW]

PLOT_BG  = '#FFFFFF'
PAPER_BG = '#FFFFFF'
GRID_COL = '#F0F2F5'
TEXT_COL = '#4A5568'
FONT     = 'Inter, sans-serif'

# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] {
    background: #F7F9FC;
    border-right: 1px solid #E2E8F0;
}

.main { background: #F7F9FC; }
.main .block-container { padding-top: 1.5rem; max-width: 1400px; }

/* Navigation boutons */
div[data-testid="stRadio"] > div {
    gap: 8px;
}
div[data-testid="stRadio"] label {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 8px !important;
    padding: 10px 16px !important;
    font-weight: 500;
    font-size: 13px;
    transition: all 0.15s;
    cursor: pointer;
    width: 100%;
}
div[data-testid="stRadio"] label:hover {
    border-color: #0066FF;
    background: #EBF3FF;
}
div[data-testid="stRadio"] label[data-checked="true"] {
    background: #0066FF !important;
    border-color: #0066FF !important;
    color: white !important;
}

/* Header page */
.page-header {
    background: linear-gradient(135deg, #0066FF 0%, #0044CC 100%);
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 20px;
    color: white;
}
.page-header h1 { font-size: 24px; font-weight: 700; margin: 0; color: white; }
.page-header p  { font-size: 13px; opacity: 0.85; margin: 4px 0 0; color: white; }

/* KPI cards */
.kpi-row { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.kpi-card {
    flex: 1; min-width: 140px;
    background: white;
    border-radius: 12px;
    padding: 16px 20px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    border-top: 3px solid var(--accent, #0066FF);
}
.kpi-label {
    font-size: 10px; font-weight: 600;
    letter-spacing: 1.2px; text-transform: uppercase;
    color: #8C95A6; margin-bottom: 6px;
}
.kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 26px; font-weight: 500;
    color: #1A202C; line-height: 1;
}
.kpi-unit { font-size: 12px; color: #8C95A6; font-family: Inter; margin-left: 3px; }
.kpi-delta { font-size: 11px; margin-top: 6px; font-weight: 500; }
.up   { color: #00C896; }
.down { color: #FF4757; }
.neu  { color: #8C95A6; }

/* Section titles */
.stitle {
    font-size: 11px; font-weight: 700;
    letter-spacing: 1.5px; text-transform: uppercase;
    color: #0066FF; margin: 20px 0 10px;
    display: flex; align-items: center; gap: 8px;
}
.stitle::after { content:''; flex:1; height:1px; background:#E2E8F0; }

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 600;
}
.badge-test  { background:#F0FDF9; color:#00C896; border:1px solid #B3F0E0; }
.badge-renfo { background:#FFF8EB; color:#FFB800; border:1px solid #FFE4A0; }
.badge-right { background:#FFF0EB; color:#FF6B35; border:1px solid #FFD4C2; }
.badge-left  { background:#EBF3FF; color:#0066FF; border:1px solid #C2D9FF; }
.badge-warn  { background:#FFF5F5; color:#FF4757; border:1px solid #FFC0C5; }
.badge-ok    { background:#F0FDF9; color:#00C896; border:1px solid #B3F0E0; }
</style>
"""

# ── Plotly layout ─────────────────────────────────────────────────────────────
def base_layout(height=370, title=None):
    l = dict(
        height=height,
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(family=FONT, color=TEXT_COL, size=12),
        margin=dict(t=40 if title else 24, b=48, l=56, r=16),
        hovermode='x unified',
        hoverlabel=dict(bgcolor='white', bordercolor='#E2E8F0',
                        font=dict(family=FONT, color='#1A202C', size=12)),
        xaxis=dict(gridcolor=GRID_COL, linecolor='#E2E8F0', zeroline=False,
                   tickfont=dict(color=TEXT_COL), title_font=dict(color=TEXT_COL)),
        yaxis=dict(gridcolor=GRID_COL, linecolor='#E2E8F0', zeroline=False,
                   tickfont=dict(color=TEXT_COL), title_font=dict(color=TEXT_COL)),
        legend=dict(bgcolor='white', bordercolor='#E2E8F0', borderwidth=1,
                    font=dict(color='#1A202C', size=12))
    )
    if title:
        l['title'] = dict(text=title, font=dict(size=13, color='#1A202C', family=FONT))
    return l

# ── Helpers HTML ──────────────────────────────────────────────────────────────
def delta_html(val, ref):
    if not ref or ref == 0:
        return '<span class="neu">— 1er point</span>'
    pct = ((val - ref) / abs(ref)) * 100
    if pct > 0.5:   return f'<span class="up">▲ +{pct:.1f}%</span>'
    elif pct < -0.5: return f'<span class="down">▼ {pct:.1f}%</span>'
    else:            return '<span class="neu">= Stable</span>'

def kpi(label, value, unit="", delta="", accent=C_BLUE):
    return f"""<div class="kpi-card" style="--accent:{accent}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}<span class="kpi-unit">{unit}</span></div>
        <div class="kpi-delta">{delta}</div>
    </div>"""

def section(title):
    import streamlit as st
    st.markdown(f'<div class="stitle">{title}</div>', unsafe_allow_html=True)
