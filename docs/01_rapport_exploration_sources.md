# Rapport d'exploration des sources de données multimodales

**Projet** : Pipeline d'acquisition de données pour le moteur de détection de fake news — CheckIt.AI
**Auteur** : Ingénieur Data Junior
**Étape** : 1 — Exploration et qualification des sources

---

## 1. Objectif

Identifier des sources permettant de récupérer des publications d'actualité **multimodales** (texte + image), avec suffisamment de métadonnées pour être exploitables par un futur détecteur de désinformation. Pour chaque source : type de données, format, langue, qualité des labels vrai/faux, méthode d'extraction, droits d'usage.

Deux sources seront retenues pour l'implémentation du pipeline automatisé (étapes 2 à 5) : **NewsAPI** et des **flux RSS**. Les deux autres sources ci-dessous sont documentées pour l'enrichissement futur du jeu d'entraînement (labels vrai/faux), conformément à la recommandation du brief.

---

## 2. Champs indispensables par publication

Avant de comparer les sources, on fixe le socle minimal qu'une publication doit fournir pour être utilisable par le moteur d'analyse :

| Champ | Rôle |
|---|---|
| `title` | Texte principal à analyser (NLP) |
| `content` / `description` | Corps du texte, contexte |
| `image_url` | Modalité image, doit être associée sans ambiguïté au texte |
| `published_at` | Date de publication (fraîcheur, corrélation d'évènements) |
| `source_domain` | Nom de domaine / éditeur (indice de fiabilité) |
| `url` | Lien vers la publication originale (traçabilité, vérification) |
| `label` (si disponible) | Vrai/faux déclaré ou déduit — rarement présent nativement, à traiter à part |

Ce socle sert de grille de lecture pour qualifier chaque source ci-dessous.

---

## 3. Sources identifiées

### 3.1 NewsAPI (retenue pour l'implémentation)

| Critère | Détail |
|---|---|
| **Type de données** | Texte (titre, description, extrait de contenu) + image (URL de l'image à la une) |
| **Format** | JSON via API REST |
| **Langue** | Multilingue (paramètre `language`, ex. `fr`, `en`) |
| **Qualité des labels** | Aucun label vrai/faux natif — c'est une agrégation de presse généraliste, pas un dataset de fact-checking |
| **Champs disponibles** | `title`, `description`, `content` (tronqué en plan gratuit), `urlToImage`, `publishedAt`, `source.name`, `url`, `author` |
| **Méthode d'extraction** | Appel API REST (`requests`) sur l'endpoint `/v2/everything` ou `/v2/top-headlines`, authentification par clé API (header ou query param) |
| **Droits d'usage** | Plan gratuit (Developer) : usage non commercial, 100 requêtes/jour, contenu limité à des fins de test. Plan payant nécessaire pour la production. |
| **Points de vigilance** | Contenu tronqué à ~200 caractères en plan gratuit ; `urlToImage` parfois `null` ou lien mort — nécessite une validation (étape 2/3) |

**Pourquoi cette source** : canal officiel, pas de scraping, format stable et bien documenté, idéal pour un script robuste et reproductible. Contrepartie : pas de label vrai/faux, donc utile pour la collecte de *candidats* à analyser, pas pour l'entraînement supervisé direct.

---

### 3.2 Flux RSS de sites de presse (retenue pour l'implémentation)

| Critère | Détail |
|---|---|
| **Type de données** | Texte (titre, résumé) + image (souvent en enclosure ou dans le HTML du résumé) |
| **Format** | XML (flux RSS/Atom) |
| **Langue** | Dépend du flux choisi (ex. Le Monde, France Info en français ; BBC, Reuters en anglais) |
| **Qualité des labels** | Aucun label — sources de presse établies, fiabilité éditoriale déclarée mais pas de vérité terrain factuelle |
| **Champs disponibles** | `title`, `summary`/`description`, `link`, `published`, parfois `media_content` ou `enclosure` pour l'image |
| **Méthode d'extraction** | Parsing via `feedparser` (bibliothèque Python dédiée aux flux RSS/Atom), aucune authentification nécessaire |
| **Droits d'usage** | Les flux RSS sont publiés par les éditeurs pour être consommés — usage de lecture/agrégation généralement toléré ; republication commerciale du contenu intégral à vérifier au cas par cas |
| **Points de vigilance** | Structure hétérogène d'un flux à l'autre (l'image n'est pas toujours dans un champ standard, parfois il faut la chercher dans le HTML embarqué) |

**Pourquoi cette source** : complète NewsAPI avec des éditeurs choisis manuellement (contrôle de la qualité éditoriale), gratuite et sans quota, canal officiel par nature.

---

### 3.3 Reddit API — via PRAW (source d'enrichissement)

| Critère | Détail |
|---|---|
| **Type de données** | Texte (titre du post, corps, commentaires) + image (posts de type image ou lien vers image/meme) |
| **Format** | JSON via API REST (wrappée par la librairie `praw`) |
| **Langue** | Majoritairement anglais, dépend des subreddits ciblés |
| **Qualité des labels** | Pas de label vrai/faux direct, mais signal indirect exploitable : score (upvotes/downvotes), flair `misleading`/`unverified` sur certains subreddits, et modération communautaire (posts supprimés pour désinformation) |
| **Champs disponibles** | `title`, `selftext`, `url` (souvent l'image), `created_utc`, `subreddit`, `score`, `num_comments` |
| **Méthode d'extraction** | API REST officielle via `praw`, authentification OAuth2 (client_id/secret d'une "app" Reddit) |
| **Droits d'usage** | Usage encadré par l'API Terms of Service de Reddit (quotas par app, usage commercial soumis à conditions depuis 2023) |
| **Points de vigilance** | Beaucoup de bruit (memes, humour) à filtrer ; forte volatilité du contenu (posts supprimés) ; nécessite un filtrage par subreddit pertinent (ex. `r/worldnews`, `r/PoliticalDiscussion`) |

**Intérêt pour CheckIt.AI** : Reddit est un terrain propice à la désinformation multimodale (images détournées, memes trompeurs), donc pertinent pour enrichir le jeu de données au-delà de l'actualité "propre" de NewsAPI/RSS.

---

### 3.4 Dataset Kaggle — FakeNewsNet (source d'enrichissement / labels)

| Critère | Détail |
|---|---|
| **Type de données** | Texte (articles complets) + image (URLs des images associées) + métadonnées sociales (partages Twitter) |
| **Format** | CSV / JSON (selon la version du dump) |
| **Langue** | Anglais |
| **Qualité des labels** | **Labels vrai/faux fiables** : construit à partir de vérifications par des fact-checkers professionnels (PolitiFact pour la politique, GossipCop pour le divertissement) |
| **Champs disponibles** | `title`, `text`, `url`, `image_url`, `label` (`fake`/`real`), métadonnées de diffusion sociale |
| **Méthode d'extraction** | Téléchargement direct du dataset (pas d'API temps réel) ; un script de collecte associé (fourni par les auteurs) permet de re-scraper les articles depuis les URLs archivées |
| **Droits d'usage** | Disponible pour la recherche académique — vérifier la licence exacte avant tout usage commercial par CheckIt.AI |
| **Points de vigilance** | Dataset statique (pas de flux temps réel), certaines URLs d'origine sont mortes (contenu à archiver ou re-scraper au moment du téléchargement) |

**Intérêt pour CheckIt.AI** : c'est la seule source ici avec un **label vrai/faux vérifié**, indispensable pour entraîner un classifieur supervisé. À utiliser en complément des flux temps réel (NewsAPI/RSS/Reddit) qui fournissent des données non labellisées à classifier en production.

---

## 4. Synthèse comparative

| Source | Modalités | Format | Labels vrai/faux | Temps réel | Méthode |
|---|---|---|---|---|---|
| NewsAPI | Texte + image | JSON (API) | Non | Oui | API REST |
| Flux RSS | Texte + image | XML | Non | Oui | `feedparser` |
| Reddit (PRAW) | Texte + image | JSON (API) | Indirect (score/flair) | Oui | API REST OAuth2 |
| Kaggle FakeNewsNet | Texte + image | CSV/JSON | **Oui (fiable)** | Non (statique) | Téléchargement + re-scraping optionnel |

**Décision** : le pipeline automatisé (étapes 2 à 5) s'appuie sur **NewsAPI + flux RSS** pour la collecte continue et non supervisée de publications candidates. Reddit et FakeNewsNet sont documentés comme sources futures d'enrichissement, notamment pour apporter des labels vrai/faux au jeu de données.

## 5. Critères de sélection des sources implémentées

Le pipeline doit tourner **sans intervention, de façon planifiée** (orchestration Airflow à l'étape 4). Chaque source a donc été évaluée sur sa capacité à être interrogée automatiquement et durablement, pas seulement sur la richesse de ses données.

| Critère | NewsAPI | Flux RSS | Reddit (PRAW) | FakeNewsNet |
|---|---|---|---|---|
| Interrogeable en continu (flux vivant) | Oui | Oui | Oui | **Non** : dump statique |
| Coût de mise en place de l'accès | Faible (clé API) | Nul (aucune authentification) | Moyen (création d'une app OAuth2, client_id/secret) | Faible (téléchargement unique) |
| Canal officiel, sans scraping | Oui | Oui | Oui | Partiel : le re-scraping des URLs d'origine est souvent nécessaire |
| Cadre d'usage compatible avec une start-up | Oui en test, offre payante en production | Oui pour la lecture et l'agrégation | **Incertain** : usage commercial de l'API soumis à accord depuis 2023 | **Incertain** : licence orientée recherche académique |
| Rapport signal/bruit pour de l'actualité | Bon (presse) | Très bon (éditeurs choisis) | Faible (memes, humour, hors-sujet) | Bon |
| Rôle dans le cas d'usage IA | Données à classifier | Données à classifier | Données à classifier | **Données d'entraînement (labels)** |

**Pourquoi Reddit n'est pas implémenté à ce stade** : techniquement accessible, mais le coût d'accès (OAuth2), l'incertitude sur les conditions d'usage commercial et le volume de bruit à filtrer en font une source à intégrer dans un second temps, une fois le pipeline stabilisé. L'architecture le permet sans refonte : un extracteur supplémentaire (`fetch` / `parse` / `extract`) produisant le schéma commun suffit.

**Pourquoi FakeNewsNet n'est pas dans le pipeline** : ce n'est pas un flux mais un jeu de données figé. Il n'a pas sa place dans un DAG exécuté chaque jour. Sa valeur est ailleurs : ses labels vrai/faux vérifiés serviront à **entraîner** le classifieur, tandis que le pipeline alimente le classifieur en publications **à analyser**. Il fera l'objet d'un chargement ponctuel distinct.

## 6. Format de sortie retenu

**JSON** en sortie brute de l'étape d'extraction (structure imbriquée naturelle pour API/RSS, préserve les champs manquants sans colonnes vides), puis conversion en **CSV/Parquet** à l'étape de transformation pour l'analyse tabulaire et l'entraînement du modèle.

## 7. Points de vigilance transverses

- **Désinformation ≠ opinion controversée** : les sources choisies (presse établie, agrégateurs) ne visent pas à collecter des propos subjectifs mais des publications factuelles à vérifier. Le tri fin entre les deux relèvera du modèle de classification, pas de l'étape d'extraction.
- **Association texte-image** : chaque enregistrement doit conserver un lien univoque entre son texte et son image (pas de recombinaison ultérieure possible si perdu à l'extraction).
- **Champs secondaires à ne pas ignorer** : `source_domain`, `url`, `author` — utiles pour scorer la fiabilité déclarée d'une source en amont du NLP.
- **Quotas et légalité** : NewsAPI (100 req/jour en gratuit), Reddit (limites par app OAuth2), RSS (pas de quota mais respect du usage éditorial).
