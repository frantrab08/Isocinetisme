import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# DEBUG TEMPORAIRE
try:
    st.write("SECRET:", st.secrets["DATABASE_URL"][:20], "...")
except Exception as e:
    st.write("ERREUR SECRET:", e)

from styles import CSS
from db import get_clients

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from styles import CSS
from db import get_clients

st.set_page_config(
    page_title="IsoTrack",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(CSS, unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏋️‍♂️ IsoTrack")
    st.markdown("*Suivi isocinétique*")
    st.markdown("---")

    clients = get_clients()
    if clients.empty:
        st.error("Aucun client en base.")
        st.stop()

    client_opts = {
        f"{r['prenom']} {r['nom']}": (r['id'], r['poids_kg'])
        for _, r in clients.iterrows()
    }
    client_choisi = st.selectbox("👤 Patient", list(client_opts.keys()))
    client_id, poids_kg = client_opts[client_choisi]

    st.markdown("---")

    cote = st.radio(
        "🦵 Genou",
        ["Right", "Left"],
        format_func=lambda x: "🔴 Droit" if x == "Right" else "🔵 Gauche"
    )

    st.markdown("---")

    page = st.radio(
        "📂 Navigation",
        ["👤 Patient", "🏥 Test ISO", "📊 Comparaison Tests", "💪 Renforcement", "🔬 Analyse détaillée"],
        index=0
    )

    st.markdown("---")
    st.markdown(
        "<div style='font-size:11px;color:#8C95A6'>IsoTrack v2.0<br>NeonDB · Streamlit</div>",
        unsafe_allow_html=True
    )

# ── Routing ───────────────────────────────────────────────────────────────────
args = (client_id, client_choisi, cote, poids_kg)

if page == "👤 Patient":
    import page_patient
    page_patient.show(*args)

elif page == "🏥 Test ISO":
    import page_tests
    page_tests.show(*args)

elif page == "📊 Comparaison Tests":
    import page_comparaison
    page_comparaison.show(*args)

elif page == "💪 Renforcement":
    import page_renfo
    page_renfo.show(*args)

elif page == "🔬 Analyse détaillée":
    import page_analyse
    page_analyse.show(*args)
