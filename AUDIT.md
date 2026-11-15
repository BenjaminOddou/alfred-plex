# Audit & refonte — Alfred Plex 3.0 → 3.3

Ce document résume l'audit du code 2.4.2, la refonte 3.0.0 et les nouveautés 3.1.0 (section 10), 3.2.0 (section 11) et 3.3.0 (section 12).

## 1. Constat de départ (2.4.2)

| Domaine | Constat |
| --- | --- |
| Structure | 15 scripts Python au même niveau, code dupliqué (connexion serveur, gestion d'erreur, découpage des arguments), état global modifié via `globals()`, aucun test réel. |
| Navigation | État encodé dans des chaînes positionnelles (`_rerun;id;level;type;key`, séparateurs `ǀ`), « retour » calculé par `level - 1`, texte interne visible dans la barre Alfred (`1;streams;…`). |
| info.plist | 133 objets, 95 connexions (27 *Call External Trigger*, 17 *Replace*, 16 *Conditional*, 8 *Split*…). |
| Dépendances | python-plexapi 4.17.0, notificator ancien. |

## 2. Bugs corrigés

| # | Bug 2.4.2 | Correction |
| --- | --- | --- |
| 1 | `search_stream.py` : f-string avec guillemets imbriqués → **SyntaxError sur Python < 3.12**, le streaming ne marchait pas avec le Python système. | Code réécrit (`commands/media.py`). |
| 2 | Recherche vide (vue par défaut) : la boucle écrasait les résultats → **seule la dernière section** était affichée. | Résultats agrégés sur toutes les sections et tous les serveurs. |
| 3 | Plex Help › Filtres : la boucle écrasait la connexion → **seul le dernier serveur** était listé. | Tous les serveurs (en parallèle). |
| 4 | « Scanning: True » seulement si *toutes* les sections scannaient (`any(s.refreshing == False)`). | `any(s.refreshing)`. |
| 5 | Raccourci « Desactivated » = chaîne `"False"` (vraie en Python) : actions calculées quand même. | `False`/vide = désactivé, libellé « Disabled ». |
| 6 | **Chaque mise à jour supprimait `accounts.json`, `servers.json`, `alias.json`** (re-connexion obligatoire). | Seul le cache est vidé, les données sont gardées, les nouveaux alias sont fusionnés. |
| 7 | Infuse : URL du flux non encodée → le token (`?X-Plex-Token=…`) était perdu. | URL encodée. |
| 8 | Recherche `AC/DC` → recherche « AC » de type « DC ». | Le suffixe n'est un type que s'il est connu. |
| 9 | Filtres découpés sur chaque `/` → valeurs contenant `/` cassées. | Découpage seulement avant `nom=`. |
| 10 | Arrêt du lecteur via `ps aux \| grep vlc \| kill` : tue `grep`, rate `VLC` (casse), peut tuer d'autres process. | `pkill -x VLC` / `pkill -x IINA`. |
| 11 | Vérifie l'app avec `mdfind` mais lance la CLI (`vlc`) → incohérent. | Vérifie la CLI (Homebrew inclus dans le PATH). |
| 12 | `get_plex_account` renvoie `None` en cas d'erreur → `AttributeError` plus loin. | Erreurs explicites (`PlexError`) affichées à l'utilisateur. |
| 13 | Historique : `originallyAvailableAt.year` plante si la date manque. | `year` optionnel. |
| 14 | Messages d'erreur avec la variable de boucle `obj` (mauvais serveur cité). | Nom du bon serveur. |
| 15 | Preset sans `/` dans « titre/sous-titre » → `IndexError`. | Sous-titre optionnel. |

## 3. Performance

| Avant | Après |
| --- | --- |
| `container_size = 15` dans la config plexapi : **toute liste paginée par 15** (watchlist de 200 éléments = 14 requêtes). | Taille par défaut, limite via `maxresults`. |
| Appel `users()` vers plex.tv à **chaque frappe** pour valider le compte en cache. | Compte en cache 24 h, sans validation ; une erreur réelle remonte. |
| Watchlist téléchargée à chaque frappe, pour chaque serveur. | Cache 10 min, mis à jour localement après ajout/retrait. |
| Requêtes par ligne : piste → `album()` ×2 + `album().tracks()`, album → `tracks()`, playlist → `items()`… (N+1). | **0 requête par ligne** (`leafCount`, `parentTitle`…). Test : recherche = 2 requêtes au total. |
| Serveurs puis sections interrogés un par un, même les sections incompatibles avec le `libtype`. | Serveurs et sections **en parallèle**, sections filtrées par type. |
| `alias.json` relu sur le disque plusieurs fois par ligne. | Lu une fois par exécution. |
| Page serveur : `isLatest()` + `checkForUpdate()` = 2 vérifications **forcées** vers plex.tv. | 1 lecture du statut en cache du serveur. |
| Recherche par GUID : 1 requête par section. | `library.search(guid=…)` : 1 requête par serveur. |
| plexapi importé pour chaque page (menu, presets…). | Import paresseux : menu/presets/aide instantanés. |
| Connexion aux serveurs d'un compte une par une (timeout 2 s chacun). | En parallèle. |
| `config.ini` réécrit à chaque exécution, log sans limite. | Écrit seulement si changé, log tournant (512 Ko × 3). |

## 4. Sécurité

| Risque | Correction |
| --- | --- |
| `eval()` sur la vue par défaut, les `advancedFilters` (donc les presets) et les valeurs de réglages serveur → **exécution de code arbitraire**. | `ast.literal_eval` / JSON : les valeurs sont lues, jamais exécutées (tests dédiés). |
| `os.system()` avec titres de médias interpolés → **injection shell** via un titre malveillant d'un serveur partagé (`$(…)`, backticks). | `subprocess` avec liste d'arguments, sans shell. |
| Token Plex écrit dans le log de debug du lecteur. | Masqué (`***`). |
| Mot de passe tapé en clair dans Alfred. | **3.1 : OAuth uniquement** (« Sign in with Plex » dans le navigateur), plus aucun mot de passe ni token tapé dans Alfred. |

## 5. python-plexapi 4.18.3

- **Python 3.10 minimum** (exigence de plexapi 4.18). `main.py` affiche un message clair si Python est trop vieux,
  et les scripts cherchent `python3` dans Homebrew (`/opt/homebrew/bin`, `/usr/local/bin`) avant le système.
- Connexion OAuth : `MyPlexPinLogin(oauth=True)`, `oauthUrl()`, `waitForLogin()`.
- Watchlist : `addToWatchlist()` / `removeFromWatchlist()` officiels (au lieu de requêtes HTTP faites à la main).
- Sessions : `PlexSession.stop(reason)` pour terminer une lecture.
- `includeGuids` par défaut (4.18) : l'identifiant TMDB est lu directement dans les résultats → appel du
  workflow *Movie and TV Show Search* sans requête supplémentaire.
- `library.search(guid=…)`, `TwoFactorRequired` (message « OTP requis »), connexions IPv6 (`resources()` 4.18).
- Discover passe par la session authentifiée de plexapi (`account.query`) au lieu de `requests` brut.

## 6. Navigation

- Chaque page a un chemin (`servers/<id>/settings/general`) : **Retour = vraie page parente**, avec fil d'Ariane
  dans le sous-titre ; **⌘⏎ sur Retour = menu principal**.
- Plus aucun texte interne dans la barre Alfred : l'état passe par des variables (`action`, `nav`…).
- Après une action (watchlist, preset, alias, réglage…) on revient **sur la même page avec la même recherche**.
- Pages de **confirmation Oui / Annuler** au lieu de taper `yes`.
- Pages Alfred filtrées en tapant (menu compris : `plex serv` → Plex Media Servers).
- Depuis Discover, la recherche sur les serveurs revient aux résultats Discover ; depuis la watchlist d'un compte,
  ⏎ cherche le média sur les serveurs.
- Bonus : aperçu de l'affiche (Quick Look), ⌘C copie le titre, sessions rafraîchies toutes les 5 s, fichier de
  log accessible depuis Plex Help.

## 7. info.plist

19 objets / 18 connexions (au lieu de 133 / 95), diagramme en étoile sans croisement :

```
Triggers + Script Filters ─▶ Router {var:action} ─▶ browse · search · discover · ask · run · open · reveal · mtv
                                   ▲                                                  │
                                   └──────────── dispatch ◀── Run Script ◀────────────┘
```

Chaque objet a une note, les objets Python sont en jaune, le Router en bleu. La configuration utilisateur est
conservée (mêmes variables, valeurs existantes compatibles) avec des descriptions ajoutées.

## 8. Tests

`tests/` : **196 tests** (pytest), sans réseau. plexapi 4.18 analyse de vrais XML Plex servis par une fausse
session HTTP : les noms d'attributs et le nombre de requêtes sont vérifiés. `test_workflow.py` vérifie aussi que
le diagramme et le code sont cohérents (toutes les actions sont routées, tous les scripts appellent un mode
existant, toutes les icônes existent…). Passent sur Python 3.10 et 3.13.

```shell
python3 -m pip install pytest ruff
python3 -m pytest
```

## 9. À vérifier sur le Mac (non testable ici : pas d'Alfred sous Linux)

1. `plex` ouvre le menu, `plex serv` filtre bien.
2. Navigation aller/retour dans Servers, Accounts, Presets, Help (variables passées par les *Call External Trigger*).
3. « Sign in with Plex » : le navigateur s'ouvre, le compte et ses serveurs s'ajoutent.
4. Un prompt (ex. modifier un alias) puis le retour sur la page.
5. Streaming VLC / IINA / Infuse, notifications (Notificator recompile son app au premier lancement).

## 10. Version 3.1.0

### Connexion

- **OAuth uniquement** : identifiants (utilisateur / mot de passe / OTP) et token supprimés (pages, commandes,
  tests, README). Un seul bouton « Sign in with Plex ».
- Nouvel utilisateur : le menu affiche *Sign in with Plex* + *Getting started* ; après la connexion on arrive sur
  le menu, qui montre les serveurs ajoutés.

### Médias

- **Page d'actions par média** (⏎ quand ⏎ n'a rien d'autre à faire, ou `fn⏎`) : lire, parcourir les enfants,
  aller à la série / saison / album, web, marquer lu / non lu, noter (0-10), watchlist, Movie and TV Show Search,
  ajouter à une playlist (ou en créer une), ajouter / retirer d'une collection, fichiers (taille, conteneur,
  résolution, codecs, débit ; afficher dans le Finder ou copier le chemin ; copier le lien direct), télécharger,
  rafraîchir les métadonnées, analyser, infos, supprimer du serveur (avec confirmation).
- Nouveaux raccourcis configurables : page d'actions (`fn⏎`), lu / non lu (`⌘⇧⏎`), téléchargement (désactivé
  par défaut). Le ✓ dans le sous-titre indique un média vu.

### Serveurs

- Récemment ajoutés, Continuer la lecture (serveur et par section).
- Sessions : Direct Play / Transcode, débit, LAN / WAN, « Terminer toutes les sessions », ⏎ = actions du média.
- Sections : analyser, vider la corbeille, chercher dans la section, taille + durée.
- **Maintenance** : logs, bases de données, corbeille, bundles, optimisation, tâches planifiées (butler).
- **Activités** en cours avec barre de progression ; installation de mise à jour (serveurs Mac / Windows).
- **Statistiques** : live (barres CPU / RAM), bibliothèques (taille, durée, part du stockage), lectures (par jour,
  jour le plus chargé, heure de pointe, top utilisateurs / titres / bibliothèques / appareils / plateformes),
  bande passante (local / distant, par utilisateur / appareil / jour), qualité (4K / 1080p / HDR par section).
  Calculs dans `stats.py` (fonctions pures, testées).

### Appareils

- Triés par dernière activité (« vu il y a 3 jours »), détails (version, modèle, IP, écran, localisation).
- **Nettoyage des vieux appareils** (non vus depuis 90 jours, réglable) en une fois — jamais les serveurs ni ce
  workflow. ⌘⏎ supprime un appareil.

### Presets

- **Sauver la recherche courante** (dernière ligne de Plex Search), dupliquer, monter / descendre, supprimer
  avec confirmation ; raccourcis ⌥ supprimer, ⌃ dupliquer, ⇧ monter.

### Exports

- CSV (UTF-8 avec BOM, lisible par Numbers / Excel) dans le dossier de téléchargements, puis affiché dans le
  Finder : section complète (fichiers, tailles, qualité, vues, notes, ids TMDB / IMDB), historique, bande
  passante, bibliothèques, qualité, sessions, réglages, appareils, utilisateurs, watchlist, presets.
- **Export des logs du workflow** (zip + versions Python / plexapi / macOS) pour un ticket GitHub.

### Raccourcis & mots-clés

- Mots-clés directs `plexs` (Plex Search) et `plexd` (Plex Discover), configurables.
- Page **Plex Help › Keyboard Shortcuts** qui affiche la configuration réelle ; **Getting Started** pour débuter.

### Corrections trouvées en route

- `totalStorage` / `totalDuration` de plexapi échouent quand l'élément XML n'a pas d'enfant (test de vérité sur
  un `Element`) : tailles et durées lues directement dans `/media/providers`.
- Un export « qualité » ne s'arrête plus si une section est en erreur.

### Tests

**240 tests** (Python 3.10 et 3.13), dont `test_features.py` pour toutes les nouveautés (pages, commandes,
appels HTTP exacts vers Plex, contenu des CSV, archive de logs).

### À vérifier sur le Mac

1. `plexs` / `plexd` ouvrent directement la recherche / Discover.
2. Page d'actions d'un film : marquer vu, noter, ajouter à une playlist / collection, télécharger.
3. Statistiques et exports CSV sur un vrai serveur (les volumes réels peuvent être longs à exporter).
4. Nettoyage des vieux appareils (vérifier la liste dans la page de confirmation avant de valider).

## 11. Version 3.2.0

### Supprimé

- Mots-clés `plexs` / `plexd` (et leurs réglages) : tout part du menu `plex`.

### Grid View (affiches) — Alfred 5.5+

- Nouvelle chaîne dans le diagramme : `grid` → Run Script `main.py grid` → **Grid View** → Router. La
  configuration de l'objet est reprise de workflows officiels d'Alfred (Thumbnail Navigation) : entrée JSON par
  l'objet précédent, recherche dans la grille, ordre fixe, titre + détails en pied.
- Affiches redimensionnées par le serveur (300×450, `transcodeImage`), téléchargées en parallèle et **mises en
  cache** (une seule fois ; réutilisées comme icônes dans les listes). Nettoyage automatique au-delà de 3000.
- Grilles : bibliothèques (avec tri / filtres), recherche, Discover, watchlist, ajouts récents, reprise de
  lecture, contenu d'une série / saison / artiste / album / collection.
- Pied de l'affiche sélectionnée : année, durée, note, classification, résolution, vu / en cours.
- Nombre de colonnes réglable (`🖼️ Poster columns`).

### Trier / filtrer sans syntaxe

- **Plex Libraries** (nouveau dans le menu) : choisir une section, puis le **tri** (toutes les options de la
  section, ⏎ / ⌘⏎ pour le sens) et les **filtres** (genre, année, résolution, collection, acteur… ou filtres
  oui / non comme *Non vus*, *HDR*) dans des listes. Chaque filtre actif se retire en un ⏎.
- Passage liste ↔ affiches, ouverture dans Plex Search ou sauvegarde en preset de la sélection.

### Plus d'infos sur un média

- **Fiche complète** dans la **Text View** d'Alfred (Markdown) : affiche, accroche, dates, durée, notes avec
  source (Rotten Tomatoes, IMDb…), résumé, **casting avec personnages**, réalisateurs / scénaristes /
  producteurs, genres, pays, collections, étiquettes, édition, identifiants, fichiers et pistes audio /
  sous-titres. Depuis la page d'actions ou ⌥⏎ sur une affiche.

### Points à vérifier sur le Mac (non testables ici)

1. **Alfred 5.5 minimum** pour Grid View / Text View.
2. Forme des affiches : l'objet Grid View utilise `imageaspect = 2` (valeur reprise d'un workflow officiel,
   non documentée publiquement). Si les affiches ont des bandes, changer « Image Aspect » dans l'objet
   Grid View du diagramme.
3. Fiche : l'objet Text View est en mode Markdown (`behaviour = 2`, valeur utilisée par Alfred pour ses
   fichiers Markdown) ; vérifier que l'affiche s'affiche (chemin relatif `../posters/`).
4. Modificateurs dans la grille (⌘⏎ / ⌥⏎) : définis dans le JSON comme pour un Script Filter ; ⏎ marche dans
   tous les cas.

### Tests

**262 tests** (Python 3.10 et 3.13) : `test_posters.py` couvre navigateur de bibliothèque (tri, filtres, état),
grilles (cache des affiches, retour, colonnes), fiche Markdown ; `test_workflow.py` vérifie la chaîne
Grid View / Text View du diagramme.

## 12. Version 3.3.0

### 1. Chargement : Alfred ne se ferme plus

- Avant, valider une action fermait Alfred (Run Script) puis le rouvrait à la fin.
- Maintenant le Router lance la commande **et** affiche une page **⏳ chargement** (« Updating the played
  state: The Matrix… », temps écoulé), rafraîchie toutes les 0,5 s grâce à un fichier de statut
  (`cache/runs/<id>.json`).
- À la fin : la page d'où l'on vient revient avec un bandeau ✅ / 🚨 (ou une ligne Return si l'on venait de
  la grille / d'une recherche). Les actions courtes ne notifient plus (résultat dans Alfred), les longues
  (exports, téléchargements, connexion…) notifient toujours.
- Script Filters : texte « Loading… » ; Grid View : « Loading posters... ».

### 2. Return partout, même sur une saisie

- Les saisies (réglage, preset, alias, note, message de fin de session…) passent d'un objet Keyword à un
  **Script Filter « Plex Prompt »** : ligne ⏎ pour valider + ligne **Return**.
- Pages de confirmation (Annuler = Return), page de chargement, grilles, recherches (Return en dernier quand
  on tape, pour que ⏎ ouvre le premier résultat).

### 3. Échap après « Full details » ne coupe plus le workflow

- Alfred ne revient avec Échap que si la Text View est **empilée sur une fenêtre Alfred visible**. Avant,
  Alfred était déjà fermé (Run Script) → Échap fermait tout.
- La fiche est maintenant écrite pendant l'affichage de la page média : « 📖 Full details » ouvre la Text View
  **par-dessus la page**, Échap y revient. Depuis une affiche (⌥⏎), la page de chargement reste dessous.

### 4. Return revient toujours à l'écran d'origine

- Nouvel **historique** : la variable `back` est une pile JSON (25 écrans max, plate : pas d'échappements
  imbriqués). Chaque page empile l'écran courant sur toutes ses actions de navigation ; Return dépile.
- Exemple : serveur → compte → Return = le serveur (plus la liste des comptes). Recherche « matrix » → film →
  Return = la recherche « matrix ».
- Tri / filtre choisis dans le navigateur de bibliothèque **remplacent** la page (Return ne repasse pas par les
  sélecteurs).

### 5. Plex Libraries fusionné dans Plex Search

- Plex Search vide = vos bibliothèques (⏎ liste, ⌘⏎ affiches) puis la vue par défaut ; on tape pour chercher.

### 6. Discover en Grid View

- « 🖼️ Show as posters » en tête quand Discover est vide (tendances), en fin de résultats sinon.
- La grille Discover inclut les personnes et garde les raccourcis de la liste (⌘ web, ⌃ infos, ⇧ watchlist).

### Diagramme

25 objets (+1 : appel de la page de chargement), toujours sans croisement de liens. Le Keyword de saisie est
remplacé par le Script Filter « Plex Prompt ».

### Tests

**288 tests** (Python 3.10 et 3.13). `test_navigation.py` : historique (aller-retour serveur ↔ compte,
recherche ↔ média, sélecteurs qui remplacent la page), page de chargement (en cours, terminée, erreur, détails),
saisies avec Return, recherche vide = bibliothèques, commandes rapides silencieuses.

### À vérifier sur le Mac

1. Pendant une action, Alfred reste ouvert sur « ⏳ … » puis revient sur la page avec ✅.
2. « 📖 Full details » puis Échap → retour sur la page média.
3. Une saisie (ex. noter un film) : la ligne Return annule et revient.
