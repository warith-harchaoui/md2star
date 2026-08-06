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
| Conversion Markdown | Office+PDF | Citations | Diagrammes | Maths | Charte | CLI une-cmd | Hors ligne | LLM local | Retour-MD |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **md2star** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Pandoc | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Pandoc + templates | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| Typst | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Marp | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Slidev | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| reveal.js | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| MkDocs | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| Docusaurus | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ |
| LibreOffice | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Overleaf | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ |
| Obsidian export | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Word / Google Docs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/paysage.png)

La carte est un résumé en 2D des 9 critères : à lire comme une forme, pas comme un classement. « md2star » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Riche en informations ↔ Facile à utiliser** et **Vertical — Précis et structuré ↔ Compréhensif et complet**.
<!-- FIGURE:END -->

## Légende des colonnes

Les neuf critères, en bref :

- **Office+PDF** — qualité et fiabilité des sorties `.docx`, `.pptx`
  et PDF (PDF sans exiger une chaîne LaTeX).
- **Citations** — citations / bibliographie (BibTeX, CSL, Zotero).
- **Diagrammes** — Mermaid / Graphviz / PlantUML rendus dans le
  document.
- **Maths** — typographie LaTeX `$…$` / `$$…$$`, en ligne et en bloc,
  rendue correctement dans la sortie choisie.
- **Charte** — gabarits à la charte maison (polices, couleurs,
  couverture, en-têtes/pieds) pour un rendu voulu, pas un export brut.
- **CLI une-cmd** — une seule commande transforme le Markdown en
  livrable, sans chaîne d'outils à câbler à la main.
- **Hors ligne** — fonctionne entièrement hors ligne par défaut, sans
  appels réseau silencieux.
- **LLM local** — fonctions optionnelles de LLM local (lint, résumés,
  propositions de fusion) via Ollama ou équivalent.
- **Retour-MD** — reconvertit un DOCX / PPTX / PDF fini en un jumeau
  Markdown éditable.

Les cases qui seraient « non applicables » dans la grille maintenue à
la main (par ex. une note Office+PDF pour un outil uniquement de
slides ou de site web) valent ⭐ ici, afin que le tableau reste en
étoiles pures — à lire comme « pas fait pour cette dimension ».

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

- Votre référence est en Markdown — vous voulez des diffs en texte
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

1. **Maths** — 3 étoiles, sa ligne la plus faible. Les maths LaTeX
   poussées reviennent à Typst, Overleaf ou Pandoc brut ; md2star rend
   bien les maths en ligne et en bloc courantes, mais n'est pas un
   substitut LaTeX complet.
2. **Office+PDF** — 4 étoiles. La sortie est soignée et fiable, mais
   les éditeurs natifs (Word / Google Docs, LibreOffice) et Overleaf
   la dépassent sur la fidélité de rendu brute dans leur propre format.
3. **Citations & Diagrammes** — 4 étoiles chacun. Suffisant pour
   rapports et articles ; Pandoc et Quarto vont plus loin sur les
   styles CSL exotiques et la longue traîne des moteurs de diagrammes.

## Quand choisir quoi

- **`md2star`** — documents issus de Markdown qui doivent partir en
  DOCX / PPTX / PDF soigné et à la charte, hors ligne, en une commande,
  avec des diffs git propres et un retour vers le Markdown.
- **Pandoc** — le convertisseur universel brut quand on accepte de
  câbler soi-même templates et chaîne PDF (md2star repose dessus).
- **Pandoc + templates** — le même moteur une fois qu'on a construit
  et qu'on maintient son propre jeu de gabarits pour la charte.
- **Quarto** — pipelines notebook R/Python → publication avec code
  exécutable et citations.
- **Typst** — une alternative LaTeX rapide et moderne pour des PDF
  riches en maths et typographiés avec précision.
- **Marp / Slidev / reveal.js** — decks de slides en Markdown ou HTML
  avec rechargement à chaud (slides uniquement, pas de chaîne
  Office / PDF à la charte).
- **MkDocs / Docusaurus** — sites de documentation depuis Markdown,
  pas des livrables Office ou PDF.
- **LibreOffice** — édition Office native et DOCX / PPTX solides quand
  votre source n'est pas du Markdown.
- **Overleaf** — LaTeX collaboratif avec PDF nativement LaTeX et
  citations.
- **Obsidian export** — notes Markdown avec export piloté par plugins
  et un peu d'outillage LLM local hors ligne.
- **Word / Google Docs** — quand l'édition Office native ou la
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
