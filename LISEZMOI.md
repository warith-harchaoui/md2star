# md2star

[🇫🇷](https://github.com/warith-harchaoui/md2star/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/md2star/blob/main/README.md)

[![PyPI](https://img.shields.io/pypi/v/md2star.svg)](https://pypi.org/project/md2star/)
[![CI](https://github.com/warith-harchaoui/md2star/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/md2star/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Licence : BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)
![Statut : stable](https://img.shields.io/badge/status-stable-brightgreen.svg)
[![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#la-promesse)

> **md2star** convertit du Markdown en `.docx`, `.pptx` et `.pdf`
> brandés, de bout en bout, en s'appuyant sur Pandoc, des templates
> soignés et une automatisation pragmatique.

![logo](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/logo.png)

`md2star` est un outil en ligne de commande multiplateforme qui
habille **Pandoc** d'une couche de style. Il règle ce que Pandoc seul
laisse en plan : espacement des listes, injection de bibliographie,
formules LaTeX, diagrammes Mermaid, intégration d'images, largeur des
tableaux, isolation des diapositives PPTX. Vous restez dans le
Markdown, sans jamais rouvrir Word pour rattraper la mise en page.

md2star a fait ses preuves : disponible sur PyPI, intégration continue au
vert à chaque envoi, versions taguées selon le versionnage sémantique
(actuellement v3.1.3, la deuxième version la plus élevée de la suite
[AI Helpers](https://github.com/warith-harchaoui/ai-helpers)). Il s'appuie
sur deux paquets sœurs de cette même suite : `os-helper` (primitives
partagées de système de fichiers et de journalisation) et
`best-engine-ai-helper` (le transport local des trois passes IA
optionnelles : le correcteur syntaxique `--lint`, la rédaction de textes
alternatifs, la reconstruction `--diagrams`).

## La promesse

**Local d'abord, par conception.** md2star tourne entièrement sur votre
machine : le Markdown devient DOCX, PPTX ou PDF localement, via
Pandoc et LibreOffice. Vos documents ne partent jamais vers un service
tiers, pas de télémétrie, pas de compte, aucune dépendance au cloud. Il
fait partie de la suite [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) :
vos données vous appartiennent, grâce à de l'Open Source local d'abord.

*La seule réserve honnête :* le **contenu** de votre document reste local. Deux
commodités optionnelles, clairement signalées, peuvent toucher le réseau, et
seulement si vous les y autorisez. Le template par défaut se télécharge une
fois depuis `deraison.ai` quand aucun `--reference-doc` local n'est fourni
(passez `--offline` pour forcer le template embarqué et ne rien contacter), et
les images distantes `![](https://…)` ne sont intégrées que si vous passez
`--allow-remote-images`. Dans les deux cas, votre Markdown lui-même ne quitte
jamais votre machine.

*Mode DOCX, l'algorithme d'ingénierie en cinq étapes de Musk rendu en direct :*

| Light | Dark |
|---|---|
| ![md2star DOCX, clair](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/light.png) | ![md2star DOCX, sombre](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/dark.png) |

*Mode PPTX, le pitch deck 10/20/30 de Kawasaki :*

| Light | Dark |
|---|---|
| ![md2star PPTX, clair](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/pptx-light.png) | ![md2star PPTX, sombre](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/pptx-dark.png) |

*Mode GUI, l'éditeur local façon Overleaf avec aperçu PDF en direct
(`md2star gui`) :*

| Light | Dark |
|---|---|
| ![md2star GUI, clair](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/gui-light.png) | ![md2star GUI, sombre](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/gui-dark.png) |

## Documentation

[💻 Documentation](https://deraison.ai/ai-helpers/docs/md2star-doc/)

[🗺️ Paysage](https://github.com/warith-harchaoui/md2star/blob/main/PAYSAGE.md)

[📋 Exemples](https://github.com/warith-harchaoui/md2star/blob/main/EXEMPLES.md)

## Pourquoi md2star ? (la réponse honnête au « utilise juste Pandoc »)

Pandoc est un **convertisseur** ; md2star est un **livrable**. Pandoc
transforme du Markdown en un `.docx` valide ; md2star transforme du Markdown
en un `.docx` que vous pouvez envoyer à un client sans ouvrir Word, puis le
relit en Markdown éditable quand il vous revient. md2star ne cherche pas à
surpasser Pandoc : il *appelle* Pandoc et y ajoute le template soigné, la
colle Mermaid/images/PDF, le chemin inverse `md2star twin` et un aller-retour
vérifié en CI que Pandoc brut vous force à construire vous-même. Il se pose
*au-dessus* de Pandoc ; il ne vous demande jamais d'abandonner Pandoc.

L'argumentaire complet, les manques de style que laisse sur vos bras un
`pandoc rapport.md -o rapport.docx` brut, le seul point où « utilise juste
Pandoc » n'a pas de réponse (le chemin inverse et la garantie d'aller-retour),
et les cas où Pandoc reste vraiment le bon outil, se trouve dans
**[WHY_MD2STAR_OVER_PANDOC.md](https://github.com/warith-harchaoui/md2star/blob/main/WHY_MD2STAR_OVER_PANDOC.md)**.

## Démarrage rapide

```bash
pipx install md2star          # une seule ligne : les quatre CLI + la GUI
md2star doctor                # vérifie la santé de l'environnement
md2docx rapport.md            # markdown → DOCX
md2pptx diapos.md             # markdown → PPTX
md2pdf  article.md            # markdown → PDF (nécessite LibreOffice)
md2star gui                   # éditeur navigateur local, aperçu PDF en direct
md2star twin rapport.pdf      # n'importe quel document → un jumeau Markdown éditable
md2star audit presentation.pptx  # ce qui cloche dans un deck : chevauchements, débordements, corps minuscule
```

Vous préférez `pip` ? Deux fichiers `requirements` correspondent aux
profils d'installation : `pip install -r requirements.txt` pour la CLI,
`pip install -r requirements-gui.txt` pour la CLI et la GUI (même wheel,
la GUI n'ajoute aucune dépendance Python).

Vous préférez HTTP ou MCP ? md2star embarque aussi une surface FastAPI et un
serveur MCP :

```bash
pip install 'md2star[api,mcp]'

md2star-api                    # FastAPI : /gui, /health, /doctor, /convert, /extract, /audit, docs sur /docs
curl -F 'file=@rapport.md' 'http://localhost:8000/convert?fmt=docx' -o rapport.docx
# ouvrez http://localhost:8000/gui pour un banc d'essai minimal dans le navigateur

md2star-mcp                    # mêmes outils (doctor / convert) via MCP
```

> Le serveur `md2star-api` sert aussi un **banc d'essai minimal** dans le
> navigateur, sur `GET /gui` : déposez un `.md`, choisissez un format,
> téléchargez le résultat. C'est le petit frère de l'éditeur complet
> `md2star gui` (aperçu PDF en direct).

Vous préférez click ? `md2star-x docx|pptx|pdf|gui|doctor` est une façade click
au-dessus du même pipeline (fournie avec l'installation cœur). md2star se
distribue aussi comme **Claude Skill / OpenCode skill**, pour qu'un agent le
pilote : voir [`skills/md2star/`](https://github.com/warith-harchaoui/md2star/blob/main/skills/md2star/SKILL.md) et
[`skills/README.md`](https://github.com/warith-harchaoui/md2star/blob/main/skills/README.md). Le catalogue complet de ce qui
déclenche md2star (formulations, commandes, situations de fichier) vit dans
**[TRIGGERS.md](https://github.com/warith-harchaoui/md2star/blob/main/TRIGGERS.md)**.

Voir **[docs/installation.md](https://github.com/warith-harchaoui/md2star/blob/main/docs/installation.md)** pour la matrice
complète par OS (macOS / Ubuntu / Fedora / Arch / Windows), le tableau
de dépendances par fonctionnalité et le guide de dépannage.

## Formats pris en charge

| Format | Statut | Pré-requis                        | CLI                       |
|--------|--------|-------------------------------------|-----------------------------|
| DOCX   | Beta   | Pandoc                            | `md2docx fichier.md`      |
| PPTX   | Beta   | Pandoc                            | `md2pptx fichier.md`      |
| PDF    | Beta   | Pandoc + LibreOffice (`soffice`)  | `md2pdf  fichier.md`      |

« Beta » veut dire que le format marche pour les cas courants, dispose
de tests automatisés et a déjà servi à produire de vrais documents.
Le bug de rendu des tableaux qui plombait la v1.x côté PDF (les
cellules s'empilaient en colonne au lieu de former une grille) est
corrigé depuis la v2.0.0 ; le template embarqué a été reconstruit sur
une base propre côté Pandoc.

## Exemples (les plus parlants)

**1. Markdown nu → DOCX brandé**

```bash
md2docx rapport.md --author "Ada Lovelace"
```

Vous obtenez `rapport.docx` avec les polices, marges et styles de
titres du template intégré, le premier `# Titre` promu en titre du
document, la date du jour localisée d'après la langue détectée, et
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

Le DOCX est rendu via LibreOffice sans interface, si bien que le PDF
hérite de tout le travail de md2star : template brandé, PNG Mermaid,
styles de tableaux, dates localisées.

Un livre de recettes complet vit dans **[EXAMPLES.md](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md)**.

---

## GUI locale (`md2star gui`)

Vous préférez le navigateur au terminal ? `md2star gui` lance un
éditeur local façon Overleaf : le Markdown à gauche, un **aperçu PDF
en direct** à droite et le téléchargement DOCX, PPTX ou PDF en un
clic.

```bash
pip install 'md2star[gui]'    # commande d'installation explicite : « je veux la GUI »
md2star gui                   # ouvre http://127.0.0.1:8765 dans le navigateur
md2star gui --port 9000       # choisit un port (repli automatique si occupé)
md2star gui --no-browser      # affiche juste l'URL, sans ouvrir le navigateur
```

> `md2star[gui]` pointe vers le **même wheel** que `md2star` : la GUI est
> déjà incluse et n'ajoute aucune dépendance Python, donc `pip install
> md2star` la contient déjà. La forme `[gui]` dit juste plus clairement
> « je viens pour l'éditeur ».

Ce qu'elle apporte :

- **Aperçu PDF en direct**, rendu dans la page via PDF.js, sans détour
  par Word ni par un lecteur PDF.
- **Explorateur de dossier** confiné au dossier que vous ouvrez, pour
  éditer tous les `.md` d'un projet (ouvrir, lire, enregistrer, créer,
  supprimer) sans quitter la page.
- **Template de référence en session** : glissez un `template.docx` ou
  `template.pptx` et la session brande sa sortie avec.
- **Sauvegarde automatique des brouillons** dans le cache, pour ne
  jamais perdre votre texte après un plantage du navigateur ou un
  redémarrage.

Elle est **locale d'abord et fonctionne hors ligne** : le serveur
n'écoute que sur `127.0.0.1`, tout le frontend (PDF.js, CodeMirror,
Tailwind, polices) est embarqué dans le paquet et elle appelle
exactement le même convertisseur que la CLI. Aucune donnée ne quitte
votre machine. Depuis la v2.6.0, la GUI est incluse dans le wheel
principal : rien de plus à installer.

---

## Fonctionnalités

- **Conversion sans friction** : écrivez en Markdown avec votre éditeur préféré (`emacs`, `vim`, `Sublime Text`, `Obsidian`, …) et produisez des `.docx`, `.pptx`, `.pdf` stylés.
- **GUI locale** (`md2star gui`) : un éditeur navigateur hors ligne (localhost uniquement) avec aperçu PDF en direct, explorateur de dossier confiné, envoi de template en session et sauvegarde automatique des brouillons. Incluse dans le wheel principal, rien de plus à installer. Voir [GUI locale](#gui-locale-md2star-gui).
- **Support LaTeX** : rendu solide des formules complexes, dans les documents comme dans les diapositives.
- **Diagrammes Mermaid** : les blocs ` ```mermaid ` sont rendus localement en PNG via la CLI officielle Mermaid et intégrés automatiquement (nécessite Node.js ≥16).
- **Métadonnées intelligentes** :
  - **Extraction automatique du titre** depuis votre premier `# Titre`.
  - **Injection d'un sous-titre** combinant l'auteur et la date localisée.
  - **Détection de la langue** via `langdetect` : formats de date fournis pour 10 langues (anglais, français, espagnol, allemand, italien, portugais, néerlandais, russe, japonais, chinois), avec noms de jours et mois traduits pour 7 d'entre elles (fr, es, de, it, pt, nl, ru). Par exemple `dimanche 10 mai 2026` plutôt que `Sunday May 10, 2026`.
- **Prêt pour la recherche** : intégration **BibTeX** native via le `citeproc` de Pandoc, pour les documents à bibliographie gérée.
- **Notes de bas de page natives** : les footnotes Markdown (`texte[^1]` + `[^1]: …`) passent directement par l'extension `footnotes` de Pandoc et deviennent de vraies notes Word. Le DOCX obtient de vraies notes en bas de page, le PPTX les regroupe en notes par diapositive. Aucune syntaxe spéciale, aucun prétraitement. Voir [EXAMPLES.md §10](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md#10-footnotes).
- **Nettoyages automatiques** (petit confort discret) : téléchargement des images `http(s)://` pour l'intégration (opt-in), conversion des `<table>` HTML en pipe-tables Pandoc et isolation des images sur leur propre diapositive PPTX quand elles cohabitent avec un tableau (sinon Pandoc les supprime).
- **Réversible par conception** : la sortie de md2star est un rendu *fidèle et récupérable*, pas une impasse à sens unique. Relisez le DOCX avec Pandoc et vos titres, votre emphase `**gras**`/`*italique*`/`` `code` ``, vos tableaux et vos listes reviennent intacts ; rendez jusqu'au PDF et relisez-le avec [kreuzberg](https://github.com/Goldziher/kreuzberg) : l'aller-retour `md → docx → pdf → texte` est l'identité exacte `g(f(x)) = x`, pour la prose, les listes à puces, les documents multi-pages et les notes de bas de page (vérifié en CI). Les conversions répétées convergent vers un **point fixe stable** au lieu de dériver. Voir [Fidélité de l'aller-retour](#fidélité-de-laller-retour).
- **Jumeau Markdown (sens inverse)** : `md2star twin <fichier>` relit **n'importe quel PDF, ou tout ce que LibreOffice sait convertir en PDF,** en un `<nom>.md` *éditable* **plus un dossier `assets/`**. Les tableaux reviennent en pipe-tables GFM ; chaque image intégrée est extraite puis reliée à nouveau. Ajoutez `--diagrams` (opt-in, nécessite un modèle local, voir le Linter LLM ci-dessous) : les figures en nœuds et flèches sont alors **ré-écrites en Mermaid** via une boucle de comparaison visuelle guidée par la cible. Un candidat est rendu avec le même `mmdc` que le sens direct et comparé à l'original extrait par un modèle de vision local ; le tout itère jusqu'à correspondance ; les autres figures vectorielles nettes sont ré-écrites en SVG éditable de la même façon. Le PNG extrait reste toujours conservé en repli, donc rien n'est jamais perdu. Tout se dégrade proprement : si le modèle local ne peut pas être résolu, les images restent de simples PNG extraits. Nécessite `pip install 'md2star[ocr]'`.
- **PPTX intelligent gabarit** : `md2pptx --smart-layout --template <gabarit-designer.pptx>` mappe chaque diapositive sur les vraies mises en page nommées d'un gabarit de designer (une présentation marketing en propose typiquement 20 à 40) au lieu des ~7 mises en page génériques de Pandoc. La sélection est **mesurée avant d'être jugée** : le contenu de chaque diapositive est compté (mots, puces, images, taille du tableau) puis les placeholders de chaque mise en page sont convertis, depuis leur géométrie EMU, en une capacité de texte à un **plancher de 30 pt** — la règle 10/20/30 de Guy Kawasaki, qui transforme « est-ce que ça tient ? » en arithmétique plutôt qu'en opinion. Les mises en page qui ne peuvent physiquement pas accueillir la diapositive (une image sans emplacement image, un tableau sans emplacement de corps) sont écartées d'emblée ; les autres sont classées par taux d'occupation autour d'une cible de ~55 %, pour qu'une diapositive ne soit ni entassée ni perdue. Un LLM tranche ensuite parmi les candidates plausibles — il voit désormais les quantités puis la capacité de chaque mise en page, non plus une simple liste de caractéristiques — et **la géométrie le corrige** s'il nomme une mise en page incapable de porter le contenu. La **Ralph Eyeball Loop peut désormais déplacer une diapositive** au lieu de seulement la retoucher : quand le juge signale une diapositive que sa mise en page ne porte pas, la boucle re-sélectionne depuis le classement géométrique plutôt que de rétrécir le corps sur une décision fausse dès le départ (une mise en page déjà quittée n'est jamais reproposée). La composition est notée elle aussi, depuis la géométrie du gabarit : contenu entassé dans un coin, boîte de corps placée au-dessus de son titre, boîtes qui ne partagent aucun bord, image focale sur une ligne des tiers, enfin le **rapport d'aspect réel** de chaque image comparé à celui de sa boîte — lu dans l'en-tête du fichier, si bien qu'un panorama va vers une mise en page image-en-haut puis un portrait vers une moitié-moitié, sans qu'aucune de ces deux règles soit écrite. Un écart est signalé dans les termes qu'un lecteur remarquerait (« il sera letterboxé ou recadré »). Les URL distantes puis les fichiers illisibles sont ignorés plutôt que pénalisés : la sélection ne fait aucune E/S réseau, puis une absence de signal n'est pas un mauvais signal ; un modèle de vision **confirme ou corrige visuellement** ce choix en comparant les vraies vignettes rendues des candidats, pas seulement leurs légendes — et les candidats qu'on lui montre viennent du classement géométrique de cette diapositive, de sorte que l'arbitrage se fait entre des mises en page dont le modèle de capacité dit qu'elles peuvent la porter, et non entre celles que le catalogue liste en premier (c'est ainsi qu'un modèle de vision finit par recommander une composition de contenu à deux colonnes pour une couverture). Sans pouvoir non plus aplatir la présentation : interrogé diapositive par diapositive, un modèle répond volontiers la même mise en page à chaque fois, or un arbitrage entre quasi-égaux n'autorise pas à redessiner, donc dès qu'une mise en page porte la moitié des diapositives, une correction supplémentaire vers elle est déclinée et le choix mesuré tient ; un assembleur `python-pptx` construit ensuite la présentation directement sur la mise en page choisie. `--reference-slides` descend un cran plus bas que la mise en page : il **clone la diapositive d'exemple du designer** pour cette mise en page puis en remplace le contenu, si bien que la diapositive hérite de ses filets d'accent, de ses chevrons numérotés et de ses traits décoratifs — les formes qui font qu'une présentation *se ressemble* et qu'aucune mise en page ne porte — avec son glyphe de puce, sa graisse, son corps puis sa couleur. Rien de ce qu'il a *écrit* ne suit : chaque cadre de texte est soit rempli avec votre contenu, soit retiré, et le retrait distingue le bouche-trou du dessin (le « 01 » d'une étape numérotée reste, une simple zone de texte part, une forme automatique est vidée mais conservée) ; sa photo d'illustration est retirée du fichier lui-même, et pas seulement de la diapositive. Une page qui ne peut pas porter honnêtement une diapositive est **refusée plutôt que remplie à moitié** — une composition à trois colonnes exige trois puces, une diapositive avec image exige un emplacement photo, une page portant un graphique ou un tableau est refusée d'office — une page composée autour d'une photographie exige une image, puisque la photo d'illustration doit partir et que le reste de la page a été composé autour de sa forme ; une page est enfin refusée quand votre texte devrait **descendre sous 12 pt** pour tenir dans les cadres dimensionnés pour la ligne du designer, la bonne question n'étant pas « est-ce que ça déborde ? » mais « jusqu'où faudrait-il rétrécir ? » — et chaque refus repasse par l'assembleur ci-dessus : l'option ne fait donc qu'ajouter. Parmi les pages qui conviennent, une diapositive avec image prend celle dont l'emplacement est le plus grand, l'ajustement par contenance faisant de cet emplacement la taille réellement vue. La **Ralph Eyeball Loop a deux yeux, dont un seul a besoin d'un modèle** : chaque passe exécute aussi l'audit déterministe sur le fichier qui vient d'être écrit et renvoie chaque constat sous forme de verdict, si bien que `--eyeball-iterations N` fait un vrai travail sur une machine sans modèle de vision, sans LibreOffice et sans réseau — et en cas de désaccord la mesure l'emporte, un modèle qui regarde un rendu ne pouvant pas voir un débordement que le moteur a déjà masqué en rapetissant le corps. Étant une mesure, elle connaît aussi la réponse et pas seulement le grief : un débordement est signalé avec la taille qui tiendrait, donc la correction exacte est appliquée d'un coup au lieu d'être approchée — et quand cette taille passe sous 12 pt, la boucle cesse de proposer de rétrécir et va chercher une boîte plus grande. Elle **s'aiguise aussi des deux côtés sur ce seam** : une diapositive clonée est jugée face à *la page du designer dont elle sort* (la candidate est littéralement cette page avec vos mots dedans, donc un écart parle de cette diapositive et non de la famille de mises en page), et la boucle gagne une correction qu'elle n'avait pas — quand rien de borné ne s'applique, elle déplace la diapositive sur **une autre démonstration de la même mise en page par le designer** avant même d'envisager d'en changer. Ce n'est qu'une fois toutes les pages jugées puis refusées que la diapositive retombe. Ajoutez `--eyeball-iterations N` pour une boucle de comparaison visuelle guidée par la cible qui compare chaque diapositive rendue à la vignette de sa mise en page choisie et applique des corrections bornées (réduire un débordement de texte, limiter les puces, agrandir une image trop petite). La présentation qu'il vous rend est **modifiable, pas seulement jolie** : le titre de chaque diapositive va dans l'emplacement de titre de la mise en page elle-même, si bien que le fichier a de vraies entrées dans le volet plan de PowerPoint puis un ordre de lecture correct pour un lecteur d'écran ; et chaque emplacement resté vide est supprimé au lieu de livrer un fantôme « Cliquez pour ajouter un titre » sous chaque calque. Un bloc Pandoc `::: notes` arrive dans le volet des notes et non sur la diapositive, puis le texte alternatif Markdown arrive dans la description accessible de chaque image. Chaque exécution se termine enfin par un **audit de disposition déterministe** du fichier qui vient d'être écrit — formes hors du cadre, texte sur texte, emplacements non remplis, corps sous 12 pt, enfin texte qui réclame plus de place que sa boîte ne lui en donne (signalé avec la taille qui, elle, tiendrait). Sans modèle, sans rendu, sans réseau : c'est la moitié d'une relecture visuelle que l'arithmétique peut trancher, donc le garde-fou qualité fonctionne encore sur une machine sans aucun LLM. Opt-in (`pip install 'md2star[pptx]'`) et non bloquant, même contrat de moteur que le Linter LLM ci-dessous. Voir [EXAMPLES.md §12](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md#12-template-intelligent-pptx).
- **Audit de présentation** (`md2star audit <deck.pptx>`) : demandez à n'importe quel PowerPoint ce qui ne va pas chez lui — du texte sur du texte, des formes qui dépassent du cadre, des emplacements que personne n'a remplis, un corps sous le plancher de lisibilité de 12 pt, enfin du texte qui réclame plus de place que sa boîte ne lui en donne (signalé avec la taille qui, elle, tiendrait). Il lit **n'importe quel** `.pptx`, pas seulement ceux produits par md2star, et ce n'est que de l'arithmétique sur l'OOXML : aucun modèle, aucun rendu, aucun réseau, et le fichier n'est jamais réécrit. Code de sortie `1` en présence d'un défaut, `0` s'il ne reste que des observations (`--strict` compte aussi les débordements) : il s'insère donc tel quel dans un job CI ou un hook pre-commit ; `--json` pour les machines. Également `POST /audit` sur la surface HTTP, ce qui en fait gratuitement un outil MCP. Nécessite `pip install 'md2star[pptx]'`. Voir [EXAMPLES.md §12](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md#12-template-intelligent-pptx).
- **Résolution souple des chemins d'images** : URL, chemins absolus et chemins relatifs se comportent tous comme attendu. Une référence relative `![](images/foo.png)` se résout par rapport au dossier du fichier source, donc `md2docx sousdossier/fichier.md` depuis n'importe quel répertoire courant retrouve toujours l'image sans avoir à s'y déplacer d'abord.
- **Identité visuelle sans configuration** : déposez un `template.docx` ou `template.pptx` à côté de votre Markdown : md2star le détecte automatiquement comme `--reference-doc`. À défaut, md2star télécharge par défaut (depuis la v2.5.0) le template `deraison.ai` et le met en cache ; passez `--no-remote-templates` ou `--offline` pour utiliser le template embarqué à la place.
- **CLI auto-documentée** : chaque wrapper accepte `--help` / `-h` et affiche d'abord les options propres à md2star, puis `pandoc --help` : toute la surface de conversion est à une commande de distance. Essayez `md2docx --help`, `md2pptx --help` ou `md2star --help`. `md2star doctor` va plus loin et signale aussi les extras optionnels (`[pptx]` / `[ocr]` / `[api]` / `[mcp]`), chacun avec ce qu'il débloque puis la commande `pip` exacte : un extra pip ne laisse aucune trace à l'exécution, sans quoi le seul moyen de découvrir qu'une fonction manque est de la lancer et de la voir échouer.
- **Linter LLM en option** : une passe locale corrige les erreurs de syntaxe (liens d'images cassés, fences non fermées, pipes mal formés) **avant** que Pandoc ne lise le fichier. **Désactivé par défaut**, pour que les conversions restent déterministes ; ajoutez `--lint` pour l'activer. Le backend et le modèle sont choisis par le **contrat brief → engine** de la suite : md2star embarque un `md2star/llm.brief.yaml` versionné décrivant les besoins de ses passes IA ; [`best-engine-ai-helper`](https://pypi.org/project/best-engine-ai-helper/) le résout contre *votre* machine au premier usage, en écrivant le choix concret dans un `md2star/llm.engine.yaml` gitignoré. **Aucun tag de modèle n'est codé en dur dans le paquet** ; le transport (Ollama local pour l'instant) gère lui-même le cycle de vie du démon, donc md2star ne lance jamais `ollama serve` ni `ollama pull`. Si aucun modèle local n'est résolu, `--lint` avertit et retombe sur le Markdown original : la passe n'est jamais bloquante.
- **Texte alternatif rédigé par IA** : avec `--lint`, chaque `![](src)` au texte alternatif vide reçoit une description générée par un modèle de vision, dans la langue même du document, en s'appuyant sur le titre et la prose environnants (mise en cache par image). Le modèle de vision provient du même engine résolu que le linter.
- **Compagnon : adaptateur de templates IA** : pour brander un template PPTX
  d'entreprise dont les noms de mises en page ne suivent pas la convention
  Pandoc, utilisez l'outil compagnon
  [md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt),
  qui construit un document de référence compatible à partir du template et
  de son export PDF.

---

## Installation

`md2star` est un paquet Python distribué sur PyPI. L'installation via
[pipx](https://pipx.pypa.io/) est recommandée : elle isole le paquet
dans son propre venv et met les quatre CLI (`md2star`, `md2docx`,
`md2pptx`, `md2pdf`) sur votre PATH. Pandoc est la seule dépendance
système obligatoire ; LibreOffice n'est requis que pour `md2pdf`,
Node.js que pour Mermaid, Ollama que pour `--lint`.

- macOS 🍎 : `brew install pandoc pipx`
  (installez `brew` grâce à [brew.sh](https://brew.sh/)), ou lancez le
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
make install            # vérifie les dépendances, lance `pipx install .`
```

Deux fichiers de dépendances pip vivent à la racine pour une
installation sans `make` (`pyproject.toml` reste la source de vérité :
ces fichiers installent le paquet en éditable et héritent donc de ses
épinglages de version) :

- `requirements.txt` : **runtime**, installe `-e .` (soit
  `langdetect` et `Pillow`), le strict nécessaire pour lancer
  `md2docx`, `md2pptx` et `md2pdf`.
- `requirements-dev.txt` : **dev et test**, installe `-e .[dev]`
  (pytest, ruff, pytest-cov, pypdf, les dépendances API/MCP et
  `kreuzberg` pour l'aller-retour OCR).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # runtime seul
pip install -r requirements-dev.txt    # + outils de test et de lint
```

### Mise à jour

| Plateforme | Commande |
|------------|----------|
| Toute (installation PyPI) | `pipx upgrade md2star` |
| macOS / Linux depuis les sources | `make update` |
| Windows depuis les sources | `powershell -ExecutionPolicy Bypass -File scripts\update.ps1` |

### Développement local

```bash
make dev                # crée .venv/ avec `pip install -e .[dev]`
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## Guide d'utilisation

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
*Crée `article.pdf`* (via LibreOffice sans interface ; `soffice` doit être sur le PATH).

### 6. Linter LLM en option

```bash
# par défaut : lint désactivé, conversions déterministes
md2docx brouillon.md

# activer (résout un modèle local au premier usage, puis exécute)
md2docx brouillon.md --lint

# no-op explicite (identique au défaut, pour un scripting sans ambiguïté)
md2docx brouillon.md --no-lint
```

Avec `--lint`, une passe locale corrige les liens d'images cassés, les fences non fermées et les pipes de tableaux mal formés avant que Pandoc ne lise le fichier. Le même `--lint` remplit aussi les `![](src)` vides via un modèle de vision local, dans la langue même du document.

**Quel modèle et comment il est choisi (contrat brief → engine).** md2star ne code aucun tag de modèle en dur. Il embarque un `md2star/llm.brief.yaml` versionné décrivant les besoins de ses passes IA (local, texte et vision, faible latence, multilingue). Au premier usage, [`best-engine-ai-helper`](https://pypi.org/project/best-engine-ai-helper/) résout ce brief contre *votre* machine et écrit le backend et le modèle concrets dans un `md2star/llm.engine.yaml` gitignoré ; chaque exécution suivante se contente de lire ce fichier engine. Tous les appels passent par `best_engine_ai_helper.llm.chat` ; le transport (Ollama local pour l'instant) gère lui-même le cycle de vie du démon : md2star ne lance jamais `ollama serve` ni `ollama pull`. Si aucun modèle local n'est résolu, `--lint` avertit sur stderr et retombe sur le Markdown original, si bien que la conversion réussit toujours. `best-engine-ai-helper` est une dépendance cœur, donc cela fonctionne d'emblée dès qu'un runtime de modèle local (Ollama aujourd'hui) est installé.

---

## Adaptateur de templates (dépôt séparé)

Pour les templates PPTX d'entreprise dont les noms de mises en page ne
suivent pas la convention Pandoc, utilisez l'outil compagnon
[md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt). Il
exécute un pipeline en trois phases : extraire thème, logo et formes
du PPTX, classer chaque mise en page avec un modèle de vision local
(Ollama) en la confrontant au PDF associé, puis assembler un document
de référence compatible Pandoc, produisant un `branded_ref.pptx` que
vous repassez à md2star via `--reference-doc`.

Il vit dans son propre dépôt parce que ses dépendances (PyMuPDF, lxml,
python-pptx, requests et un VLM Ollama en cours d'exécution) sont
nettement plus lourdes que ce qu'exige le pipeline de conversion de
base. Son profil de correction (piloté par un VLM) diffère aussi par
nature du cœur déterministe de md2star.

---

## Exemples

Un livre de recettes autonome vit dans **[EXAMPLES.md](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md)**,
couvrant titres, Mermaid, listes, diapositives multi-colonnes, formules
LaTeX, bibliographies, templates brandés, détection de langue, sauts de
page et [notes de bas de page](https://github.com/warith-harchaoui/md2star/blob/main/EXAMPLES.md#10-footnotes).

Vous pouvez aussi trouver des exemples plus complexes dans le dossier
[`tests/examples/`](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples). Pour compiler nativement tous les documents du
dossier en une fois, exécutez le script bash :
```bash
cd tests/examples
./run.sh
```

Voici des fichiers `.docx` et `.pptx` basiques, générés dynamiquement pendant notre suite de tests à partir d'exemples Markdown :

**Exemples de documents Word**
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
- Langue et date (français) [assets/docx/with_lang.docx](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_lang.docx) *(depuis [with_lang.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/docx/with_lang.md))*
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

**Exemples de diapositives PowerPoint**
- Exemple étoffé [assets/pptx/example.pptx](https://github.com/warith-harchaoui/md2star/blob/main/assets/pptx/example.pptx) *(depuis [example.md](https://github.com/warith-harchaoui/md2star/blob/main/assets/pptx/example.md))*
  ```bash
  md2pptx assets/pptx/example.md
  ```
- Template personnalisé [tests/examples/branded_slides.pptx](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/branded_slides.pptx) *(depuis [branded_slides.md](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/branded_slides.md) + [Presentation1.pptx](https://github.com/warith-harchaoui/md2star/blob/main/tests/examples/Presentation1.pptx))*
  ```bash
  md2pptx tests/examples/branded_slides.md --reference-doc tests/examples/Presentation1.pptx
  ```

---

## Qualité et fiabilité

La fiabilité est un objectif de conception. La suite de tests automatisée couvre :
- [x] **Précision des métadonnées** : extraction du titre, injection de l'auteur, composition du sous-titre.
- [x] **Rendu bibliographique** : pipeline citeproc contre l'instantané figé [references.bib](https://github.com/warith-harchaoui/md2star/blob/main/assets/references.bib).
- [x] **Localisation des dates** : rendu des jours et mois en français, injection du format de date.
- [x] **Invariants du préprocesseur** : espacement des listes, préservation des blocs de code, conversion des `<table>` HTML, normalisation des séparateurs de pipe-tables, injection de largeur d'image, détection de langue, repli Mermaid, dépliage du math-in-code, isolation PPTX.
- [x] **Mode hors ligne** : toutes les phases à accès réseau refusent de tourner sous `--offline`.
- [x] **Géométrie des présentations** : `md2star audit <deck.pptx>` mesure n'importe quel PPTX — formes hors du cadre, texte sur texte, emplacements non remplis, corps sous 12 pt, texte qui déborde de sa boîte. Sans modèle : c'est donc un vrai garde-fou et non un avis, exécuté à la fin de chaque conversion `--smart-layout`.
- [x] **Hygiène des diapositives clonées** : avec `--reference-slides`, un gabarit de designer est synthétisé page par page puis la présentation construite est vérifiée dans les deux sens — le filet d'accent, le logo, l'ornement « 01 », le glyphe de puce du masque et la place de l'image dans l'ordre d'empilement survivent tous, tandis qu'aucune ligne du texte bouche-trou du designer ni sa photo d'illustration n'atteint le fichier (la relation de la photo est retirée elle aussi : elle ne peut donc pas voyager dans le paquet sans être vue).
- [x] **Intégrité du comparatif** : les tableaux en étoiles de LANDSCAPE / PAYSAGE doivent correspondre aux CSV dont sont tirées les cartes de positionnement, pour que la figure ne trace jamais des notes que les documents ne revendiquent plus.

### Tests d'intégration (shell)

Nécessite **Pandoc** installé :
```bash
make test
```

### Tests unitaires (Python)

Nécessite **pytest** et votre environnement virtuel généré :
```bash
python -m pytest tests/ -v
```

Pour plus de détails, voir [tests/README.md](https://github.com/warith-harchaoui/md2star/blob/main/tests/README.md).

---

## Fidélité de l'aller-retour

Convertir en `.docx` n'enferme pas votre contenu dans un format binaire. La
sortie de md2star est un **rendu fidèle et réversible** de votre Markdown :
relisez le `.docx` avec n'importe quel lecteur DOCX et le contenu source
revient.

**Ce qui survit à l'aller-retour `md → docx → md`** :

| Élément                           | Récupéré ? |
|------------------------------------|:----------:|
| Titres (niveaux de section)       | ✅ |
| `**gras**` / `*italique*`         | ✅ |
| `` `code` `` en ligne              | ✅ (via Pandoc) |
| Tableaux pipe (chaque cellule)     | ✅ |
| Listes à puces et numérotées       | ✅ |
| Paragraphes                        | ✅ |

**Il atteint un point fixe.** L'aller-retour est idempotent au sens
mathématique : l'exécuter deux fois donne le même document qu'une seule fois
(`g(g(x)) == g(x)`), si bien que les conversions répétées *convergent* au lieu
d'accumuler des scories. C'est vérifié en CI par
[`tests/test_roundtrip.py`](https://github.com/warith-harchaoui/md2star/blob/main/tests/test_roundtrip.py), qui convertit un
échantillon en DOCX, le relit avec le lecteur natif de Pandoc et contrôle à la
fois la survie du contenu et la propriété de point fixe.

La seule chose que md2star *ajoute* à chaque exécution, par conception, est
un **sous-titre de date** localisé et ré-estampillé à la date du jour ; cela
(et des détails cosmétiques sans valeur sémantique, comme le retour à la
ligne ou le nombre exact de tirets dans un séparateur de tableau) est
normalisé avant la vérification d'idempotence. Rien d'autre ne dérive.

**Reproduisez-le vous-même** (n'importe quel lecteur DOCX fonctionne ; la voie
Pandoc intégrée ne demande aucune installation supplémentaire) :

```bash
md2docx rapport.md --offline           # rapport.md → rapport.docx
pandoc rapport.docx -t gfm --wrap=none # rapport.docx → Markdown sur stdout
```

**Le sens `pdf → md` est exact lui aussi, et vérifié en CI.** Rendu jusqu'au
PDF puis relu avec [kreuzberg](https://github.com/Goldziher/kreuzberg)
(`extract_file_sync(path, config=ExtractionConfig(output_format=OutputFormat.PLAIN))`),
l'aller-retour `md → docx → pdf → texte` est l'**identité** `g(f(x)) = x`,
prouvée par égalité exacte du document entier sous une *forme normale*
explicite dans
[`tests/test_roundtrip_ocr.py`](https://github.com/warith-harchaoui/md2star/blob/main/tests/test_roundtrip_ocr.py), exécutée pour de
vrai en CI sur la chaîne complète LibreOffice et kreuzberg. Elle tient pour :

- les **paragraphes** de toute longueur (le retour à la ligne est refusionné) ;
- les **listes à puces** ;
- les documents **multi-pages** (les numéros de page en pied sont normalisés) ;
- les **notes de bas de page**, étiquettes numériques `[^1]` comme nommées `[^aa]` :
  le *texte* de la note est récupéré même si le rendu renumérote l'étiquette.

Ce qu'un PDF ne peut pas rendre, c'est le balisage qu'il n'a jamais stocké :
l'emphase en ligne, les *niveaux* de titres et la structure des tableaux
deviennent du texte brut ; les mots survivent, pas le balisage. Ce balisage
structuré est précisément ce que le lecteur DOCX ci-dessus récupère, si bien
que les deux sens couvrent ensemble tout le document.

---

## Personnalisation

### Paramètres par défaut
Ajustez vos paramètres globaux dans `md2star/data/metadata.yaml` :
```yaml
author: "Votre Nom"
date_format: "%A %e %B %Y"
lang: "fr-FR"
```

Conventions retenues :

  + `date_format` utilise un format `strftime()`.
Voir la [documentation C/POSIX sur le formatage des dates](https://pubs.opengroup.org/onlinepubs/9699919799/functions/strftime.html) pour plus de détails.

  + `lang` utilise une étiquette BCP 47 (par exemple `en-US`, `fr-FR`).
Voir la [RFC 5646](https://datatracker.ietf.org/doc/html/rfc5646) pour plus de détails.

### Modèles de style

Deux niveaux de personnalisation, du plus local au plus global :

**Par projet** (recommandé) : déposez un `template.docx` ou
`template.pptx` à côté de votre Markdown. Tous les wrappers md2star
le détectent et le passent en `--reference-doc`. Committez-le avec vos
sources pour que collaborateurs et CI produisent exactement le même
rendu.

À défaut de `template.docx` (préféré) ou de l'ancien
`.pandoc-reference.docx` (toujours honoré, avec un avis de
dépréciation), md2star télécharge **par défaut** (depuis la v2.5.0) le
template `deraison.ai` et le met en cache sous XDG :

```
https://deraison.ai/template.docx
https://deraison.ai/template.pptx
```

Passez `--no-remote-templates` (ou le commutateur brutal `--offline`)
pour sauter ce téléchargement et utiliser le template embarqué dans le
wheel. Un échec de téléchargement (pas de réseau, 404, timeout) retombe
lui aussi sur le template embarqué, si bien qu'une conversion n'échoue
jamais simplement parce que `deraison.ai` est injoignable. Éditez
ensuite la copie locale ou mise en cache dans Word, PowerPoint ou
LibreOffice, puis committez-la dès que le style vous convient.

**Global** (change le défaut embarqué pour tout projet qui n'a pas
épinglé le sien) : éditez les templates maîtres dans `md2star/data/`
pour changer polices, marges ou logos :
- `md2star/data/template.docx`
- `md2star/data/template.pptx`

Ils sont livrés dans le wheel et servent de repli hors ligne quand
aucun `template.{docx,pptx}` n'est trouvé à côté de votre Markdown.
Après édition, lancez `make reinstall` pour que les changements
prennent effet sur les CLI déjà installées.

---

## Documentation développeur

Pour les contributeurs et les utilisateurs avancés intéressés par les rouages internes de notre logique Python et de nos hooks d'analyse AST, consultez nos guides d'API internes :
- [Guide développeur](https://github.com/warith-harchaoui/md2star/blob/main/docs/developer_guide.md)

---

## Projets connexes

- **[Pandoc](https://pandoc.org/)** : le moteur qui rend la conversion de documents universelle.
- **[MarkItDown](https://github.com/microsoft/markitdown)** : un utilitaire de Microsoft qui fait l'opération inverse, convertissant des documents Office et d'autres formats *vers* le Markdown.
- **[Obsidian](https://obsidian.md/)** : notre environnement recommandé pour écrire du Markdown de haute fidélité.
- **[Zotero](https://www.zotero.org/)** : le compagnon idéal pour gérer vos bibliographies `.bib`.

---

## Dépannage

| Problème | Solution |
|----------|----------|
| `md2docx: command not found` | Ajoutez `~/.local/bin` à votre PATH (`pipx ensurepath`) et redémarrez votre shell. |
| `pandoc: command not found` | Installez [Pandoc](https://pandoc.org/installing.html). |
| Erreurs `mmdc` ou blocs mermaid laissés tels quels | Installez Node.js ≥16, pour que `npx` puisse récupérer `@mermaid-js/mermaid-cli`. |
| Vous voulez activer le linter LLM | Passez `--lint`. Il est désactivé par défaut ; avec `--lint`, le wrapper démarre le démon Ollama et télécharge le modèle à la demande. Nécessite `ollama` sur le `PATH` ; sinon, il ne fait rien silencieusement. |
| `--lint` a affiché une erreur de téléchargement de modèle | Le premier lancement résout et télécharge le modèle local que `best-engine-ai-helper` choisit pour cette machine (voir « Quel modèle et comment il est choisi » ci-dessus ; il n'y a pas de tag fixe, le nom varie donc d'une machine à l'autre). Si le téléchargement a échoué (par exemple hors ligne), md2star retombe silencieusement sur le Markdown original ; réparez votre réseau et relancez. |
| `md2pdf: LibreOffice not found` | Installez LibreOffice (`brew install --cask libreoffice` / `apt-get install libreoffice` / winget). |
| Avertissements de mise en page sur un template PPTX | Normal si un template n'a pas les noms de mise en page standards ; la sortie reste valide. |
| Image distante non intégrée | Passez `--allow-remote-images` pour activer ce téléchargement (md2star est hors ligne par défaut). |

---

## Sécurité et mode hors ligne

Aucun fichier `.md` que vous traitez ne peut déclencher d'appel réseau de son
propre chef. Les images distantes restent opt-in via
`--allow-remote-images`. Depuis la v2.5.0, le template de référence
`deraison.ai` est téléchargé par défaut quand aucun `template.{docx,pptx}`
local n'existe (mis en cache sous XDG, avec repli sur le template embarqué en
cas d'échec) ; `--no-remote-templates` saute cette étape. Le commutateur
`--offline` est le coupe-circuit brutal : il interdit tout accès réseau et
rend le refus explicite dans les scripts. Modèle de sécurité complet :
**[SECURITY.md](https://github.com/warith-harchaoui/md2star/blob/main/SECURITY.md)**.

## Feuille de route et statut

- Voir **[ROADMAP.md](https://github.com/warith-harchaoui/md2star/blob/main/ROADMAP.md)** pour ce qui arrive et ce qui est
  explicitement hors périmètre.
- Voir **[CHANGELOG.md](https://github.com/warith-harchaoui/md2star/blob/main/CHANGELOG.md)** pour le diff par version.
- Voir **[docs/audit.md](https://github.com/warith-harchaoui/md2star/blob/main/docs/audit.md)** pour le dernier audit
  d'ingénierie honnête (forces, risques, priorités).

## Contribuer

Voir **[CONTRIBUTING.md](https://github.com/warith-harchaoui/md2star/blob/main/CONTRIBUTING.md)** pour le démarrage rapide,
l'organisation du projet et la checklist de PR. En résumé : `make dev`
+ `python -m pytest tests/` + `ruff check md2star/ tests/`.

## Variante Rust

Un projet distinct, [`md2star-rs`](https://github.com/warith-harchaoui/md2star-rs), poursuit le
même objectif « Markdown en entrée, DOCX/PPTX fidèle en sortie » sans Pandoc : un pipeline
lecteur → AST → écrivain entièrement en Rust, compilé en un binaire statique unique sans
dépendance d'exécution — pas d'installation de Pandoc requise, ce qui le rend utilisable sur
téléphone, sur des machines verrouillées et (à terme) en WASM. La contrepartie : c'est un
sous-ensemble ciblé, pas un remplacement — pas de bibliographie ni de citations (aucun
processeur CSL Rust stable pour l'instant), pas de conversion mathématique vers OMML, pas
d'images intégrées ni de relations d'hyperliens dans le moteur PPTX. Utilisez `md2star-rs` pour
un binaire unique sans installation, pour du Markdown → Word/PowerPoint simple ; restez sur
`md2star` (ce paquet) pour les citations, les mathématiques et la fidélité maximale.

## Auteur

[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

---

## Licence

Distribué sous la **[Licence BSD 3-Clause](https://github.com/warith-harchaoui/md2star/blob/main/LICENSE)**, la même licence
permissive que celle utilisée par scikit-learn et d'autres projets
scientifiques majeurs en Python.

**Auteur :** [Warith HARCHAOUI](https://www.linkedin.com/in/warith-harchaoui/)
