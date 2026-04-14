# md2star ✍️⭐️

> **md2star** est un pont efficace entre Markdown et docx / pptx.

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Lua](https://img.shields.io/badge/lua-5.3-blue.svg)
![Bash](https://img.shields.io/badge/bash-4+-lightgray.svg)
![PowerShell](https://img.shields.io/badge/powershell-7+-blue.svg)

`md2star` est un ensemble d'outils multiplateformes simplifié, conçu pour les auteurs qui exigent la rapidité de **Markdown** et les formats d'entreprise de **Microsoft Office** (`.docx` et `.pptx`). En combinant la puissance de **Pandoc** avec une logique de style soignée, il automatise les parties fastidieuses de la préparation des documents.

---

## ✨ Fonctionnalités

- **🚀 Conversion sans friction pour vos idées** : Écrivez vos idées dans des fichiers Markdown avec votre éditeur de texte léger préféré (`emacs`, `vim`, `Sublime Text`, `Atom`, `Obsidian`, etc.), et laissez notre outil générer instantanément des documents `.docx` et `.pptx` en suivant les styles d'entreprise et favoris de votre choix.
- **📐 Support des Mathématiques LaTeX** : Rendu robuste de formules complexes dans les documents et les diapositives.
- **🏷️ Métadonnées Intelligentes** : 
  - **Extraction automatique du titre** depuis votre premier `# Titre`.
  - **Injection intelligente des sous-titres** pour les métadonnées telles que l'Auteur, la Date et la Catégorie.
  - **Détection Automatique de la Langue** utilisant `langdetect` avec plus de 50 langues prises en charge.
- **📚 Prêt pour la Science** : Intégration **BibTeX** native pour des citations de recherche professionnelles (pour un environnement d'entreprise, pas pour des publications académiques), ce qui est, à ma connaissance, la seule façon de gérer de grandes quantités de références de manière fiable.

---

## 🛠️ Installation

Pour garantir un maximum de fiabilité et d'isolation, `md2star` utilise [Conda](https://docs.conda.io/en/latest/miniconda.html) pour son environnement Python et s'appuie sur `pandoc` comme moteur principal.

### 1. Installer les Dépendances de Bas Niveau (Pandoc)

Vous devez installer Pandoc nativement sur votre machine en utilisant le gestionnaire de paquets de votre système d'exploitation :

- **🍏 macOS** :
  Veuillez installer *Homebrew* s'il n'est pas déjà installé :

  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```

  et ensuite

  ```bash
  brew install pandoc
  ```
- **🐧 Linux (Debian/Ubuntu)** :
  ```bash
  sudo apt-get update && sudo apt-get install pandoc
  ```
- **🪟 Windows** :
  ```powershell
  winget install --id JohnMacFarlane.Pandoc
  ```

### 2. Installer Conda

Si vous n'avez pas installé Conda, veuillez télécharger et installer **Miniconda** (un installeur minimal pour conda).
🔗 **[Téléchargez Miniconda Ici](https://www.anaconda.com/docs/getting-started/miniconda/install/overview)**

### 3. Cloner & Configurer l'Environnement

Ouvrez votre terminal ou Anaconda Prompt et exécutez les commandes suivantes pour cloner le dépôt, construire l'environnement Python 3.10 isolé, et installer les wrappers de l'application :

**🍏 macOS & 🐧 Linux**
```bash
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star
conda env create -f environment.yaml
conda activate md2star
make install
```

**🪟 Windows**
```powershell
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star
conda env create -f environment.yaml
conda activate md2star
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

> [!NOTE]
> Assurez-vous d'exécuter `conda activate md2star` avant d'utiliser les outils d'exportation !

### 4. Mise à jour

Pour importer de manière transparente les dernières modifications du dépôt et réinstaller vos composants :

**🍏 macOS & 🐧 Linux**
```bash
make update
```

**🪟 Windows**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\update.ps1
```

---

## 📖 Guide d'Utilisation

### 1. Export Simple
```bash
md2docx monfichier.md
```
*Génère `monfichier.docx`*.

### 2. Article Scientifique (avec Citations et Formules Mathématiques)
```bash
md2docx travail.md --author "Dr. R. Chercheur" --bib references.bib --bibliography-name "Références"
```
*Génère `travail.docx`*.


### 3. Diapositives de Présentation
```bash
md2pptx diapositives.md --author "Nom de l'Orateur"
```
*Génère `diapositives.pptx`*.

---

## 💡 Exemples

De bons exemples peuvent être trouvés [ici](EXAMPLES.md).

Vous pouvez également trouver des exemples plus complexes dans le répertoire [`examples/`](examples). Pour compiler par lots nativement tous les documents du dossier, exécutez le script d'exécution :
```bash
cd examples
./run.sh
```

Ci-dessous, des fichiers `.docx` et `.pptx` de base générés dynamiquement pendant notre suite de tests à partir de fichiers Markdown d'exemple :

**Exemples de Documents Word**
- Titre de Base [assets/docx/basic.docx](assets/docx/basic.docx) *(depuis [basic.md](assets/docx/basic.md))* 
  ```bash
  md2docx assets/docx/basic.md
  ```
- Auteur Injecté [assets/docx/with_author.docx](assets/docx/with_author.docx) *(depuis [with_author.md](assets/docx/with_author.md))*
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
- Formules Mathématiques [assets/docx/math.docx](assets/docx/math.docx) *(depuis [math.md](assets/docx/math.md))*
  ```bash
  md2docx assets/docx/math.md
  ```

**Exemples de Diapositives PowerPoint**
- Exemple Extensif [assets/pptx/example.pptx](assets/pptx/example.pptx) *(depuis [example.md](assets/pptx/example.md))*
  ```bash
  md2pptx assets/pptx/example.md
  ```

---

## 🧪 Qualité & Fiabilité

![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

`md2star` est construit pour être fiable. Notre suite de tests automatisée couvre :
- [x] **Précision des Métadonnées** : Vérification du Titre, de l'Auteur et du Sous-titre.
- [x] **Intégrité Multi-Format** : Parité entre les sorties DOCX et PPTX.
- [x] **Rendu de la Bibliographie** : Utilisation du snapshot [references.bib](assets/references.bib).
- [x] **Localisation** : Rendu des dates en français et en-têtes internationaux.

### Tests d'intégration (shell)

Nécessite l'installation de **Pandoc** :
```bash
make test
```

### Tests unitaires (Python)

Nécessite **pytest** et l'environnement conda:
```bash
python -m pytest tests/ -v
```

Pour plus de détails, voir [tests/README.md](tests/README.md).

---

## ⚙️ Personnalisation

### Paramètres de Métadonnées par Défaut
Ajustez vos paramètres par défaut globaux dans `pandoc/metadata.yaml` :
```yaml
author: "Votre Nom par Défaut"
date_format: "%A, %e %B %Y"
lang: "en-US"
```

Conventions choisies :

  + `date_format` utilise une chaîne de format de style `strftime()`.
Voir la [documentation de formatage date-heure C/POSIX](https://pubs.opengroup.org/onlinepubs/9699919799/functions/strftime.html) pour plus d'informations.

  + `lang` utilise une étiquette de langue BCP 47 (par ex., `en-US`, `fr-FR`).
Voir la [documentation RFC 5646](https://datatracker.ietf.org/doc/html/rfc5646) pour plus d'informations.

### Modèles de Style
Modifiez les modèles de base dans `assets/` pour changer globalement les polices, les marges ou les logos :
- [template.docx](assets/template.docx)
- [template.pptx](assets/template.pptx)

Lors de l'installation, ceux-ci sont copiés dans `~/.pandoc/` (ou `%APPDATA%\pandoc` sous Windows). Voir [assets/README.md](assets/README.md) pour les détails.

---

## 📚 Documentation Développeur

Pour les contributeurs et les utilisateurs avancés intéressés par le fonctionnement interne de notre logique Python et les crochets d'analyse AST, consultez nos guides d'API internes :
- [Guide Développeur](docs/developer_guide.md)

---

## 📦 Projets Connexes

- **[Pandoc](https://pandoc.org/)** : Le moteur qui rend la conversion de documents universelle.
- **[Obsidian](https://obsidian.md/)** : Notre environnement recommandé pour écrire en Markdown de haute fidélité.
- **[Zotero](https://www.zotero.org/)** : Le compagnon de recherche idéal pour gérer vos bibliographies `.bib`.

---

## 🔧 Dépannage

| Problème | Solution |
|------|----------|
| `md2docx: command not found` | Ajoutez `~/.local/bin` à votre variables PATH (voir sortie d'installation) |
| `pandoc: command not found` | Installez [Pandoc](https://pandoc.org/installing.html) via votre gestionnaire de paquets |
| Les dates françaises sont en anglais | Assurez-vous que la localisation `fr_FR.UTF-8` est installée (`locale -a`) |
| Avertissements de disposition modèle PPTX | Normal si le modèle manque des dispositions de diapositives standard ; sortie toujours valide |

---

## 🤝 Contribuer

1. Forkez & clonez le dépôt.
2. Activez conda et exécutez `make install` pour configurer localement.
3. Apportez vos modifications.
4. Exécutez `make test` et `python -m pytest tests/ -v` pour vérifier.
5. Ouvrez une pull request.

---

## 📄 Licence

Distribué sous **The Unlicense** (Domaine Public). Conçu avec précision pour l'auteur moderne.
