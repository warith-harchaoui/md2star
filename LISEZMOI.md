# md2star

[![PyPI](https://img.shields.io/pypi/v/md2star.svg)](https://pypi.org/project/md2star/)
[![CI](https://github.com/warith-harchaoui/md2star/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/md2star/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Licence : BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)
![Statut : beta](https://img.shields.io/badge/status-beta-orange.svg)

> **md2star** convertit du Markdown en `.docx`, `.pptx` et `.pdf`
> brandés, de bout en bout, en s'appuyant sur Pandoc, des templates
> soignés et une automatisation pragmatique.

![logo](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/logo.png)

`md2star` est un outil en ligne de commande multiplateforme qui
enveloppe **Pandoc** d'une couche de style soignée. Il prend en charge
les détails que Pandoc seul rate — espacement des listes, injection
de bibliographie, formules LaTeX, diagrammes Mermaid, embarquement
d'images, largeurs de colonnes, isolation de diapositives PPTX — pour
vous garder dans Markdown sans ouvrir Word pour corriger la mise en
page.


*Mode DOCX — algorithme d'ingénierie de Musk rendu en direct:*

| Light | Dark |
|---|---|
| ![md2star DOCX — light](assets/light.png) | ![md2star DOCX — dark](assets/dark.png) |

*PPTX mode — Pitch Deck de Kawasaki 10/20/30:*

| Light | Dark |
|---|---|
| ![md2star PPTX — light](assets/pptx-light.png) | ![md2star PPTX — dark](assets/pptx-dark.png) |

## Pourquoi md2star ?

Pandoc seul est puissant mais agnostique : il produit un DOCX brut,
sans template, sans date localisée, sans largeurs de tableau
raisonnables, sans rendu Mermaid. Le résultat demande d'être retouché
dans Word avant d'être partageable.

`md2star` s'intercale entre vous et Pandoc. Vous écrivez en Markdown ;
vous obtenez un DOCX / PPTX / PDF qui ressemble à un document
délibéré.

## Démarrage rapide

```bash
pipx install md2star          # une seule ligne : installe les quatre CLI
md2star doctor                # vérifie la santé de l'environnement
md2docx rapport.md            # markdown → DOCX
md2pptx diapos.md             # markdown → PPTX
md2pdf  article.md            # markdown → PDF (nécessite LibreOffice)
```

Voir **[docs/installation.md](docs/installation.md)** pour la matrice
complète par OS (macOS / Ubuntu / Fedora / Arch / Windows), le tableau
de dépendances par fonctionnalité et le guide de dépannage.

## Formats pris en charge

| Format | Statut | Pré-requis                        | CLI                       |
|--------|--------|-----------------------------------|---------------------------|
| DOCX   | Beta   | Pandoc                            | `md2docx fichier.md`      |
| PPTX   | Beta   | Pandoc                            | `md2pptx fichier.md`      |
| PDF    | Beta   | Pandoc + LibreOffice (`soffice`)  | `md2pdf  fichier.md`      |

« Beta » signifie : le format fonctionne pour les cas courants,
dispose d'une couverture de tests automatisée, et a déjà servi à
produire de vrais documents. Le bug de rendu des tableaux qui
hantait la v1.x côté PDF (cellules empilées en colonne au lieu de
former une grille) est corrigé en v2.0.0 — le template embarqué
a été reconstruit sur une base Pandoc-propre.

## Exemples (les plus parlants)

**1. Markdown nu → DOCX brandé**

```bash
md2docx rapport.md --author "Ada Lovelace"
```

Vous obtenez `rapport.docx` avec les polices / marges / styles de
titres du template intégré, le premier `# Titre` promu en titre du
document, la date du jour localisée selon la langue détectée et
l'auteur rendu dans le sous-titre.

**2. Article scientifique avec bibliographie**

```bash
md2docx article.md --author "Dr. R. Chercheur" \
                   --bib references.bib \
                   --bibliography-name "Références"
```

Le `citeproc` de Pandoc résout les références `[@einstein1905]`
contre le fichier BibTeX et ajoute une section « Références » à la
fin.

**3. PDF qui colle exactement au DOCX**

```bash
md2pdf article.md --author "Dr. R. Chercheur" --bib references.bib
```

Le DOCX est rendu via LibreOffice headless, donc le PDF hérite de
tous les soins md2star — template brandé, PNG Mermaid, styles de
tableaux, dates localisées.

Un livre de recettes complet vit dans **[EXAMPLES.md](EXAMPLES.md)**.

---

## Fonctionnalités

- **Conversion sans friction** : Écrivez en Markdown avec votre éditeur préféré (`emacs`, `vim`, `Sublime Text`, `Obsidian`, …) et produisez des `.docx`, `.pptx`, `.pdf` stylés.
- **Support LaTeX** : Rendu robuste de formules complexes dans les documents et les diapositives.
- **Diagrammes Mermaid** : les blocs ` ```mermaid ` sont rendus localement en PNG via la CLI officielle Mermaid et intégrés automatiquement (nécessite Node.js ≥16).
- **Métadonnées intelligentes** :
  - **Extraction automatique du titre** depuis votre premier `# Titre`.
  - **Injection de sous-titre** combinant l'Auteur et la Date localisée.
  - **Détection de la langue** via `langdetect` : formats de date livrés pour 10 langues (anglais, français, espagnol, allemand, italien, portugais, néerlandais, russe, japonais, chinois), avec noms de jours/mois traduits pour 7 (fr, es, de, it, pt, nl, ru) — par exemple `dimanche 10 mai 2026` au lieu de `Sunday May 10, 2026`.
- **Prêt pour la recherche** : Intégration **BibTeX** native via `citeproc` de Pandoc, pour des documents avec une bibliographie gérée.
- **Notes de bas de page natives** : les footnotes Markdown (`texte[^1]` + `[^1]: …`) traversent directement l'extension `footnotes` de Pandoc et deviennent de vraies notes Word — le DOCX obtient de vraies notes en bas de page, le PPTX les regroupe en notes par diapositive. Aucune syntaxe spéciale, aucun prétraitement. Voir [EXAMPLES.md §10](EXAMPLES.md#10-footnotes).
- **Nettoyages automatiques** (qualité de vie discrète) : téléchargement des images `http(s)://` pour l'embarquement (opt-in), conversion des `<table>` HTML en pipe-tables Pandoc, et isolation des images sur leur propre diapositive PPTX lorsqu'elles cohabiteraient avec un tableau (sinon Pandoc les supprime).
- **Réversible par conception** : la sortie DOCX de md2star est un rendu *fidèle et récupérable*, pas une impasse à sens unique. Relisez-la vers du Markdown avec n'importe quel lecteur DOCX (Pandoc, [kreuzberg](https://github.com/Goldziher/kreuzberg)) et vos titres, votre emphase `**gras**`/`*italique*`/`` `code` ``, vos tableaux et vos listes reviennent intacts — et les conversions répétées convergent vers un **point fixe stable** au lieu de dériver. Voir [Fidélité de l'aller-retour](#fidélité-de-laller-retour).
- **Résolution gracieuse des chemins d'images** : URLs, chemins absolus et chemins relatifs « marchent comme on s'y attend ». Une référence relative `![](images/foo.png)` est résolue par rapport au dossier du fichier source.
- **Identité visuelle zéro-config** : déposez un `template.docx` / `template.pptx` à côté de votre Markdown, md2star le détecte automatiquement comme `--reference-doc`. Si aucun n'existe, md2star télécharge par défaut (depuis v2.5.0) le template `deraison.ai` et le met en cache ; passez `--no-remote-templates` / `--offline` pour utiliser le template embarqué à la place.
- **CLI auto-documentée** : chaque wrapper supporte `--help` / `-h` et affiche d'abord les options spécifiques à md2star puis `pandoc --help`. Essayez `md2docx --help`, `md2pptx --help` ou `md2star --help`.
- **Linter LLM opt-in** : une passe locale Ollama corrige les erreurs de syntaxe (liens d'images cassés, fences non fermées, pipes mal formés) **avant** que Pandoc lise le fichier. **Désactivé par défaut** ; ajoutez `--lint` pour l'activer. Le wrapper lance alors `ollama serve` et `ollama pull` le modèle par défaut à la demande — `gemma4:e2b-mlx` sur macOS (build MLX optimisé Apple Silicon) ou `gemma4:e2b` sur Linux/Windows.
- **Texte alternatif rédigé par IA** : avec `--lint`, chaque `![](src)` au texte alternatif vide reçoit une description générée par modèle de vision (même modèle `gemma4:e2b`, cache par image). Surchargez le modèle via `MD2STAR_ALT_TEXT_MODEL`.
- **Compagnon : Adaptateur de Templates IA** : pour brander un template PPTX
  d'entreprise dont les noms de mises en page ne suivent pas la convention
  Pandoc, utilisez l'outil compagnon
  [md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt).

---

## Installation

`md2star` est un package Python distribué sur PyPI. L'installation via
[pipx](https://pipx.pypa.io/) est recommandée — elle isole le package
dans son propre venv et met les quatre CLI (`md2star`, `md2docx`,
`md2pptx`, `md2pdf`) sur votre PATH. Pandoc est la seule dépendance
système obligatoire ; LibreOffice n'est requis que pour `md2pdf` ;
Node.js que pour Mermaid ; Ollama que pour `--lint`.

- macOS 🍎 : `brew install pandoc pipx`
  (installez `brew` grâce à [brew.sh](https://brew.sh/))

  ```bash
  pipx ensurepath          # une fois : ajoute ~/.local/bin au PATH
  pipx install md2star

  # Optionnel : la sortie PDF nécessite LibreOffice
  brew install --cask libreoffice
  # Optionnel : les diagrammes Mermaid nécessitent Node.js
  brew install node
  # Optionnel : --lint et le texte alt IA nécessitent Ollama
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

Deux fichiers de dépendances pip vivent à la racine pour un chemin
d'installation sans `make` (le `pyproject.toml` reste la source de
vérité — ces fichiers installent le package en éditable et héritent
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

# activer (lance `ollama serve` et tire le modèle à la demande)
md2docx brouillon.md --lint

# no-op explicite (identique au défaut)
md2docx brouillon.md --no-lint
```

Lorsque vous passez `--lint`, une passe locale Ollama (modèle texte `gemma4:e2b-mlx` sur macOS, `gemma4:e2b` sur Linux/Windows) corrige liens d'images cassés, fences non fermées et pipes de tables mal formés avant que Pandoc lise le fichier. Le même `--lint` remplit aussi les `![](src)` vides en utilisant un modèle de vision local (`MD2STAR_ALT_TEXT_MODEL` pour surcharger). Le wrapper démarre le démon à la demande (`ollama serve`) et tire le modèle par défaut au premier usage. Si `--lint` est passé mais qu'Ollama n'est pas installé, md2star affiche un avertissement et continue avec le Markdown original.

---

## Adaptateur de Templates (dépôt séparé)

Pour les templates PPTX d'entreprise dont les noms de mises en page ne
suivent pas la convention Pandoc, utilisez l'outil compagnon
[md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt). Il
extrait thème/logo/formes du PPTX, classe chaque mise en page via un
modèle de vision locale (Ollama) en confrontant le PDF associé, puis
assemble un document de référence compatible Pandoc — vous obtenez un
`branded_ref.pptx` à passer à md2star via `--reference-doc`.

Il vit dans son propre dépôt parce que ses dépendances (PyMuPDF, lxml,
python-pptx, requests + un Ollama VLM en cours d'exécution) sont
nettement plus lourdes que ce dont le pipeline de conversion de base
a besoin.

---

## Exemples

Un livre de recettes autonome vit dans **[EXAMPLES.md](EXAMPLES.md)**.

Vous pouvez aussi compiler tous les exemples du dossier
[`tests/examples/`](tests/examples) :
```bash
cd tests/examples
./run.sh
```

**Exemples de Documents Word**
- Titre de base [assets/docx/basic.docx](assets/docx/basic.docx) *(depuis [basic.md](assets/docx/basic.md))*
  ```bash
  md2docx assets/docx/basic.md
  ```
- Auteur injecté [assets/docx/with_author.docx](assets/docx/with_author.docx) *(depuis [with_author.md](assets/docx/with_author.md))*
  ```bash
  md2docx assets/docx/with_author.md --author "Testeur"
  ```
- Bibliographie [assets/docx/with_bib.docx](assets/docx/with_bib.docx) *(depuis [with_bib.md](assets/docx/with_bib.md))*
  ```bash
  md2docx assets/docx/with_bib.md --bib "assets/references.bib" --bibliography-name "Références"
  ```
- Langue & Date (Français) [assets/docx/with_lang.docx](assets/docx/with_lang.docx) *(depuis [with_lang.md](assets/docx/with_lang.md))*
  ```bash
  md2docx assets/docx/with_lang.md --author "Utilisateur"
  ```
- Formules mathématiques [assets/docx/math.docx](assets/docx/math.docx) *(depuis [math.md](assets/docx/math.md))*
  ```bash
  md2docx assets/docx/math.md
  ```
- Notes de bas de page [tests/examples/footnotes_document.docx](tests/examples/footnotes_document.docx) *(depuis [footnotes_document.md](tests/examples/footnotes_document.md))*
  ```bash
  md2docx tests/examples/footnotes_document.md
  ```

**Exemples de Diapositives PowerPoint**
- Exemple extensif [assets/pptx/example.pptx](assets/pptx/example.pptx) *(depuis [example.md](assets/pptx/example.md))*
  ```bash
  md2pptx assets/pptx/example.md
  ```
- Template personnalisé [tests/examples/branded_slides.pptx](tests/examples/branded_slides.pptx) *(depuis [branded_slides.md](tests/examples/branded_slides.md) + [Presentation1.pptx](tests/examples/Presentation1.pptx))*
  ```bash
  md2pptx tests/examples/branded_slides.md --reference-doc tests/examples/Presentation1.pptx
  ```

---

## Qualité & Fiabilité

`md2star` est conçu pour la fiabilité. La suite de tests automatisée couvre :
- [x] **Précision des métadonnées** : extraction du titre, injection de l'auteur, composition du sous-titre.
- [x] **Rendu bibliographique** : pipeline citeproc contre le snapshot [references.bib](assets/references.bib).
- [x] **Localisation des dates** : rendu des jours/mois en français et injection du format de date.
- [x] **Invariants du préprocesseur** : espacement des listes, préservation des blocs de code, conversion des `<table>` HTML, injection de largeur d'image, détection de langue, fallback Mermaid, math-in-code, isolation PPTX.
- [x] **Mode hors-ligne** : toutes les phases avec accès réseau refusent de tourner avec `--offline`.

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
relisez le `.docx` avec n'importe quel lecteur DOCX et le contenu source
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
mathématique — l'exécuter deux fois donne le même document qu'une seule fois
(`g(g(x)) == g(x)`), donc les conversions répétées *convergent* au lieu
d'accumuler des scories. C'est vérifié en CI par
[`tests/test_roundtrip.py`](tests/test_roundtrip.py), qui convertit un
échantillon en DOCX, le relit avec le lecteur natif de Pandoc, et vérifie à la
fois la survie du contenu et la propriété de point fixe.

La seule chose que md2star *ajoute* à chaque exécution — par conception — est
un **sous-titre de date** localisé, ré-estampillé à la date du jour ; cela (et
des détails cosmétiques comme le retour à la ligne ou le nombre exact de tirets
dans un séparateur de tableau, sans valeur sémantique) est normalisé avant la
vérification d'idempotence. Rien d'autre ne dérive.

**Reproduisez-le vous-même** (n'importe quel lecteur DOCX fonctionne ; la voie
Pandoc intégrée ne demande aucune installation supplémentaire) :

```bash
md2docx rapport.md --offline           # rapport.md → rapport.docx
pandoc rapport.docx -t gfm --wrap=none # rapport.docx → Markdown sur stdout
```

Vous préférez un lecteur basé sur l'OCR qui couvre aussi le sens `pdf → md` ?
La même propriété tient avec
[kreuzberg](https://github.com/Goldziher/kreuzberg)
(`extract_file_sync(path, config=ExtractionConfig(output_format=OutputFormat.MARKDOWN))`),
qui a récupéré **100 %** du texte des titres et des mots du corps depuis le
DOCX et **94–99 %** depuis le PDF rendu par LibreOffice dans nos mesures.

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
vos sources pour que collaborateurs et CI produisent rigoureusement
le même rendu.

Si ni `template.docx` (préféré) ni l'ancien `.pandoc-reference.docx`
n'existent, md2star télécharge **par défaut** (depuis v2.5.0) le
template `deraison.ai` et le met en cache (XDG) :

```
https://deraison.ai/template.docx
https://deraison.ai/template.pptx
```

Passez `--no-remote-templates` (ou le commutateur `--offline`) pour
sauter ce téléchargement et utiliser le template embarqué dans le
wheel. Un échec de téléchargement (pas de réseau, 404, timeout)
retombe aussi sur le template embarqué : une conversion n'échoue
jamais parce que `deraison.ai` est injoignable.

**Global** (modifie le défaut embarqué) : modifiez les modèles dans
`md2star/data/` pour changer polices, marges ou logos. Relancez
`make reinstall` ensuite pour que les changements prennent effet.

---

## Documentation Développeur

- [Guide Développeur](docs/developer_guide.md)

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

Aucun `.md` que vous traitez ne peut faire d'appel réseau de son
propre chef. Les images distantes restent opt-in via
`--allow-remote-images`. Depuis v2.5.0, le template de référence
`deraison.ai` est téléchargé par défaut quand aucun
`template.{docx,pptx}` local n'existe (mis en cache XDG, repli sur le
template embarqué en cas d'échec) ; `--no-remote-templates` le saute.
Le commutateur `--offline` est le coupe-circuit dur qui interdit tout
accès réseau et rend le refus explicite dans les scripts. Modèle de
sécurité complet : **[SECURITY.md](SECURITY.md)**.

## Feuille de route

- Voir **[ROADMAP.md](ROADMAP.md)** pour ce qui arrive et ce qui n'est
  explicitement pas dans le périmètre.
- Voir **[CHANGELOG.md](CHANGELOG.md)** pour le diff par version.
- Voir **[LANDSCAPE.md](LANDSCAPE.md)** pour un comparatif de md2star
  face aux outils voisins (en anglais).

## Contribuer

Voir **[CONTRIBUTING.md](CONTRIBUTING.md)** pour le démarrage rapide,
l'organisation du projet et la checklist de PR. TL;DR : `make dev`
+ `python -m pytest tests/` + `ruff check md2star/ tests/`.

---

## Licence

Distribué sous la **[Licence BSD 3-Clause](LICENSE)** — la même licence
permissive que celle utilisée par scikit-learn et d'autres projets
scientifiques majeurs en Python.

**Auteur :** [Warith HARCHAOUI](https://www.linkedin.com/in/warith-harchaoui/)
