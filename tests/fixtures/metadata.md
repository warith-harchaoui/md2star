---
lang: fr-FR
date_format: "%A %e %B %Y"
---

# Métadonnées explicites

Cette fixture vérifie que la YAML front-matter pilote bien le rendu :
`lang: fr-FR` doit déclencher la localisation française des dates,
et `date_format` doit produire un libellé du type "lundi 21 juin
2026" (capitalisé par le filtre Lua).

## Contenu

Un paragraphe court pour donner du grain au moteur de détection de
langue, au cas où celui-ci s'exécuterait quand même (le front-matter
prend la priorité, mais la pipeline doit rester correcte si la
détection s'exécute en parallèle).
