# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/md2star/blob/main/LANDSCAPE.md)

Comparaison concurrentielle honnête dans l'espace « Markdown →
document soigné », mesurée face à `md2star`. Les notes vont de ⭐ (1)
à ⭐⭐⭐⭐⭐ (5), évaluées sur la tâche visée par `md2star` : partir
d'une source Markdown de référence et produire un DOCX / PPTX / PDF à
l'allure voulue, hors ligne par défaut, avec des diffs propres et
compatibles git. Un outil optimisé pour un tout autre usage (édition
Office native, typographie nativement LaTeX) n'est pas pénalisé ; la
note reflète seulement l'adéquation à *ce* créneau. Choisir le bon
outil compte plus que choisir le nôtre : si votre équipe vit dans des
documents Office natifs, Word / Google Docs bat md2star et nous le
disons.

Nous nous notons honnêtement : `md2star` n'a pas 5 étoiles sur chaque
ligne. Ce document est maintenu à la main et reflète l'état de chaque
projet à la mi-2026 ; ouvrez une issue si quelque chose est dépassé.

## En un coup d'œil

<!-- TABLE:START -->
| Conversion Markdown | Office+PDF | Citations | Diagrammes | Maths | Charte | CLI une-cmd | Hors ligne | LLM local | Retour-MD | Gabarit-ajusté | Auto-contrôle | Modifiable |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **md2star** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Pandoc | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Pandoc + gabarits | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Typst | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ |
| md2pptx | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Marp | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| Slidev | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| reveal.js | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| MkDocs | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| Docusaurus | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| LibreOffice | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Overleaf | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| Export Obsidian | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ |
| Gamma / Copilot | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Presenton | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
| PPTAgent | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Word / Google Docs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/paysage.png)

La carte est un résumé en 2D des douze critères : à lire comme une forme, pas comme un classement. « md2star » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Académique ↔ Design** et **Vertical — Visuel ↔ Complet** : ce sont les pôles avec lesquels la figure elle-même est dessinée, reconstructible depuis le tableau ci-dessus avec `scripts/positioning.py`.
<!-- FIGURE:END -->

## Légende des colonnes

Les douze critères, en bref :

- **Office+PDF**: qualité et fiabilité des sorties `.docx`, `.pptx`
  et PDF (PDF sans exiger une chaîne LaTeX).
- **Citations**: citations / bibliographie (BibTeX, CSL, Zotero).
- **Diagrammes**: Mermaid / Graphviz / PlantUML rendus dans le
  document.
- **Maths**: typographie LaTeX `$…$` / `$$…$$`, en ligne et en bloc,
  rendue correctement dans la sortie choisie.
- **Charte**: gabarits à la charte maison (polices, couleurs,
  couverture, en-têtes/pieds) pour un rendu voulu, pas un export brut.
- **CLI une-cmd**: une seule commande transforme le Markdown en
  livrable, sans chaîne d'outils à câbler à la main.
- **Hors ligne**: fonctionne entièrement hors ligne par défaut, sans
  appels réseau silencieux.
- **LLM local**: fonctions optionnelles de LLM local (lint, résumés,
  propositions de fusion) via Ollama ou équivalent.
- **Retour-MD**: reconvertit un DOCX / PPTX / PDF fini en un jumeau
  Markdown éditable.
- **Gabarit-ajusté** : pour le PPTX, l'outil décide-t-il *sur quelle
  diapositive du gabarit du graphiste* chaque contenu doit atterrir,
  en jugeant la quantité réelle de contenu ? À distinguer de
  **Marqué** : ce sont deux affirmations différentes. Marqué signifie
  « la sortie porte les bonnes polices puis les bonnes couleurs » ;
  Gabarit-ajusté signifie « le contenu a atterri sur la bonne
  diapositive ». Un outil peut réussir la première puis manquer la
  seconde — pandoc n'atteint qu'une septaine de mises en page nommées,
  par une heuristique fixe, quel que soit le contenu du gabarit.

  Le Designer de PowerPoint obtient une bonne note ici, à juste titre :
  il lit le texte puis les images d'une diapositive et propose des
  arrangements équilibrés. La différence tient au vocabulaire employé
  — Designer compose depuis le catalogue de Microsoft, là où md2star
  cherche à mapper sur les mises en page de *votre* graphiste sans
  toucher à son travail.

- **Auto-contrôle** : l'outil inspecte-t-il **sa propre sortie** pour
  vous dire ce qui ne va pas — texte hors du cadre, deux formes l'une
  sur l'autre, corps trop petit pour être lu, plus de texte que la
  boîte n'en contient — ou vous rend-il un fichier en supposant que le
  rendu s'est bien passé ? La plupart des convertisseurs sont dans le
  second cas et c'est pourquoi une mauvaise diapositive se découvre
  d'ordinaire en ouvrant la présentation. L'avertissement « Overfull
  \hbox » de LaTeX est le plus ancien exemple du premier cas ; le
  vérificateur d'accessibilité de PowerPoint en est le plus connu.

- **Modifiable** : ce que vous pouvez encore *faire* du fichier ensuite.
  Du vrai texte dans de vrais emplacements, un plan que PowerPoint sait
  lire, des formes natives que l'on peut déplacer — par opposition à un
  artefact plat qui a seulement l'air juste, ce que livrent d'ordinaire
  l'export d'un HTML rendu ou une présentation générée par IA. Le critère
  est repris de l'*indice de modifiabilité* (L0–L5, lu dans la structure
  du fichier lui-même) de
  [SlidesGen-Bench](https://arxiv.org/html/2601.09487), dont le résultat
  principal mérite d'être redit : sur les systèmes mesurés, la force
  esthétique était **inversement corrélée** à la profondeur de
  modifiabilité et aucun ne réussissait les deux. Une « barrière
  structurelle », selon ses termes. Tout le pari de md2star est que cette
  barrière vient de ce que l'on *génère* le design au lieu d'en hériter :
  prenez le design du gabarit d'un vrai graphiste et la sortie peut
  rester de l'OOXML natif de bout en bout — c'est aussi par là que
  PPTAgent atteint la même note.

Les cases qui seraient « non applicables » dans la grille maintenue à
la main (par ex. une note Office+PDF pour un outil uniquement de
slides ou de site web) valent ⭐ ici, afin que le tableau reste en
étoiles pures : à lire comme « pas fait pour cette dimension ».

### Deux lignes ajoutées par la littérature 2026

**Presenton** est ce qui ressemble le plus à un Gamma open source :
auto-hébergeable, avec vos propres modèles, une invite ou un document en
entrée et du PPTX/PDF en sortie. Il partage le terrain hors-ligne et
LLM-local de md2star et s'en écarte sur la seule question qui compte
ici : il *écrit* la présentation, là où md2star place une source de
vérité Markdown sur le gabarit d'un graphiste et laisse son design
tranquille.

**PPTAgent** ([EMNLP 2025](https://aclanthology.org/2025.emnlp-main.728/))
est le système de recherche auquel le chemin `--reference-slides` de
md2star doit son idée centrale : éditer une *diapositive de référence*,
pas une mise en page. Il mérite pour cela l'autre cinq étoiles de la
colonne Gabarit-ajusté et la note maximale en Modifiable, puisqu'une
diapositive de référence éditée est native par construction. Là où il
diffère : il rédige aussi le contenu, son auto-contrôle PPTEval est un
banc d'évaluation pour l'article plutôt qu'un garde-fou que l'outil
passe sur votre fichier et il lui faut un modèle à chaque étape. md2star
garde les mots de l'auteur, exécute son audit sans aucun modèle et
retombe sur une conversion Pandoc ordinaire quand aucun moteur n'est
disponible.

## Positionnement

`md2star` se place volontairement à l'intersection d'une **source
Markdown de référence** (diffs en texte brut, archive grepable, aucun
risque de format propriétaire) et d'une **sortie de document soignée
et à la charte** (un DOCX, PPTX ou PDF à l'allure voulue, pas un export
brut), pilotée par **une seule commande**, **hors ligne**, avec des
assistances **LLM local** optionnelles et un **retour** vers le
Markdown. Il ne cherche volontairement **pas** à battre Typst ou
Overleaf sur les maths nativement LaTeX, ni Word / Google Docs sur
l'édition Office native.

Choisissez `md2star` quand **toutes** ces conditions sont réunies :

- Votre référence est en Markdown : vous voulez des diffs en texte
  brut, une archive grepable et aucun risque de format propriétaire.
- Vous produisez du DOCX, PPTX ou PDF comme livrable soigné (articles,
  rapports internes, slides client, supports de formation, brouillon
  de livre destiné à un correcteur).
- Vous voulez la charte intégrée et une conversion en une commande,
  pas une chaîne gabarits + PDF à câbler à la main.
- Vous tenez au hors-ligne par défaut, à l'absence de télémétrie et à
  des assistances LLM local optionnelles.
- Votre équipe est petite (1–10) et asynchrone ou vous travaillez
  seul sur plusieurs appareils.

Là où `md2star` ne domine délibérément pas le tableau :

1. **Maths**: 3 étoiles, sa ligne la plus faible. Les maths LaTeX
   poussées reviennent à Typst, Overleaf ou Pandoc brut ; md2star rend
   bien les maths en ligne et en bloc courantes, mais n'est pas un
   substitut LaTeX complet.
2. **Office+PDF**: 4 étoiles. La sortie est soignée et fiable, mais
   les éditeurs natifs (Word / Google Docs, LibreOffice) et Overleaf
   la dépassent sur la fidélité de rendu brute dans leur propre format.
3. **Citations & Diagrammes**: 4 étoiles chacun. Suffisant pour
   rapports et articles ; Pandoc et Quarto vont plus loin sur les
   styles CSL exotiques et la longue traîne des moteurs de diagrammes.

## Quand choisir quoi

- **`md2star`**: documents issus de Markdown qui doivent partir en
  DOCX / PPTX / PDF soigné et à la charte, hors ligne, en une commande,
  avec des diffs git propres et un retour vers le Markdown.
- **Pandoc**: le convertisseur universel brut quand on accepte de
  câbler soi-même templates et chaîne PDF (md2star repose dessus).
- **Pandoc + templates**: le même moteur une fois qu'on a construit
  et qu'on maintient son propre jeu de gabarits pour la charte.
- **Quarto**: pipelines notebook R/Python → publication avec code
  exécutable et citations.
- **Typst**: une alternative LaTeX rapide et moderne pour des PDF
  riches en maths et typographiés avec précision.
- **md2pptx**: Markdown → PPTX sans Pandoc dans la boucle et de loin
  le plus grand vocabulaire d'écriture de cette liste (cartes,
  entonnoirs, diapositives de tâches, sommaire généré, hooks Python en
  ligne). À choisir quand ce vocabulaire vous intéresse et que vous
  acceptez de l'apprendre ; le pari de md2star est l'inverse : le
  Markdown reste simple puis c'est le *gabarit* qui porte le design.
- **Marp / Slidev / reveal.js**: decks de slides en Markdown ou HTML
  avec rechargement à chaud (slides uniquement, pas de chaîne
  Office / PDF à la charte).
- **Gamma / Copilot**: quand vous n'avez pas de document source et
  voulez une présentation générée depuis une consigne, dans le cloud,
  en acceptant que le catalogue de l'outil fasse le design.
- **MkDocs / Docusaurus**: sites de documentation depuis Markdown,
  pas des livrables Office ou PDF.
- **LibreOffice**: édition Office native et DOCX / PPTX solides quand
  votre source n'est pas du Markdown.
- **Overleaf**: LaTeX collaboratif avec PDF nativement LaTeX et
  citations.
- **Obsidian export**: notes Markdown avec export piloté par plugins
  et un peu d'outillage LLM local hors ligne.
- **Word / Google Docs**: quand l'édition Office native ou la
  co-édition en temps réel est le vrai produit.

## Méthodologie

- Nous notons le **comportement livré** de chaque outil, pas sa
  feuille de route, dans sa **configuration par défaut**, pour l'usage
  que **la plupart des utilisateurs** en font réellement. (Pandoc pilote
  techniquement HTML → Chrome headless → PDF, mais en pratique personne
  ne le fait sans wrapper, donc sa note PDF reflète le défaut dépendant
  de LaTeX.)
- Contrôle de biais : quand `md2star` hésite entre deux notes, nous
  prenons la **plus basse** ; quand un concurrent hésite, nous prenons
  la note que son utilisateur type défendrait. Nous ne relèverons pas
  notre auto-évaluation sans confirmation indépendante.
- Si une note vous semble fausse, ouvrez une issue avec l'outil, la
  colonne, la note actuelle et proposée et une raison concrète (lien
  vers une fonctionnalité, un benchmark, un document représentatif).

## Sources et date de relevé

**Sources relevées le 27/10/2026, face à md2star v3.10.0.** La colonne md2star
a été relue dans ce dépôt à cette version. Les colonnes concurrentes viennent
de la lecture de la mi-2026 signalée en tête de ce document, notées d'après la
documentation publiée de chaque projet : lisez-les donc comme « à la mi-2026 »
puis ouvrez une issue dès qu'un projet a bougé.

Les deux moitiés du tableau ne sont pas sourcées de la même façon et la
différence mérite d'être dite :

- **La ligne de md2star** se lit dans le code, pas dans le README. Chaque
  affirmation a une commande derrière elle : `md2star doctor` pour ce qui est
  réellement installé, `md2docx --bib` pour Citations, `md2docx` sur un bloc
  `mermaid` pour Diagrams, `md2star twin` pour Reverse-MD, `md2star audit` pour
  Self-check puis `md2pptx --smart-layout --template` pour Template-fit — la
  seule ligne qui exige un LLM+VLM local résolu avant même de pouvoir être
  exercée. La note Editable, c'est le fichier lui-même : du vrai texte dans de
  vrais emplacements, ce que l'audit parcourt.
- **Toutes les autres lignes** sont notées d'après la documentation publiée du
  projet, lue comme la lit un utilisateur potentiel : configuration par défaut,
  comportement documenté, aucune version privée. Quand la documentation reste
  muette, la cellule vaut ⭐ plutôt qu'une supposition.

Sources primaires, ligne par ligne :

- **Pandoc**, **Pandoc + templates** — [le manuel Pandoc](https://pandoc.org/MANUAL.html) :
  `--reference-doc`, `--citeproc` puis les mises en page nommées du writer PPTX.
- **Quarto** — [le guide Quarto](https://quarto.org/docs/guide/).
- **Typst** — [la documentation Typst](https://typst.app/docs/).
- **md2pptx** — [MartinPacker/md2pptx](https://github.com/MartinPacker/md2pptx)
  et son guide utilisateur, où figure aussi son vocabulaire d'écriture.
- **Marp** — [marp.app](https://marp.app/) · **Slidev** — [sli.dev](https://sli.dev/)
  · **reveal.js** — [revealjs.com](https://revealjs.com/).
- **MkDocs** — [mkdocs.org](https://www.mkdocs.org/) · **Docusaurus** —
  [docusaurus.io](https://docusaurus.io/).
- **LibreOffice** — [libreoffice.org](https://www.libreoffice.org/).
- **Overleaf** — [overleaf.com](https://www.overleaf.com/).
- **Obsidian export** — [obsidian.md](https://obsidian.md/) et son annuaire de
  plugins communautaires ; la ligne note l'écosystème de plugins, pas
  l'application seule.
- **Gamma / Copilot** — [gamma.app](https://gamma.app/) et
  [Copilot dans PowerPoint](https://support.microsoft.com/en-us/powerpoint/welcome-to-copilot-in-powerpoint).
- **Presenton** — [presenton/presenton](https://github.com/presenton/presenton) :
  Apache-2.0, auto-hébergé via Docker, avec Ollama / LM Studio parmi ses
  backends pris en charge — d'où ses étoiles Offline et Local-LLM.
- **PPTAgent** — [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.728/)
  et [icip-cas/PPTAgent](https://github.com/icip-cas/PPTAgent).
- **Word / Google Docs** — [Microsoft Word](https://www.microsoft.com/microsoft-365/word)
  et [Google Docs](https://workspace.google.com/products/docs/).

La colonne **Editable** n'est pas de notre invention : ses niveaux sont ceux du
Presentation Editability Index (L0–L5) de
[SlidesGen-Bench](https://arxiv.org/abs/2601.09487), cité dans la légende des
colonnes ci-dessus.

Ce qui manque volontairement : aucun chiffre de durée, aucun score de
benchmark, aucun numéro de version épinglé sur le logiciel d'autrui. Une étoile
est ici un jugement daté sur l'adéquation à un créneau, ce qui est honnête là
où une mesure sans date ne le serait pas. Quand une note a vieilli — et dans ce
domaine certaines vieilliront — la section [Méthodologie](#méthodologie) dit à
quoi ressemble une correction utile.

## Idées à reprendre

Étudié plutôt que deviné : ce que chaque voisin fait mieux, puis ce que cette bibliothèque devrait changer pour l'égaler. Rien ici n'est un engagement : c'est la liste de lecture dont part la version suivante.

- **`Quarto` — `reference-doc` pour les présentations, pas seulement pour les documents** — Cette bibliothèque honore déjà un modèle de référence pour le `.docx`. Quarto applique la même idée au `.pptx`, qui est la moitié encore manquante : une présentation qui hérite d'un masque maison plutôt que des défauts de l'outil.

- **`Marp` — nommer dans la doc l'arbitrage entre éditabilité puis fidélité** — `--pptx-editable` produit du vrai texte avec de vraies formes au prix d'un peu de fidélité ; le défaut produit une présentation fidèle qu'on ne peut guère modifier. Marp documente l'arbitrage au lieu de choisir à votre place, or un lecteur qui compare des convertisseurs a besoin exactement de cette phrase.

- **L'export PPTX de `Slidev` — un point de vigilance, non une idée** — Il exporte chaque diapositive en image : aucun texte n'est sélectionnable. À consigner dans le tableau parce que « exporte en pptx » se lit comme équivalent d'un outil à l'autre sans l'être.

- **`Quarto` — des cellules exécutables, des figures produites au rendu** — Une figure produite par le document lui-même ne peut pas dériver des nombres qui la fondent. Pour une suite qui génère déjà ses figures de paysage depuis des CSV, c'est le même principe un étage plus haut.
