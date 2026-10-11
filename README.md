# OfficeLab AI

OfficeLab AI est une plateforme SaaS d'apprentissage pratique des compétences
numériques et bureautiques. Le projet est actuellement dans son Lot 0 :
cadrage technique et prototype du moteur de simulation.

## Prérequis

- Python 3.12 ou supérieur
- Git

## Installation locale

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Générez ensuite une clé locale et placez-la dans `DJANGO_SECRET_KEY` du fichier
`.env` :

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Le fichier `.env` contient des secrets locaux et ne doit jamais être ajouté à
Git.

## Démarrage

```bash
python manage.py migrate
python manage.py seed_prototype
python manage.py createsuperuser
python manage.py runserver
```

Dans un second terminal, démarrez l'interface :

```bash
cd frontend
npm install
npm run dev
```

L'API est disponible sur <http://127.0.0.1:8000/> et l'interface du prototype
sur <http://127.0.0.1:5173/>. Le compte créé avec `createsuperuser` permet de se
connecter au prototype.

## Vérifications

```bash
python manage.py check
python manage.py test
```

## État du projet

Le Lot 0 est en cours : le dépôt contient un moteur de gestion de fichiers,
une API authentifiée, des checkpoints, un évaluateur et une interface Vue.
L'explorateur interactif propose trois missions : créer une arborescence,
renommer et ranger des fichiers. « Vérifier mon travail » permet de corriger
sans fermer la tentative ; « Terminer la mission » enregistre le résultat final.
La barre latérale, les vues vignettes/liste, le clic droit, le glisser-déposer
et le couper/coller sont implémentés. Leur recette visuelle reste à effectuer.
L'interface retrouve les tentatives en cours après connexion ou rechargement
et permet de les reprendre avec leurs fichiers et leurs indices déjà consultés.
Les indices progressifs sont sauvegardés sans pénalité de score. Le second
simulateur et la recette débutants restent à réaliser avant la validation du prototype.

Le scénario `FILES-001` est livré en version 2. Son barème distingue le nom du
fichier de son emplacement. `python manage.py seed_prototype` installe cette
version et les missions `FILES-101`, `FILES-102`, `FILES-103`, sans modifier la
version 1 ni les tentatives qui y sont liées.
L'API choisit la dernière version publiée pour les nouvelles tentatives.

Les scénarios sont validés à l'enregistrement. Une version publiée reste
immuable après archivage et ne peut pas redevenir un brouillon. Pour modifier
ses règles, créez une nouvelle version. Les écritures ORM `update`,
`bulk_update` et `bulk_create` des versions sont volontairement interdites :
utilisez `save()` ou `objects.create()` pour passer par la validation.

Voir [le suivi du prototype](docs/prototype-simulation.md) pour le périmètre
prévu et les éléments restant à valider.

La suite suit l'ordre [explorateur → navigateur → messagerie](docs/parcours-fichiers-navigateur-messagerie.md).
Le navigateur et la messagerie ne sont pas encore implémentés.
