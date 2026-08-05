# md2star

[🇫🇷](https://github.com/warith-harchaoui/md2star/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/md2star/blob/main/README.md)

[![PyPI](https://img.shields.io/pypi/v/md2star.svg)](https://pypi.org/project/md2star/)
[![CI](https://github.com/warith-harchaoui/md2star/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/md2star/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Licence : BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)
![Statut : beta](https://img.shields.io/badge/status-beta-orange.svg)
[![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#la-promesse)

> **md2star** convertit du Markdown en `.docx`, `.pptx` et `.pdf`
> brandés, de bout en bout, en s'appuyant sur Pandoc, des templates
> soignés et une automatisation pragmatique.

![logo](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/logo.png)

`md2star` est un outil en ligne de commande multiplateforme qui
habille **Pandoc** d'une couche de style. Il gère les détails que
Pandoc seul laisse passer : espacement des listes, injection de
bibliographie, formules LaTeX, diagrammes Mermaid, embarquement
d'images, largeurs de colonnes, isolation des diapositives PPTX. Vous
restez dans Markdown, sans jamais ouvrir Word pour rattraper la mise
en page.

## La promesse

**Local d'abord, par conception.** md2star tourne entièrement sur votre
machine : le Markdown devient DOCX/PPTX/PDF localement via
Pandoc/LibreOffice. Vos documents ne partent jamais vers un service
tiers ; pas de télémétrie, pas de compte, aucune dépendance au cloud. Il
fait partie de la suite [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) :
vos données vous appartiennent, grâce à de l'Open Source local d'abord.

*La seule réserve honnête :* le **contenu** de votre document reste local. Deux
commodités optionnelles, clairement signalées, peuvent toucher le réseau, et
uniquement si vous les y autorisez. Le template par défaut est téléchargé une
fois depuis `deraison.ai` à défaut de `--reference-doc` local (passez
`--offline` pour forcer le template embarqué et ne rien contacter), et les
images distantes `![](https://…)` ne sont intégrées qu'avec
`--allow-remote-images`. Dans les deux cas, votre Markdown ne quitte
jamais votre machine.


*Mode DOCX — algorithme d'ingénierie de Musk rendu en direct:*

| Light | Dark |
|---|---|
| ![md2star DOCX — light](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/light.png) | ![md2star DOCX — dark](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/dark.png) |

*PPTX mode — Pitch Deck de Kawasaki 10/20/30:*

| Light | Dark |
|---|---|
| ![md2star PPTX — light](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/pptx-light.png) | ![md2star PPTX — dark](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/pptx-dark.png) |

*Mode GUI — l'éditeur local façon Overleaf avec aperçu PDF en direct
(`md2star gui`):*

| Light | Dark |
|---|---|
| ![md2star GUI — light](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/gui-light.png) | ![md2star GUI — dark](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/gui-dark.png) |

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/md2star-doc/)

[🗺️ Paysage](https://github.com/warith-harchaoui/md2star/blob/main/PAYSAGE.md)

[📋 Exemples](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md)

## Pourquoi md2star ? (la réponse honnête au « utilise juste Pandoc »)

Pandoc est un **convertisseur** ; md2star est un **livrable**. Pandoc
transforme du Markdown en un `.docx` valide ; md2star transforme du Markdown
en un `.docx` que vous pouvez envoyer à un client sans ouvrir Word — et le
relit en Markdown éditable quand il vous revient. md2star ne fait pas mieux que
Pandoc ; il *appelle* Pandoc et y ajoute le template soigné, la colle
Mermaid/images/PDF, le chemin inverse `md2star twin` et un aller-retour vérifié
en CI que Pandoc brut vous force à construire vous-même. Il se pose *au-dessus*
de Pandoc — il ne vous demande jamais d'abandonner Pandoc.

L'argumentaire complet — les manques de style que `pandoc rapport.md -o
rapport.docx` vous laisse sur les bras, le seul endroit où « utilise juste
Pandoc » n'a pas de réponse (le chemin inverse + la garantie d'aller-retour),
et là où Pandoc est vraiment le bon outil — est dans
**[WHY_MD2STAR_OVER_PANDOC.md](https://github.com/warith-harchaoui/md2star/blob/main/WHY_MD2STAR_OVER_PANDOC.md)**.

## Démarrage rapide

```bash
pipx install md2star          # une seule ligne : les quatre CLI + la GUI
md2star doctor                # vérifie la santé de l'environnement
md2docx rapport.md            # markdown → DOCX
md2pptx diapos.md             # markdown → PPTX
md2pdf  article.md            # markdown → PDF (nécessite LibreOffice)
md2star gui                   # éditeur navigateur local, aperçu PDF en direct
```

Vous préférez `pip` ? Deux fichiers `requirements` correspondent aux
profils d'installation : `pip install -r requirements.txt` pour la CLI,
`pip install -r requirements-gui.txt` pour la CLI + la GUI (même wheel,
la GUI n'ajoute aucune dépendance Python).

Vous préférez HTTP ou MCP ? md2star embarque aussi une surface FastAPI et un
serveur MCP :

```bash
pip install 'md2star[api,mcp]'

md2star-api                    # FastAPI : /gui, /health, /doctor, /convert — docs sur /docs
curl -F 'file=@rapport.md' 'http://localhost:8000/convert?fmt=docx' -o rapport.docx
# ouvrez http://localhost:8000/gui pour un banc d'essai minimal dans le navigateur

md2star-mcp                    # mêmes outils (doctor / convert) via MCP
```

> Le serveur `md2star-api` sert aussi un **banc d'essai minimal** dans le
> navigateur sur `GET /gui` — déposez un `.md`, choisissez un format, téléchargez
> le résultat. C'est le petit frère de l'éditeur complet `md2star gui` (aperçu
> PDF en direct).

Vous préférez click ? `md2star-x docx|pptx|pdf|gui|doctor` est une façade click
au-dessus du même pipeline (fournie avec l'installation cœur). md2star se
distribue aussi comme **Claude Skill / OpenCode skill** pour qu'un agent le
pilote : voir [`skills/md2star/`](https://github.com/warith-harchaoui/md2star/blob/main/skills/md2star/SKILL.md) et
[`skills/README.md`](https://github.com/warith-harchaoui/md2star/blob/main/skills/README.md). Le catalogue complet de ce qui
déclenche md2star (formulations, commandes, situations de fichier) vit dans
**[TRIGGERS.md](https://github.com/warith-harchaoui/md2star/blob/main/TRIGGERS.md)**.

Voir **[docs/installation.md](https://github.com/warith-harchaoui/md2star/blob/main/docs/installation.md)** pour la matrice
complète par OS (macOS / Ubuntu / Fedora / Arch / Windows), le tableau
de dépendances par fonctionnalité et le guide de dépannage.

## Formats pris en charge

| Format | Statut | Pré-requis                        | CLI                       |
|--------|--------|-----------------------------------|---------------------------|
| DOCX   | Beta   | Pandoc                            | `md2docx fichier.md`      |
| PPTX   | Beta   | Pandoc                            | `md2pptx fichier.md`      |
| PDF    | Beta   | Pandoc + LibreOffice (`soffice`)  | `md2pdf  fichier.md`      |

« Beta » signifie : le format marche pour les cas courants, dispose
de tests automatisés, et a déjà servi à produire de vrais documents.
Le bug de rendu des tableaux qui plombait la v1.x côté PDF (cellules
empilées en colonne au lieu de former une grille) est corrigé en
v2.0.0 ; le template embarqué a été reconstruit sur une base Pandoc
propre.

## Exemples (les plus parlants)

**1. Markdown nu → DOCX brandé**

```bash
md2docx rapport.md --author "Ada Lovelace"
```

Vous obtenez `rapport.docx` avec les polices / marges / styles de
titres du template intégré, le premier `# Titre` promu en titre du
document, la date du jour localisée d'après la langue détectée et
l'auteur reporté dans le sous-titre.

**2. Article scientifique avec bibliographie**

```bash
md2docx article.md --author "Dr. R. Chercheur" \
                   --bib references.bib \
                   --bibliography-name "Références"
```

Le `citeproc` de Pandoc résout les références `[@einstein1905]`
depuis le fichier BibTeX et ajoute une section « Références » en fin
de document.

**3. PDF qui colle exactement au DOCX**

```bash
md2pdf article.md --author "Dr. R. Chercheur" --bib references.bib
```

Le DOCX est rendu via LibreOffice headless, donc le PDF hérite de
tout le travail de md2star : template brandé, PNG Mermaid, styles de
tableaux, dates localisées.

Un livre de recettes complet vit dans **[EXAMPLES.md](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md)**.

---

## GUI locale (`md2star gui`)

Vous préférez le navigateur au terminal ? `md2star gui` lance un
éditeur local façon Overleaf : le Markdown à gauche, un **aperçu PDF
en direct** à droite, et le téléchargement DOCX / PPTX / PDF en un
clic.

```bash
pip install 'md2star[gui]'    # commande d'installation explicite « je veux la GUI »
md2star gui                   # ouvre http://127.0.0.1:8765 dans le navigateur
md2star gui --port 9000       # choisit un port (repli auto si occupé)
md2star gui --no-browser      # affiche juste l'URL, sans ouvrir le navigateur
```

> `md2star[gui]` pointe vers le **même wheel** que `md2star` : la GUI est incluse
> et n'ajoute aucune dépendance Python, donc `pip install md2star` la contient
> déjà. La forme `[gui]` dit juste plus clairement « je viens pour
> l'éditeur ».

Ce qu'elle apporte :

- **Aperçu PDF en direct** rendu dans la page via PDF.js, sans détour
  par Word ni un lecteur PDF.
- **Explorateur de dossier** confiné au dossier que vous ouvrez, pour
  éditer tous les `.md` d'un projet (ouvrir / lire / enregistrer /
  créer / supprimer) sans quitter la page.
- **Template de référence en session** : glissez un `template.docx` /
  `template.pptx` et la session brande sa sortie avec.
- **Sauvegarde automatique des brouillons** dans le cache, pour ne
  jamais perdre votre texte après un crash du navigateur ou un
  redémarrage.

Elle est **locale d'abord et hors-ligne** : le serveur n'écoute que
sur `127.0.0.1`, tout le frontend (PDF.js, CodeMirror, Tailwind,
polices) est embarqué dans le paquet, et elle appelle exactement le
même convertisseur que la CLI. Aucune donnée ne quitte votre machine.
Depuis la v2.6.0, la GUI est dans le wheel principal : rien de plus à
installer.

---

## Fonctionnalités

- **Conversion sans friction** : écrivez en Markdown avec votre éditeur préféré (`emacs`, `vim`, `Sublime Text`, `Obsidian`, …) et produisez des `.docx`, `.pptx`, `.pdf` stylés.
- **GUI locale** (`md2star gui`) : un éditeur navigateur hors-ligne (localhost uniquement) avec aperçu PDF en direct, explorateur de dossier confiné, upload de template en session et sauvegarde automatique des brouillons. Incluse dans le wheel principal, rien de plus à installer. Voir [GUI locale](#gui-locale-md2star-gui).
- **Support LaTeX** : rendu solide des formules complexes dans les documents comme dans les diapositives.
- **Diagrammes Mermaid** : les blocs ` ```mermaid ` sont rendus localement en PNG via la CLI officielle Mermaid et intégrés automatiquement (nécessite Node.js ≥16).
- **Métadonnées intelligentes** :
  - **Extraction automatique du titre** depuis votre premier `# Titre`.
  - **Injection d'un sous-titre** combinant l'auteur et la date localisée.
  - **Détection de la langue** via `langdetect` : formats de date fournis pour 10 langues (anglais, français, espagnol, allemand, italien, portugais, néerlandais, russe, japonais, chinois), avec noms de jours et mois traduits pour 7 d'entre elles (fr, es, de, it, pt, nl, ru). Par exemple `dimanche 10 mai 2026` au lieu de `Sunday May 10, 2026`.
- **Prêt pour la recherche** : intégration **BibTeX** native via le `citeproc` de Pandoc, pour des documents à bibliographie gérée.
- **Notes de bas de page natives** : les footnotes Markdown (`texte[^1]` + `[^1]: …`) passent directement par l'extension `footnotes` de Pandoc et deviennent de vraies notes Word. Le DOCX obtient de vraies notes en bas de page, le PPTX les regroupe en notes par diapositive. Aucune syntaxe spéciale, aucun prétraitement. Voir [EXAMPLES.md §10](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md#10-footnotes).
- **Nettoyages automatiques** (petit confort discret) : téléchargement des images `http(s)://` pour l'embarquement (opt-in), conversion des `<table>` HTML en pipe-tables Pandoc, et isolation des images sur leur propre diapositive PPTX quand elles cohabiteraient avec un tableau (sinon Pandoc les supprime).
- **Réversible par conception** : la sortie DOCX de md2star est un rendu *fidèle et récupérable*, pas une impasse à sens unique. Relisez-la vers du Markdown avec n'importe quel lecteur DOCX (Pandoc, [kreuzberg](https://github.com/Goldziher/kreuzberg)) : vos titres, votre emphase `**gras**`/`*italique*`/`` `code` ``, vos tableaux et vos listes reviennent intacts, et les conversions répétées convergent vers un **point fixe stable** au lieu de dériver. Voir [Fidélité de l'aller-retour](#fidélité-de-laller-retour).
- **Jumeau Markdown (sens inverse)** : `md2star twin <fichier>` relit **n'importe quel PDF — ou tout ce que LibreOffice sait convertir en PDF** — en un `<nom>.md` *éditable* **plus un dossier `assets/`**. Les tableaux reviennent en pipe-tables GFM et chaque image embarquée est extraite puis re-liée. Ajoutez `--diagrams` (opt-in, nécessite un modèle local — voir le Linter LLM ci-dessous) et les figures en nœuds-et-flèches sont **ré-écrites en Mermaid** via une *boucle œil-de-lynx guidée par la cible* — on rend un candidat avec le même `mmdc` que le sens direct, on le compare à l'original extrait via un modèle de vision local, et on itère jusqu'à correspondance ; les autres figures vectorielles nettes sont ré-écrites en SVG éditable de la même façon. Le PNG extrait est toujours conservé en repli, donc rien n'est jamais perdu. Tout se dégrade proprement : si le modèle local ne peut être résolu, les images restent de simples PNG extraits. Nécessite `pip install 'md2star[ocr]'`.
- **Résolution souple des chemins d'images** : URLs, chemins absolus et chemins relatifs se comportent comme prévu. Une référence relative `![](images/foo.png)` est résolue par rapport au dossier du fichier source.
- **Identité visuelle zéro-config** : déposez un `template.docx` / `template.pptx` à côté de votre Markdown, md2star le détecte automatiquement comme `--reference-doc`. À défaut, md2star télécharge par défaut (depuis v2.5.0) le template `deraison.ai` et le met en cache ; passez `--no-remote-templates` / `--offline` pour utiliser le template embarqué.
- **CLI auto-documentée** : chaque wrapper accepte `--help` / `-h` et affiche d'abord les options propres à md2star, puis `pandoc --help`. Essayez `md2docx --help`, `md2pptx --help` ou `md2star --help`.
- **Linter LLM opt-in** : une passe locale corrige les erreurs de syntaxe (liens d'images cassés, fences non fermées, pipes mal formés) **avant** que Pandoc lise le fichier. **Désactivé par défaut** ; ajoutez `--lint` pour l'activer. Le backend et le modèle sont choisis par le **contrat brief → engine** de la suite : md2star embarque un `md2star/llm.brief.yaml` versionné décrivant les besoins de ses passes IA, et [`best-engine-ai-helper`](https://pypi.org/project/best-engine-ai-helper/) le résout contre *votre* machine au premier usage — écrivant le choix concret dans un `md2star/llm.engine.yaml` gitignoré. **Aucun tag de modèle n'est codé en dur** ; le transport (Ollama local pour l'instant) gère lui-même le cycle de vie du démon, donc md2star ne lance jamais `ollama serve` / `ollama pull`. Si aucun modèle local n'est résolu, `--lint` avertit et retombe sur le Markdown original — la passe n'est jamais bloquante.
- **Texte alternatif rédigé par IA** : avec `--lint`, chaque `![](src)` au texte alternatif vide reçoit une description générée par un modèle de vision, dans la langue même du document, en s'appuyant sur le titre et la prose environnants (cache par image). Le modèle de vision provient du même engine résolu que le linter.
- **Compagnon : adaptateur de templates IA** : pour brander un template PPTX
  d'entreprise dont les noms de mises en page ne suivent pas la convention
  Pandoc, utilisez l'outil compagnon
  [md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt).

---

## Installation

`md2star` est un package Python distribué sur PyPI. L'installation via
[pipx](https://pipx.pypa.io/) est recommandée : elle isole le package
dans son propre venv et met les quatre CLI (`md2star`, `md2docx`,
`md2pptx`, `md2pdf`) sur votre PATH. Pandoc est la seule dépendance
système obligatoire ; LibreOffice n'est requis que pour `md2pdf`,
Node.js que pour Mermaid, Ollama que pour `--lint`.

- macOS 🍎 : `brew install pandoc pipx`
  (installez `brew` grâce à [brew.sh](https://brew.sh/)) — ou lancez le
  bootstrap idempotent en une commande `bash scripts/brew.sh --with-pdf`

  ```bash
  pipx ensurepath          # une fois : ajoute ~/.local/bin au PATH
  pipx install md2star

  # Optionnel : la sortie PDF nécessite LibreOffice
  brew install --cask libreoffice
  # Optionnel : les diagrammes Mermaid nécessitent Node.js
  brew install node
  # Optionnel : --lint et le texte alt IA nécessitent un runtime de modèle local (Ollama aujourd'hui)
  brew install ollama
  ```

- Ubuntu 🐧 : `sudo apt-get install pandoc pipx`

  ```bash
  pipx ensurepath
  pipx install md2star

  # Dépendances optionnelles
  sudo apt-get install libreoffice nodejs
  curl -fsSL https://ollama.com/install.sh | sh   # ollama
  ```

- Windows 🪟 : `winget install --id JohnMacFarlane.Pandoc`

  ```powershell
  python -m pip install --user pipx
  python -m pipx ensurepath
  pipx install md2star

  # Dépendances optionnelles
  winget install --id TheDocumentFoundation.LibreOffice
  winget install --id OpenJS.NodeJS
  winget install --id Ollama.Ollama
  ```

### Installation depuis les sources (développement)

```bash
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star
make install            # vérifie les deps, lance `pipx install .`
```

Deux fichiers de dépendances pip vivent à la racine pour une
installation sans `make` (le `pyproject.toml` reste la source de
vérité : ces fichiers installent le package en éditable et héritent
donc de ses pins) :

- `requirements.txt` — **runtime** : installe `-e .` (soit
  `langdetect` + `Pillow`), le strict nécessaire pour lancer
  `md2docx` / `md2pptx` / `md2pdf`.
- `requirements-dev.txt` — **dev + test** : installe `-e .[dev]`
  (pytest, ruff, pytest-cov, pypdf, les deps API/MCP, et `kreuzberg`
  pour l'aller-retour OCR).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # runtime seul
pip install -r requirements-dev.txt    # + outils de test/lint
```

### Mise à jour

| Plateforme | Commande |
|------------|----------|
| Tout (install PyPI) | `pipx upgrade md2star` |
| macOS / Linux depuis les sources | `make update` |
| Windows depuis les sources | `powershell -ExecutionPolicy Bypass -File scripts\update.ps1` |

### Développement local

```bash
make dev                # crée .venv/ avec `pip install -e .[dev]`
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## Guide d'Utilisation

### 1. Export simple
```bash
md2docx monfichier.md
```
*Crée `monfichier.docx`*.

### 2. Article scientifique (avec citations et formules)
```bash
md2docx travail.md --author "Dr. R. Chercheur" --bib references.bib --bibliography-name "Références" --lang fr-FR
```
*Crée `travail.docx`*.

### 3. Diapositives
```bash
md2pptx diapositives.md --author "Nom de l'Orateur"
```
*Crée `diapositives.pptx`*.

### 4. Diapositives avec template personnalisé
```bash
md2pptx diapositives.md --reference-doc mon_template.pptx
```

### 5. Export PDF
```bash
md2pdf article.md --author "Dr. R. Chercheur" --bib references.bib
```
*Crée `article.pdf`* (via LibreOffice headless ; `soffice` requis sur le PATH).

### 6. Linter LLM opt-in

```bash
# par défaut : lint désactivé, conversions déterministes
md2docx brouillon.md

# activer (résout un modèle local au premier usage, puis exécute)
md2docx brouillon.md --lint

# no-op explicite (identique au défaut)
md2docx brouillon.md --no-lint
```

Avec `--lint`, une passe locale corrige les liens d'images cassés, les fences non fermées et les pipes de tables mal formés avant que Pandoc lise le fichier. Le même `--lint` remplit aussi les `![](src)` vides via un modèle de vision local, dans la langue même du document.

**Quel modèle, et comment il est choisi (contrat brief → engine).** md2star ne code aucun tag de modèle en dur. Il embarque un `md2star/llm.brief.yaml` versionné décrivant les besoins de ses passes IA (local, texte + vision, faible latence, multilingue). Au premier usage, [`best-engine-ai-helper`](https://pypi.org/project/best-engine-ai-helper/) résout ce brief contre *votre* machine et écrit le backend + modèle concrets dans un `md2star/llm.engine.yaml` gitignoré ; les exécutions suivantes lisent simplement ce fichier engine. Tous les appels passent par `best_engine_ai_helper.llm.chat`, et le transport (Ollama local pour l'instant) gère lui-même le cycle de vie du démon — md2star ne lance jamais `ollama serve` / `ollama pull`. Si aucun modèle local n'est résolu, `--lint` avertit sur stderr et retombe sur le Markdown original, donc la conversion réussit toujours. `best-engine-ai-helper` est une dépendance cœur, donc cela fonctionne d'emblée dès qu'un runtime de modèle local (Ollama aujourd'hui) est installé.

---

## Adaptateur de Templates (dépôt séparé)

Pour les templates PPTX d'entreprise dont les noms de mises en page ne
suivent pas la convention Pandoc, utilisez l'outil compagnon
[md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt). Il
extrait thème, logo et formes du PPTX, classe chaque mise en page via
un modèle de vision local (Ollama) en la confrontant au PDF associé,
puis assemble un document de référence compatible Pandoc : vous
obtenez un `branded_ref.pptx` à passer à md2star via `--reference-doc`.

Il vit dans son propre dépôt parce que ses dépendances (PyMuPDF, lxml,
python-pptx, requests, plus un Ollama VLM en cours d'exécution) sont
nettement plus lourdes que celles du pipeline de conversion de base.

---

## Exemples

Un livre de recettes autonome vit dans **[EXAMPLES.md](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md)**.

Vous pouvez aussi compiler tous les exemples du dossier
[`tests/examples/`](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples) :
```bash
cd tests/examples
./run.sh
```

**Exemples de Documents Word**
- Titre de base [assets/docx/basic.docx](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/basic.docx) *(depuis [basic.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/basic.md))*
  ```bash
  md2docx assets/docx/basic.md
  ```
- Auteur injecté [assets/docx/with_author.docx](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_author.docx) *(depuis [with_author.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_author.md))*
  ```bash
  md2docx assets/docx/with_author.md --author "Testeur"
  ```
- Bibliographie [assets/docx/with_bib.docx](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_bib.docx) *(depuis [with_bib.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_bib.md))*
  ```bash
  md2docx assets/docx/with_bib.md --bib "assets/references.bib" --bibliography-name "Références"
  ```
- Langue & Date (Français) [assets/docx/with_lang.docx](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_lang.docx) *(depuis [with_lang.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_lang.md))*
  ```bash
  md2docx assets/docx/with_lang.md --author "Utilisateur"
  ```
- Formules mathématiques [assets/docx/math.docx](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/math.docx) *(depuis [math.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/math.md))*
  ```bash
  md2docx assets/docx/math.md
  ```
- Notes de bas de page [tests/examples/footnotes_document.docx](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/footnotes_document.docx) *(depuis [footnotes_document.md](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/footnotes_document.md))*
  ```bash
  md2docx tests/examples/footnotes_document.md
  ```

**Exemples de Diapositives PowerPoint**
- Exemple extensif [assets/pptx/example.pptx](https://github.com/warith-harchaoui/md2star/blob/main/assets/pptx/example.pptx) *(depuis [example.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/pptx/example.md))*
  ```bash
  md2pptx assets/pptx/example.md
  ```
- Template personnalisé [tests/examples/branded_slides.pptx](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/branded_slides.pptx) *(depuis [branded_slides.md](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/branded_slides.md) + [Presentation1.pptx](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/Presentation1.pptx))*
  ```bash
  md2pptx tests/examples/branded_slides.md --reference-doc tests/examples/Presentation1.pptx
  ```

---

## Qualité & Fiabilité

La fiabilité est un objectif de conception. La suite de tests automatisée couvre :
- [x] **Précision des métadonnées** : extraction du titre, injection de l'auteur, composition du sous-titre.
- [x] **Rendu bibliographique** : pipeline citeproc contre le snapshot [references.bib](https://github.com/warith-harchaoui/md2star/blob/main/assets/references.bib).
- [x] **Localisation des dates** : rendu des jours et mois en français, injection du format de date.
- [x] **Invariants du préprocesseur** : espacement des listes, préservation des blocs de code, conversion des `<table>` HTML, injection de largeur d'image, détection de langue, fallback Mermaid, math-in-code, isolation PPTX.
- [x] **Mode hors-ligne** : toutes les phases à accès réseau refusent de tourner sous `--offline`.

### Tests d'intégration (shell)

```bash
make test
```

### Tests unitaires (Python)

```bash
python -m pytest tests/ -v
```

---

## Fidélité de l'aller-retour

Convertir en `.docx` n'enferme pas votre contenu dans un format binaire. La
sortie de md2star est un **rendu fidèle et réversible** de votre Markdown :
relisez le `.docx` avec n'importe quel lecteur DOCX, et le contenu source
revient.

**Ce qui survit à l'aller-retour `md → docx → md`** :

| Élément                          | Récupéré ? |
|----------------------------------|:----------:|
| Titres (niveaux de section)      | ✅ |
| `**gras**` / `*italique*`        | ✅ |
| `` `code` `` en ligne            | ✅ (via Pandoc) |
| Tableaux pipe (chaque cellule)   | ✅ |
| Listes à puces et numérotées     | ✅ |
| Paragraphes                      | ✅ |

**Il atteint un point fixe.** L'aller-retour est idempotent au sens
mathématique : l'exécuter deux fois donne le même document qu'une seule fois
(`g(g(x)) == g(x)`), donc les conversions répétées *convergent* au lieu
d'accumuler des scories. C'est vérifié en CI par
[`tests/test_roundtrip.py`](https://github.com/warith-harchaoui/md2star/blob/main/tests/test_roundtrip.py), qui convertit un
échantillon en DOCX, le relit avec le lecteur natif de Pandoc, et contrôle à la
fois la survie du contenu et la propriété de point fixe.

La seule chose que md2star *ajoute* à chaque exécution, par conception, est
un **sous-titre de date** localisé, ré-estampillé à la date du jour ; cela (et
des détails cosmétiques sans valeur sémantique comme le retour à la ligne ou le
nombre exact de tirets dans un séparateur de tableau) est normalisé avant la
vérification d'idempotence. Rien d'autre ne dérive.

**Reproduisez-le vous-même** (n'importe quel lecteur DOCX fonctionne ; la voie
Pandoc intégrée ne demande aucune installation supplémentaire) :

```bash
md2docx rapport.md --offline           # rapport.md → rapport.docx
pandoc rapport.docx -t gfm --wrap=none # rapport.docx → Markdown sur stdout
```

**Le sens `pdf → md` est exact lui aussi — et vérifié en CI.** Rendu jusqu'au PDF
puis relu avec [kreuzberg](https://github.com/Goldziher/kreuzberg)
(`extract_file_sync(path, config=ExtractionConfig(output_format=OutputFormat.PLAIN))`),
l'aller-retour `md → docx → pdf → texte` est l'**identité** `g(f(x)) = x` — prouvée
par égalité exacte du document entier sous une *forme normale* explicite dans
[`tests/test_roundtrip_ocr.py`](https://github.com/warith-harchaoui/md2star/blob/main/tests/test_roundtrip_ocr.py), exécutée pour de vrai
en CI avec la chaîne complète LibreOffice + kreuzberg. Elle tient pour :

- les **paragraphes** de toute longueur (le retour à la ligne est refusionné) ;
- les **listes à puces** ;
- les documents **multi-pages** (les numéros de page sont normalisés) ;
- les **notes de bas de page** — étiquettes numériques `[^1]` comme nommées `[^aa]` :
  le *texte* de la note est récupéré même si le rendu renumérote l'étiquette.

Ce qu'un PDF ne peut pas rendre, c'est le balisage qu'il n'a jamais stocké :
l'emphase en ligne, les *niveaux* de titres et la structure des tableaux deviennent
du texte brut ; les mots survivent, pas le balisage. Ce balisage structuré est
précisément ce que le lecteur DOCX ci-dessus récupère, si bien que les deux sens
couvrent ensemble tout le document.

---

## Personnalisation

### Paramètres par défaut
Ajustez vos paramètres globaux dans `md2star/data/metadata.yaml` :
```yaml
author: "Votre Nom"
date_format: "%A %e %B %Y"
lang: "fr-FR"
```

Conventions :

  + `date_format` utilise un format `strftime()`. Voir la
[documentation C/POSIX](https://pubs.opengroup.org/onlinepubs/9699919799/functions/strftime.html).

  + `lang` utilise une étiquette BCP 47 (ex. `fr-FR`, `en-US`). Voir
la [RFC 5646](https://datatracker.ietf.org/doc/html/rfc5646).

### Modèles de style

Deux niveaux de personnalisation :

**Par projet** (recommandé) : déposez un `template.docx` ou
`template.pptx` à côté de votre Markdown. Tous les wrappers md2star
le détectent et le passent en `--reference-doc`. Committez-le avec
vos sources pour que collaborateurs et CI produisent exactement le
même rendu.

À défaut de `template.docx` (préféré) ou de l'ancien
`.pandoc-reference.docx`, md2star télécharge **par défaut** (depuis
v2.5.0) le template `deraison.ai` et le met en cache (XDG) :

```
https://deraison.ai/template.docx
https://deraison.ai/template.pptx
```

Passez `--no-remote-templates` (ou le commutateur `--offline`) pour
sauter ce téléchargement et utiliser le template embarqué dans le
wheel. Un échec de téléchargement (pas de réseau, 404, timeout)
retombe lui aussi sur le template embarqué : une conversion n'échoue
jamais parce que `deraison.ai` est injoignable.

**Global** (modifie le défaut embarqué) : éditez les modèles dans
`md2star/data/` pour changer polices, marges ou logos. Relancez
ensuite `make reinstall` pour que les changements prennent effet.

---

## Documentation Développeur

- [Guide Développeur](https://github.com/warith-harchaoui/md2star/blob/main/docs/developer_guide.md)

---

## Projets Connexes

- **[Pandoc](https://pandoc.org/)** : Le moteur de conversion universel.
- **[MarkItDown](https://github.com/microsoft/markitdown)** : Conversion Office → Markdown.
- **[Obsidian](https://obsidian.md/)** : Notre environnement d'écriture recommandé.
- **[Zotero](https://www.zotero.org/)** : Compagnon idéal pour gérer vos bibliographies `.bib`.

---

## Dépannage

| Problème | Solution |
|----------|----------|
| `md2docx: command not found` | Ajoutez `~/.local/bin` au PATH (`pipx ensurepath`) et redémarrez votre shell. |
| `pandoc: command not found` | Installez [Pandoc](https://pandoc.org/installing.html). |
| Erreurs `mmdc` / blocs mermaid laissés tels quels | Installez Node.js ≥16. |
| Activer le linter LLM | Passez `--lint`. Si `ollama` n'est pas sur le `PATH`, un avertissement s'affiche et la conversion continue sans lint. |
| `md2pdf: LibreOffice not found` | Installez LibreOffice (brew / apt / winget). |
| Image distante non embarquée | Passez `--allow-remote-images` (md2star est offline par défaut). |

---

## Sécurité & mode hors-ligne

Aucun `.md` que vous traitez ne peut déclencher d'appel réseau de son
propre chef. Les images distantes restent opt-in via
`--allow-remote-images`. Depuis v2.5.0, le template de référence
`deraison.ai` est téléchargé par défaut à défaut de
`template.{docx,pptx}` local (mis en cache XDG, repli sur le template
embarqué en cas d'échec) ; `--no-remote-templates` le saute. Le
commutateur `--offline` est le coupe-circuit dur : il interdit tout
accès réseau et rend le refus explicite dans les scripts. Modèle de
sécurité complet : **[SECURITY.md](https://github.com/warith-harchaoui/md2star/blob/main/SECURITY.md)**.

## Feuille de route

- Voir **[ROADMAP.md](https://github.com/warith-harchaoui/md2star/blob/main/ROADMAP.md)** pour ce qui arrive et ce qui n'est
  explicitement pas dans le périmètre.
- Voir **[CHANGELOG.md](https://github.com/warith-harchaoui/md2star/blob/main/CHANGELOG.md)** pour le diff par version.

## Contribuer

Voir **[CONTRIBUTING.md](https://github.com/warith-harchaoui/md2star/blob/main/CONTRIBUTING.md)** pour le démarrage rapide,
l'organisation du projet et la checklist de PR. TL;DR : `make dev`
+ `python -m pytest tests/` + `ruff check md2star/ tests/`.

---

## Licence

Distribué sous la **[Licence BSD 3-Clause](https://github.com/warith-harchaoui/md2star/blob/main/LICENSE)** — la même licence
permissive que celle utilisée par scikit-learn et d'autres projets
scientifiques majeurs en Python.

**Auteur :** [Warith HARCHAOUI](https://www.linkedin.com/in/warith-harchaoui/)
