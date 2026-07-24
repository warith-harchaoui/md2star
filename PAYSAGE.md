# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/md2star/blob/main/LANDSCAPE.md)

Comparaison concurrentielle honnête dans l'espace « Markdown →
document soigné », mesurée face à `md2star`. Les notes vont de ⭐ (1)
à ⭐⭐⭐⭐⭐ (5), évaluées sur la tâche visée par `md2star` — partir
d'une source Markdown de référence et produire un DOCX / PPTX / PDF à
l'allure délibérée, hors ligne par défaut, avec des diffs propres et
compatibles git. Un outil optimisé pour un tout autre usage (co-édition
en temps réel, écriture nativement LaTeX) n'est pas pénalisé — la note
reflète seulement l'adéquation à *ce* créneau. Choisir le bon outil
compte plus que choisir le nôtre : si votre équipe co-édite en temps
réel, Google Docs bat md2star et nous le disons.

Nous nous notons honnêtement — `md2star` n'obtient pas 5 étoiles sur
chaque ligne. Ce document est maintenu à la main et reflète l'état de
chaque projet à la mi-2026 ; ouvrez une issue si quelque chose est
dépassé.

## En un coup d'œil

<!-- TABLE:START -->
| Conversion Markdown | MD-src | WYSIWYG | DOCX | PPTX | PDF | Citations | Diagrammes | Maths | LLM local | Hors ligne | OSS | Collab temps réel | Git-async | Mobile |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **md2star** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Pandoc | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Quarto | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Curvenote | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Stencila | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Marp / Slidev | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Typora | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Zettlr | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Obsidian + plugins | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| StackEdit | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| HedgeDoc / HackMD | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| CryptPad | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Notion | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| GitBook | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Google Docs | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Overleaf | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| MS Word / Office | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/paysage.png)

La carte est un résumé en 2D des 14 critères : à lire comme une forme, pas comme un classement. « md2star » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Facile à Collaborer ↔ Fiable et Évolutif** et **Vertical — Simplicité de Référence ↔ Riches en Informations**.
<!-- FIGURE:END -->

## Légende des colonnes

Les critères, en bref :

- **MD-src** — Markdown est le format source natif, pas seulement une
  voie d'import/export.
- **WYSIWYG** — véritable édition inline « tel écrit, tel affiché »,
  et non un aperçu en volet séparé.
- **DOCX / PPTX / PDF** — qualité et fiabilité des sorties `.docx`,
  `.pptx` et PDF (PDF sans exiger une chaîne LaTeX).
- **Citations** — citations / bibliographie (BibTeX, CSL, Zotero).
- **Diagrammes** — Mermaid / Graphviz / PlantUML intégrés.
- **Maths** — typographie LaTeX `$…$` / `$$…$$`, en ligne et en bloc,
  rendue correctement dans la sortie choisie.
- **LLM local** — fonctions optionnelles de LLM local (lint, résumés,
  propositions de fusion) via Ollama ou équivalent.
- **Hors ligne** — fonctionne entièrement hors ligne par défaut, sans
  appels réseau silencieux.
- **OSS** — libre et open source sous licence permissive ou copyleft.
- **Collab temps réel** — co-édition en temps réel avec présence
  (curseurs, sélections, qui tape).
- **Git-async** — collaboration asynchrone compatible git sur les
  fichiers source (diffs propres, fusions saines).
- **Mobile** — édition mobile de premier ordre, pas seulement
  « fonctionne dans un navigateur ».

Les cases qui seraient « non applicables » dans la grille maintenue à
la main (par ex. une note PPTX pour un outil uniquement de slides)
valent ⭐ ici, afin que le tableau reste en étoiles pures — à lire
comme « pas fait pour cette dimension ».

## Positionnement

`md2star` se place volontairement à l'intersection d'une **source
Markdown de référence** (diffs en texte brut, archive grepable, aucun
risque de format propriétaire) et d'une **sortie de document soignée**
(un DOCX, PPTX ou PDF à l'allure délibérée, pas un export brut). Il ne
cherche délibérément **pas** à concurrencer Google Docs sur la
co-édition en temps réel, Overleaf sur l'écriture nativement LaTeX, ou
MS Word sur la fidélité de rendu native.

Choisissez `md2star` quand **toutes** ces conditions sont réunies :

- Votre référence est en Markdown — vous voulez des diffs en texte
  brut, une archive grepable et aucun risque de format propriétaire.
- Vous produisez du DOCX, PPTX ou PDF comme livrable soigné (articles,
  rapports internes, slides client, supports de formation, brouillon
  de livre destiné à un correcteur).
- Vous tenez au hors-ligne par défaut et à l'absence de télémétrie.
- Votre équipe est petite (1–10) et asynchrone, ou vous travaillez
  seul sur plusieurs appareils.
- Un éditeur en volet séparé (source Markdown + aperçu en direct) vous
  convient, plutôt qu'un vrai WYSIWYG inline.

Là où `md2star` ne concourt délibérément pas :

1. **Collab temps réel** — 1 étoile, volontairement. Ajouter présence
   + CRDT en ferait un autre produit. Si le temps réel voit le jour,
   ce sera un produit Premium hébergé, pas une fonction de l'édition
   Communautaire.
2. **WYSIWYG** — 3 étoiles. L'aperçu en volet séparé garde la source
   Markdown propre et relisible ; l'éditeur local est livré dans le
   paquet principal (`md2star gui`), tandis qu'un mode WYSIWYG à volet
   unique reste une piste, pas un engagement.
3. **Mobile** — 2 étoiles. La GUI web locale écoute sur `127.0.0.1` et
   suppose un poste de bureau ; une coque mobile est dans la file à
   long terme, non promise.

## Quand choisir quoi

- **`md2star`** — documents issus de Markdown qui doivent partir en
  DOCX / PPTX / PDF soigné, hors ligne, avec des diffs git propres.
- **Pandoc** — quand on veut le convertisseur universel brut et qu'on
  accepte de câbler soi-même templates et chaîne PDF (md2star repose
  dessus).
- **Quarto** — pipelines notebook R/Python → publication avec code
  exécutable et citations.
- **Curvenote / Stencila** — publication scientifique en temps réel ou
  exécutable sur MyST Markdown, avec citations, maths et collab.
- **Typora / iA Writer** — véritable édition Markdown WYSIWYG à volet
  unique.
- **Obsidian** — Markdown mobile-first avec un vaste écosystème de
  plugins.
- **Zettlr** — écriture académique en Markdown intégrée à Zotero.
- **Marp / Slidev** — slides uniquement en Markdown avec rechargement
  à chaud.
- **StackEdit** — Markdown dans le navigateur depuis n'importe quel
  appareil, avec lecture/écriture directe GitHub/GitLab (pas d'export
  DOCX/PPTX).
- **HedgeDoc / CryptPad** — co-édition en temps réel (et chiffrée de
  bout en bout) auto-hébergeable.
- **Overleaf** — LaTeX collaboratif avec PDF nativement LaTeX.
- **Google Docs / Notion / MS Word** — quand la co-édition temps réel,
  un wiki d'équipe ou l'édition Office native est le vrai produit.

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
  l'auto-évaluation de md2star sans confirmation indépendante.
- Si une note vous semble erronée, ouvrez une issue avec l'outil, la
  colonne, la note actuelle et proposée, et une raison concrète (lien
  vers une fonctionnalité, un benchmark, un document représentatif).
