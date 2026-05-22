# 🦵 Isocinetisme

> ⚠️ **Projet en cours de développement** — fonctionnalités actives, code en évolution active.

![Python](https://img.shields.io/badge/Python-3.x-blue?style=flat-square) ![Streamlit](https://img.shields.io/badge/Streamlit-cloud-red?style=flat-square) ![PostgreSQL](https://img.shields.io/badge/NeonDB-PostgreSQL-336791?style=flat-square) ![Plotly](https://img.shields.io/badge/Plotly-interactive-3F4F75?style=flat-square) ![Status](https://img.shields.io/badge/status-en%20cours-orange?style=flat-square)

🔗 **[isocinetisme.streamlit.app](https://isocinetisme.streamlit.app/)**

---

## 🎯 Contexte & motivation

Utilisateur régulier d'un appareil isocinétique dans le cadre de mon suivi physique, j'ai voulu aller bien plus loin que les exports bruts du logiciel propriétaire.

L'isocinétisme mesure la force musculaire à vitesse angulaire constante (ex. 60°/s, 240°/s) tout au long du mouvement. Les données produites — pic de couple, ratio agoniste/antagoniste, déficit droite/gauche, ratio mixte — sont des indicateurs cliniques utilisés en médecine du sport de haut niveau (protocoles CNF Clairefontaine, FFF).

Ce projet est une tentative de **rendre ces données exploitables visuellement**, en automatisant leur traitement de A à Z : des fichiers CSV bruts jusqu'à un dashboard interactif déployé en ligne. L'objectif est aussi de **montrer un pipeline data complet**, digne d'un projet data analyst, sur un domaine que je pratique et que je comprends cliniquement.

---

## 🔄 Pipeline — de A à Z

```
📄 Fichiers CSV bruts   →   🔧 Parsing & nettoyage   →   🗄️ NeonDB (PostgreSQL)   →   📊 Dashboard Streamlit
   (export appareil)          (pandas · Python)               (cloud serverless)           (app en ligne)
```

Les noms de fichiers encodent toutes les métadonnées :

```
BART_ François 03_03_2026 19_39_43 30 10 Right 2.CSV
 ↑ nom/prénom   ↑ date/heure         ↑vitesse ↑reps ↑côté ↑série
```

Le script `import_iso.py` parse le nom, nettoie les données brutes, normalise les statuts machine (`'1'`, `'1.0'`, `'Actif'`…), et insère tout en base avec gestion des conflits (`ON CONFLICT DO NOTHING`).

---

## 🔬 Bases scientifiques

Les indicateurs calculés s'appuient sur les protocoles utilisés en médecine du sport de haut niveau.

**Indicateurs implémentés :**

- **Pic de couple (Peak Torque)** — sommet de la courbe force/position, exprimé en Nm et rapporté au poids de corps (Nm/kg)
- **Travail total (Énergie)** — calculé par intégration numérique (méthode des trapèzes) : `∑ |couple| × |vitesse| × π/180 × Δt`, exprimé en Joules
- **Déficit droite/gauche** — asymétrie en %, seuil de significativité clinique : 10–15 % selon la littérature
- **Ratio IJ/Q concentrique** à 60°/s et 240°/s — ratio agoniste/antagoniste, facteur de risque si < 0,47 (Dauty, MLTJ 2016)
- **Coefficient de variation** — validité du test : CV < 10 % = bonne reproductibilité

**Seuils cliniques de référence (protocole CNF Clairefontaine) :**

- Déficit Quadriceps < 16 % et IJ symétrique à 60°/s → critères de reprise d'entraînement post-LCA
- Ratio mixte (IJ exc 30°/s / Q conc 240°/s) < 0,9 → signal d'alerte pour lésions récidivantes des IJ
- Déséquilibre non corrigé en début de saison → 4–5× plus de risques de lésion musculaire (Croisier et al., Am J Sports Med 2008)

**Vitesses utilisées dans les protocoles :**
- 60°/s → force maximale
- 240°/s → puissance / explosivité
- 30°/s en excentrique → renforcement cicatriciel

📄 *Référence principale : Tamalet & Gaspar — [Pratique de l'isocinétisme à Clairefontaine](https://media-cnf-centre-medical.fff.fr/uploads/document/4de6f9a8baff488483c4eaeb6218c7ba.pdf), CNF / FFF, DIU Pathologies du Football 2020-2021*

---

## ⚙️ Stack technique

| Composant | Technologie |
|---|---|
| Interface | Streamlit |
| Base de données | NeonDB · PostgreSQL serverless |
| Langage | Python 3 |
| Visualisation | Plotly |
| Import / nettoyage | pandas, psycopg2 |
| Déploiement | Streamlit Cloud |
| Connexion BDD | psycopg2 + `st.secrets` / `.env` |

---

## 📂 Structure du projet

```
isocinetisme/
├── app.py                # Entrée Streamlit, routing, sidebar
├── db.py                 # Toutes les requêtes SQL (fonctions cachées via @st.cache_data)
├── styles.py             # CSS global, palette couleurs, helpers KPI/section
├── import_iso.py         # Script d'import CSV → NeonDB
├── diagnostic.py         # Script utilitaire de debug BDD
├── page_patient.py       # Page fiche patient & historique séances
├── page_tests.py         # Page évolution des tests isocinétiques
├── page_comparaison.py   # Page comparaison multi-tests (dates + côtés)
├── page_renfo.py         # Page séances de renforcement
├── page_analyse.py       # Page analyse détaillée rep par rep
└── requirements.txt
```

---

## 📊 Fonctionnalités actuelles

### 👤 Fiche patient
- KPIs globaux : nombre de séances totales, tests ISO, séances de renforcement, poids
- Historique des séances filtrable par type (Test ISO / Renforcement) et par côté

### 🏥 Tests isocinétiques
- Détection automatique des tests (séances à exactement 3 séries : 60°/s × 3 reps, 30°/s × 3 reps, 240°/s × 20 reps)
- Évolution des pics de couple dans le temps
- Comparaison côté droit / côté gauche sur le même graphique

### 📊 Comparaison multi-tests
- Sélection libre de plusieurs tests (dates et côtés au choix)
- Tableau comparatif : pic de couple Quad/IJ, ratio IJ/Q, valeurs normalisées au poids
- Courbes de la meilleure répétition superposées par test
- Toutes les répétitions superposées par test
- Graphique de déficit D/G dans le temps avec seuil clinique (-10 %) matérialisé

### 💪 Renforcement
- Distinction automatique renforcement / test (nombre de séries ≠ 3)
- KPIs : couple max, énergie totale, record, durée du suivi
- Évolution globale par séance avec droite de tendance (régression linéaire)
- Vue "série par série" : une ligne par séance (axe X = numéro de série)
- Évolution dans le temps par série
- Tableau croisé dynamique (pivot) couple max / énergie par série et par date

### 🔬 Analyse détaillée
- Vue d'ensemble de la séance : tableau récapitulatif par série (couple max, énergie, durée, reps actives)
- Zoom sur une série : courbes couple/position et couple/temps rep par rep
- Identification de la meilleure répétition (courbe clinique de référence)
- Stats par répétition : couple max, durée, amplitude, énergie
- Filtres interactifs : sélection des reps, Extension seule / Retour seul

---

## 🗺️ Objectifs à venir

- [ ] Calcul et affichage des ratios IJ/Q (concentrique et mixte) avec interprétation clinique automatisée
- [ ] Détection des asymétries critiques (déficit > 15 %) avec alertes visuelles
- [ ] Intégration de valeurs normatives (âge, sexe, sport) pour contextualiser les résultats
- [ ] Génération de rapports PDF par patient (compte-rendu de test exportable)
- [ ] Gestion multi-patients avec authentification (usage en cabinet kiné)
- [ ] Export Excel pour partage avec le corps médical

---

## 🔐 Sécurité

Le fichier `.env` (avec la `DATABASE_URL` NeonDB) n'est jamais commité — protégé par `.gitignore`.  
En production (Streamlit Cloud), les secrets sont gérés via **Settings → Secrets** (`st.secrets`).

---

## 👤 Auteur

François Bart — projet personnel dans le cadre d'un suivi isocinétique en kinésithérapie du sport.
