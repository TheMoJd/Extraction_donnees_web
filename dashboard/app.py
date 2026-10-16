"""Tableau de bord KPI du pipeline CheckIt.AI (étape 5).

Lancement (depuis la racine) : .venv/Scripts/streamlit run dashboard/app.py
Prérequis : le PostgreSQL du docker-compose démarré, CHECKIT_LECTEUR_PASSWORD dans .env.

Connexion avec le rôle checkit_lecteur : lecture seule, le dashboard ne peut rien modifier.
Les seuils affichés sont ceux de src/monitoring/config.py, les mêmes que ceux du DAG.
"""
import os
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
load_dotenv(BASE_DIR / ".env")

from monitoring.config import SEUILS  # noqa: E402  (après l'ajout de src/ au chemin)

QUOTA_NEWSAPI_JOUR = 100

# Couleurs par rôle (palette catégorielle validée daltonisme, ordre fixe).
# La couleur suit l'entité : NewsAPI est toujours bleu, RSS toujours orange.
BLEU, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
COULEURS_SOURCES = alt.Scale(domain=["NewsAPI", "RSS"], range=[BLEU, ORANGE])
COULEURS_ETAPES = alt.Scale(domain=["Extraction", "Transformation", "Chargement"], range=[BLEU, ORANGE, AQUA])
GRIS_SEUIL = "#898781"


# --------------------------------------------------------------------------- données

@st.cache_data(ttl=60)  # relit la base au plus une fois par minute
def charge_donnees() -> tuple[pd.DataFrame, pd.DataFrame]:
    connexion = psycopg2.connect(
        host=os.getenv("CHECKIT_DB_HOST", "localhost"),
        port=int(os.getenv("CHECKIT_DB_PORT", "5435")),
        dbname="checkit",
        user="checkit_lecteur",
        password=os.getenv("CHECKIT_LECTEUR_PASSWORD", ""),
    )
    try:
        executions = lit_requete(connexion, "SELECT * FROM executions ORDER BY debut")
        publications = lit_requete(
            connexion,
            "SELECT source_type, count(*) AS nb, count(*) FILTER (WHERE image_valide) AS nb_images, "
            "max(date_publication) AS plus_recente FROM publications GROUP BY source_type",
        )
    finally:
        connexion.close()
    return executions, publications


def lit_requete(connexion, requete: str) -> pd.DataFrame:
    """Exécute une requête et retourne un DataFrame (pd.read_sql n'est garanti qu'avec SQLAlchemy)."""
    with connexion.cursor() as curseur:
        curseur.execute(requete)
        colonnes = [c.name for c in curseur.description]
        return pd.DataFrame(curseur.fetchall(), columns=colonnes)


def prepare(executions: pd.DataFrame) -> pd.DataFrame:
    df = executions.copy()
    df["debut"] = pd.to_datetime(df["debut"], utc=True).dt.tz_convert("Europe/Paris")
    df["run"] = df["debut"].dt.strftime("%d/%m %H:%M")
    df["taux_valides"] = df["nb_valides"] / df["nb_extraits"]
    df["taux_images"] = df["nb_images_valides"] / df["nb_valides"]
    df["duree_totale_s"] = df[["duree_extraction_s", "duree_transformation_s", "duree_chargement_s"]].sum(axis=1)
    return df


def pourcent(valeur) -> str:
    return "—" if pd.isna(valeur) else f"{valeur:.0%}"


# --------------------------------------------------------------------------- graphiques

def courbe_taux(df: pd.DataFrame, colonne: str, seuil: float, titre: str) -> alt.LayerChart:
    """Un taux par run (une seule série, donc pas de légende) + la ligne du seuil d'alerte."""
    base = alt.Chart(df).encode(
        x=alt.X("run:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
    )
    ligne = base.mark_line(color=BLEU, strokeWidth=2).encode(
        y=alt.Y(f"{colonne}:Q", title=None, scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
    )
    points = base.mark_point(color=BLEU, filled=True, size=70).encode(
        y=f"{colonne}:Q",
        tooltip=[alt.Tooltip("run:N", title="Run"), alt.Tooltip(f"{colonne}:Q", title=titre, format=".1%")],
    )
    regle = alt.Chart(pd.DataFrame({"seuil": [seuil]})).mark_rule(
        color=GRIS_SEUIL, strokeDash=[4, 4], strokeWidth=1
    ).encode(y="seuil:Q")
    etiquette = alt.Chart(pd.DataFrame({"seuil": [seuil], "texte": [f"seuil d'alerte {seuil:.0%}"]})).mark_text(
        align="left", dx=4, dy=-6, color=GRIS_SEUIL, fontSize=11
    ).encode(x=alt.value(0), y="seuil:Q", text="texte:N")
    return (ligne + points + regle + etiquette).properties(height=220)


def barres_empilees(df: pd.DataFrame, colonnes: dict, echelle: alt.Scale, titre_y: str, fmt: str) -> alt.Chart:
    """Barres empilées par run ; une couleur par catégorie, avec légende."""
    long = df.melt(id_vars=["run"], value_vars=list(colonnes), var_name="cle", value_name="valeur")
    long["categorie"] = long["cle"].map(colonnes)
    return (
        alt.Chart(long)
        .mark_bar(size=22, stroke="white", strokeWidth=2)  # 2 px d'écart entre segments
        .encode(
            x=alt.X("run:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("valeur:Q", stack="zero", title=titre_y),
            color=alt.Color("categorie:N", scale=echelle, title=None, legend=alt.Legend(orient="top")),
            order=alt.Order("cle:N"),
            tooltip=[
                alt.Tooltip("run:N", title="Run"),
                alt.Tooltip("categorie:N", title="Catégorie"),
                alt.Tooltip("valeur:Q", title=titre_y, format=fmt),
            ],
        )
        .properties(height=240)
    )


# --------------------------------------------------------------------------- page

st.set_page_config(page_title="Santé du pipeline CheckIt.AI", page_icon="📰", layout="wide")
st.title("Santé du pipeline CheckIt.AI")
st.caption(
    "Chaque jour, le pipeline collecte des articles d'actualité (texte + image), les nettoie "
    "et les range dans la base. Cette page indique s'il a bien fonctionné, à quelle vitesse et à quel coût."
)

try:
    executions, publications = charge_donnees()
except psycopg2.OperationalError as exc:
    st.error(f"Impossible de joindre la base de données. Le conteneur PostgreSQL est-il démarré ?\n\n{exc}")
    st.stop()

if executions.empty:
    st.info("Aucun run enregistré pour l'instant. Déclenche le DAG checkit_etl dans Airflow.")
    st.stop()

df = prepare(executions)
dernier = df.iloc[-1]

# --- 1. Verdict du dernier run ----------------------------------------------------------
st.subheader("Dernier run")
alertes = list(dernier["alertes"] or [])
quand = dernier["debut"].strftime("%d/%m/%Y à %H:%M")
if dernier["statut"] == "echec":
    st.error(f"❌ **Échec** — run du {quand}, étape « {dernier['etape_en_echec']} »")
elif alertes:
    st.warning(f"⚠️ **Terminé avec {len(alertes)} alerte(s)** — run du {quand}")
else:
    st.success(f"✅ **Conforme** — run du {quand}, aucune alerte")
for alerte in alertes:
    st.markdown(f"- {'❌' if alerte.startswith('CRITIQUE') else '⚠️'} {alerte}")

# --- 2. Indicateurs clés ----------------------------------------------------------------
reussis = df[df["statut"] == "succes"]
moyenne_valides = reussis["taux_valides"].mean()
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Publications en base", f"{int(publications['nb'].sum()):,}".replace(",", " "),
          help="Articles uniques stockés, toutes sources confondues.")
k2.metric("Données valides (dernier run)", pourcent(dernier["taux_valides"]),
          help=f"Part des articles collectés qui passent les contrôles qualité. Alerte sous {SEUILS['taux_valides_min']:.0%}.")
k3.metric("Images accessibles (dernier run)", pourcent(dernier["taux_images"]),
          help=f"Part des articles valides dont l'image s'affiche réellement. Alerte sous {SEUILS['taux_images_valides_min']:.0%}.")
k4.metric("Durée du dernier run", "—" if pd.isna(dernier["duree_totale_s"]) else f"{dernier['duree_totale_s']:.0f} s",
          help=f"Temps total des 3 étapes. Alerte au-delà de {SEUILS['duree_totale_max_s']} s.")
k5.metric("Runs réussis", pourcent(len(reussis) / len(df)), help=f"Sur les {len(df)} runs enregistrés.")

# --- 3. Précision -------------------------------------------------------------------------
st.subheader("Précision des données")
st.caption("Au-dessus de la ligne pointillée, tout va bien ; en dessous, une alerte est levée.")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Part de données valides par run**")
    st.altair_chart(courbe_taux(reussis, "taux_valides", SEUILS["taux_valides_min"], "Données valides"),
                    width="stretch")
with c2:
    st.markdown("**Part d'images accessibles par run**")
    st.altair_chart(courbe_taux(reussis, "taux_images", SEUILS["taux_images_valides_min"], "Images accessibles"),
                    width="stretch")

# --- 4. Volume ----------------------------------------------------------------------------
st.subheader("Volume collecté")
v1, v2 = st.columns(2)
with v1:
    st.markdown("**Articles collectés par source**")
    st.altair_chart(barres_empilees(reussis, {"nb_newsapi": "NewsAPI", "nb_rss": "RSS"},
                                    COULEURS_SOURCES, "Articles", "d"), width="stretch")
with v2:
    st.markdown("**Nouveaux articles ajoutés à la base**")
    st.caption("Les articles déjà vus lors d'un run précédent ne sont pas recomptés.")
    st.altair_chart(
        alt.Chart(reussis).mark_bar(size=22, color=BLEU, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("run:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("nb_nouvelles:Q", title="Nouveaux articles"),
            tooltip=[alt.Tooltip("run:N", title="Run"), alt.Tooltip("nb_nouvelles:Q", title="Nouveaux"),
                     alt.Tooltip("nb_deja_presentes:Q", title="Déjà en base")],
        ).properties(height=240),
        width="stretch",
    )

# --- 5. Rapidité --------------------------------------------------------------------------
st.subheader("Rapidité")
st.caption("Temps passé dans chaque étape. La transformation domine : elle vérifie une à une que chaque image est accessible.")
st.altair_chart(
    barres_empilees(reussis, {"duree_extraction_s": "Extraction", "duree_transformation_s": "Transformation",
                              "duree_chargement_s": "Chargement"}, COULEURS_ETAPES, "Secondes", ".1f"),
    width="stretch",
)

# --- 6. Coût ------------------------------------------------------------------------------
st.subheader("Coût et ressources")
aujourdhui = pd.Timestamp.now(tz="UTC").normalize()
appels_jour = int(executions.loc[pd.to_datetime(executions["debut"], utc=True) >= aujourdhui, "appels_newsapi"].fillna(0).sum())
r1, r2, r3 = st.columns(3)
with r1:
    st.metric("Quota NewsAPI utilisé aujourd'hui", f"{appels_jour} / {QUOTA_NEWSAPI_JOUR}",
              help=f"Plan gratuit : {QUOTA_NEWSAPI_JOUR} requêtes par jour. Alerte au-delà de {SEUILS['appels_newsapi_jour_max']}.")
    st.progress(min(appels_jour / QUOTA_NEWSAPI_JOUR, 1.0))
r2.metric("Mémoire maximale d'une étape", "—" if pd.isna(dernier["memoire_max_mo"]) else f"{dernier['memoire_max_mo']:.0f} Mo",
          help="Pic de mémoire vive du processus le plus gourmand, au dernier run.")
r3.metric("Stockage des fichiers intermédiaires", f"{df['taille_fichiers_ko'].sum() / 1024:.1f} Mo",
          help="Cumul des fichiers bruts (JSON) et transformés (CSV) produits par les runs enregistrés.")

# --- 7. Détail ----------------------------------------------------------------------------
with st.expander("Historique détaillé des runs (tableau)"):
    tableau = df[["run", "statut", "nb_newsapi", "nb_rss", "nb_valides", "taux_valides", "taux_images",
                  "nb_nouvelles", "duree_totale_s", "alertes"]].iloc[::-1]
    st.dataframe(
        tableau, hide_index=True, width="stretch",
        column_config={
            "run": "Run", "statut": "Statut", "nb_newsapi": "NewsAPI", "nb_rss": "RSS",
            "nb_valides": "Valides", "nb_nouvelles": "Nouveaux",
            "taux_valides": st.column_config.NumberColumn("% valides", format="percent"),
            "taux_images": st.column_config.NumberColumn("% images", format="percent"),
            "duree_totale_s": st.column_config.NumberColumn("Durée (s)", format="%.0f"),
            "alertes": "Alertes",
        },
    )

with st.expander("Seuils d'alerte en vigueur"):
    st.table(pd.DataFrame([
        ("Données valides", f"moins de {SEUILS['taux_valides_min']:.0%}", "Attention"),
        ("Images accessibles", f"moins de {SEUILS['taux_images_valides_min']:.0%}", "Attention"),
        ("Articles collectés", f"moins de {SEUILS['nb_extraits_min']}", "Attention"),
        ("Une source ne renvoie rien", "0 article NewsAPI ou RSS", "Critique"),
        ("Durée d'un run", f"plus de {SEUILS['duree_totale_max_s']} s", "Attention"),
        ("Appels NewsAPI dans la journée", f"plus de {SEUILS['appels_newsapi_jour_max']}", "Attention"),
        ("Échec d'une étape", "après 2 nouvelles tentatives", "Critique"),
    ], columns=["Indicateur", "Alerte si", "Niveau"]))
