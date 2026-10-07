# Prototype du moteur de simulation

## 1. Statut du document

| Élément | Valeur |
|---|---|
| Produit | OfficeLab AI |
| Lot | Lot 0 — cadrage et prototype |
| Version | 0.1 |
| Statut | Proposition à valider avant implémentation |
| Public pilote | Apprenant débutant en français |
| Support prioritaire | Ordinateur, navigateur moderne |

## 2. Objectif du prototype

Le prototype doit vérifier qu'un même moteur peut charger, exécuter, sauvegarder
et évaluer plusieurs simulations pédagogiques sans coder une application
indépendante pour chaque exercice.

Deux scénarios serviront de preuve :

1. organiser des fichiers et des dossiers ;
2. naviguer dans un navigateur et sur des pages web simulés.

Le prototype n'est pas une reproduction exacte de Windows, Chrome, Edge,
Firefox ou d'un site tiers. Il utilise une identité visuelle propre à OfficeLab
et observe uniquement les actions nécessaires à l'apprentissage.

## 3. Principes communs

- Une consigne principale est affichée à la fois.
- L'apprenant peut essayer, annuler et recommencer sans sanction.
- Les chemins équivalents sont acceptés lorsque l'état attendu est atteint.
- Les actions sont traduites en événements logiques indépendants de l'interface.
- Une tentative peut être sauvegardée et reprise.
- Les indices sont déterministes et ne nécessitent pas d'intelligence
  artificielle.
- Le feedback décrit l'écart observé et propose une correction.
- Le fonctionnement sans souris est prévu pour toutes les actions essentielles.
- Les scénarios, règles, barèmes et indices sont versionnés.

## 4. Cycle d'une tentative

Une tentative suit les états suivants :

```text
créée → en cours → sauvegardée → soumise → réussie ou échouée
                    ↘ abandonnée
```

Le moteur doit :

1. charger le scénario et son état initial ;
2. créer une tentative liée à la version du scénario ;
3. recevoir les événements de l'interface ;
4. appliquer chaque événement à l'état courant ;
5. créer des checkpoints ;
6. fournir un indice à la demande ;
7. évaluer la soumission ;
8. retourner le score, les critères et le feedback.

## 5. Scénario 1 — Organiser des fichiers et dossiers

### 5.1 Objectif pédagogique

À la fin de l'exercice, l'apprenant sait ouvrir un emplacement, créer un dossier,
créer et renommer un fichier, puis déplacer ce fichier.

### 5.2 Consigne

> Dans « Documents », créez un dossier nommé « Formation ». Créez ensuite un
> fichier nommé « exercice.txt », renommez-le « rapport.txt », puis placez-le
> dans le dossier « Formation ». Validez lorsque vous avez terminé.

### 5.3 État initial

```text
Accueil/
├── Documents/
├── Images/
└── Téléchargements/
```

L'apprenant démarre sur l'écran d'accueil du gestionnaire de fichiers. Aucun
élément nommé `Formation`, `exercice.txt` ou `rapport.txt` n'existe.

### 5.4 État final attendu

```text
Accueil/
├── Documents/
│   └── Formation/
│       └── rapport.txt
├── Images/
└── Téléchargements/
```

### 5.5 Actions autorisées

- ouvrir un dossier ;
- revenir au dossier parent ;
- sélectionner un élément ;
- créer un dossier ;
- créer un fichier texte ;
- renommer un élément ;
- déplacer un élément par couper/coller ;
- déplacer un élément par glisser-déposer ;
- annuler la dernière action compatible ;
- demander un indice ;
- recommencer ;
- sauvegarder et valider.

Le menu contextuel, les boutons visibles et les raccourcis documentés doivent
produire les mêmes événements logiques.

### 5.6 Événements logiques principaux

| Événement | Données minimales |
|---|---|
| `folder.opened` | identifiant du dossier |
| `folder.created` | parent, nom |
| `file.created` | parent, nom, type |
| `item.renamed` | identifiant, ancien nom, nouveau nom |
| `item.moved` | identifiant, ancien parent, nouveau parent |
| `action.undone` | identifiant de l'action annulée |
| `hint.requested` | niveau d'indice |
| `attempt.submitted` | version de l'état |

Les noms affichés ne doivent pas être utilisés comme identifiants techniques.

### 5.7 Règles de validation et barème

| Critère | Points |
|---|---:|
| Le dossier `Formation` existe dans `Documents` | 25 |
| Un fichier texte nommé `rapport.txt` existe | 25 |
| `rapport.txt` se trouve dans `Documents/Formation` | 35 |
| Aucun élément parasite demandé par erreur ne reste dans `Documents` | 10 |
| Validation explicite de la tentative | 5 |
| Total | 100 |

La réussite est obtenue à partir de 80 points, avec obligation de satisfaire le
critère de localisation du fichier. Le fichier peut être créé directement sous
le nom `rapport.txt` : l'état final reste correct, mais le moteur conserve
l'information que la compétence « renommer » n'a pas été observée. Cette
distinction servira au diagnostic de compétence sans invalider arbitrairement
le résultat final.

### 5.8 Indices progressifs

1. « Commencez par ouvrir le dossier Documents. »
2. « Utilisez l'action Nouveau dossier et nommez-le Formation. »
3. « Vérifiez le nom et l'emplacement du fichier demandé. »
4. Mise en évidence temporaire de l'action ou de l'emplacement concerné.

Chaque indice est enregistré. Le prototype affiche le nombre d'indices utilisés
mais ne retire pas de points. Une politique de pénalité pourra être évaluée
après les tests utilisateurs.

### 5.9 Erreurs et feedback

| Situation | Feedback attendu |
|---|---|
| Nom de dossier incorrect | Indiquer le nom attendu sans supprimer le dossier |
| Extension absente ou incorrecte | Expliquer la différence entre nom et extension |
| Fichier au mauvais emplacement | Montrer l'emplacement actuel et celui attendu |
| Élément déjà existant | Proposer de choisir un autre nom ou d'utiliser l'existant |
| Déplacement impossible | Expliquer la cause et conserver l'état précédent |
| Soumission incomplète | Lister les critères réussis et ceux restant à accomplir |

## 6. Scénario 2 — Naviguer sur des pages web simulées

### 6.1 Objectif pédagogique

À la fin de l'exercice, l'apprenant sait utiliser une barre d'adresse, suivre un
lien, revenir en arrière, ouvrir et sélectionner un onglet, puis repérer une
information sur une page.

### 6.2 Environnement contrôlé

Le navigateur, les adresses et les pages sont internes au simulateur. Aucune
requête vers Internet n'est nécessaire. Le site fictif s'appelle
« Portail Formation OfficeLab ».

Pages disponibles :

```text
formation.officelab.test/
├── accueil
├── catalogue
│   ├── fondamentaux
│   └── bureautique
└── contact
```

### 6.3 Consigne

> Saisissez `formation.officelab.test` dans la barre d'adresse. Ouvrez le
> catalogue, consultez la formation « Fondamentaux numériques », revenez à la
> page précédente, puis ouvrez « Bureautique » dans un nouvel onglet. Dans ce
> nouvel onglet, trouvez la durée de la formation et sélectionnez la bonne
> réponse.

La durée affichée dans le jeu de données du scénario est « 20 heures ».

### 6.4 État initial

- un seul onglet ouvert ;
- page de démarrage neutre ;
- barre d'adresse vide ;
- historique vide ;
- aucune réponse sélectionnée.

### 6.5 Actions autorisées

- sélectionner la barre d'adresse ;
- saisir et charger une adresse ;
- activer un lien ;
- revenir à la page précédente ;
- avancer dans l'historique ;
- actualiser la page simulée ;
- ouvrir un lien dans un nouvel onglet ;
- sélectionner ou fermer un onglet ;
- faire défiler la page ;
- sélectionner une réponse ;
- demander un indice, recommencer et valider.

### 6.6 Événements logiques principaux

| Événement | Données minimales |
|---|---|
| `address.submitted` | adresse normalisée |
| `page.loaded` | identifiant de page |
| `link.activated` | page source, cible, mode d'ouverture |
| `history.back` | page source, page cible |
| `tab.opened` | identifiant de l'onglet, page |
| `tab.selected` | identifiant de l'onglet |
| `answer.selected` | question, valeur |
| `hint.requested` | niveau d'indice |
| `attempt.submitted` | version de l'état |

### 6.7 Règles de validation et barème

| Critère | Points |
|---|---:|
| L'adresse attendue a été chargée | 15 |
| La page Catalogue a été consultée | 15 |
| La page Fondamentaux numériques a été consultée | 15 |
| Un retour dans l'historique a été réalisé | 15 |
| La page Bureautique est ouverte dans un second onglet | 20 |
| Le second onglet est actif lors de la recherche | 5 |
| La réponse « 20 heures » est sélectionnée | 15 |
| Total | 100 |

La réussite est obtenue à partir de 80 points avec une réponse finale correcte
et l'ouverture d'un second onglet.

### 6.8 Indices progressifs

1. « La barre située en haut permet de saisir une adresse. »
2. « Le catalogue est accessible depuis la page d'accueil. »
3. « Le bouton Retour permet de revoir la page précédente. »
4. « Utilisez le menu du lien Bureautique pour l'ouvrir dans un nouvel onglet. »
5. Mise en évidence temporaire de l'élément concerné.

### 6.9 Erreurs et feedback

| Situation | Feedback attendu |
|---|---|
| Adresse inconnue | Afficher une page d'erreur pédagogique sans accès Internet |
| Lien ouvert dans le même onglet | Expliquer comment ouvrir un nouvel onglet |
| Mauvais onglet actif | Indiquer le titre de l'onglet à sélectionner |
| Mauvaise durée | Inviter à relire la section « Informations pratiques » |
| Soumission incomplète | Présenter les étapes acquises et celles manquantes |

## 7. Format déclaratif initial

Le format définitif sera validé par une décision d'architecture. Le prototype
partira d'une structure de ce type :

```json
{
  "schema_version": "1.0",
  "scenario": {
    "code": "FILES-001",
    "version": 1,
    "title": "Organiser des fichiers et dossiers",
    "runtime": "file_manager",
    "locale": "fr",
    "instructions": [],
    "initial_state": {},
    "allowed_actions": [],
    "criteria": [],
    "hints": [],
    "completion": {
      "minimum_score": 80,
      "required_criteria": []
    }
  }
}
```

Le backend valide le schéma avant publication. Une tentative conserve la
version exacte du scénario et du moteur utilisée.

## 8. Persistance minimale

Le prototype doit distinguer :

- `Scenario` : identité stable du scénario ;
- `ScenarioVersion` : définition publiée et immuable ;
- `Attempt` : tentative d'un apprenant ;
- `SimulationEvent` : événement pédagogique nécessaire ;
- `Checkpoint` : état sérialisé permettant la reprise ;
- `EvaluationResult` : score et résultat par critère.

Une clé d'idempotence empêche qu'un événement renvoyé après une coupure soit
appliqué deux fois.

## 9. Accessibilité et expérience débutant

- Toutes les commandes critiques sont accessibles au clavier.
- Le focus est toujours visible et suit un ordre logique.
- Les menus utilisent des rôles et libellés accessibles.
- La couleur n'est jamais le seul moyen de transmettre une information.
- Les messages d'erreur sont annoncés et associés à l'action concernée.
- Le zoom à 200 % ne bloque pas l'accomplissement de l'exercice.
- Les zones interactives ont une taille suffisante.
- Les animations respectent la préférence de réduction des mouvements.
- Le vocabulaire technique dispose d'une explication simple.
- Les simulations complexes annoncent clairement leur largeur minimale.

## 10. Données et confidentialité

Le journal ne doit pas enregistrer chaque mouvement de souris ni chaque frappe.
Il conserve seulement les actions logiques utiles à l'évaluation, au diagnostic
et à la reprise. Aucun contenu sensible ni adresse Internet réelle n'est requis.

Pour le Lot 0, les données peuvent être supprimées à la fin du pilote selon une
durée validée avec le responsable du projet.

## 11. Critères Go/No-Go

Le prototype obtient un avis **Go** si les conditions suivantes sont réunies :

| Domaine | Critère |
|---|---|
| Réutilisation | Les deux scénarios utilisent le même cycle de tentative et le même évaluateur |
| Déclaratif | Modifier consigne, état initial, critères et indices ne nécessite pas de modifier le moteur |
| Exactitude | Les états finaux conformes sont acceptés et les états non conformes sont expliqués |
| Chemins multiples | Au moins deux méthodes de déplacement sont acceptées pour le scénario Fichiers |
| Reprise | Une tentative interrompue reprend au dernier checkpoint valide |
| Idempotence | Le renvoi d'un événement ne produit pas de double effet |
| Accessibilité | Les deux scénarios essentiels sont réalisables sans souris |
| Performance | Une action courante produit un retour visuel immédiat sur l'appareil pilote |
| Réseau faible | Une coupure n'entraîne pas la perte des actions déjà confirmées |
| Utilisabilité | Au moins 4 débutants sur 5 terminent le scénario guidé sans intervention directe |
| Traçabilité | Chaque résultat indique la version du scénario, du moteur et des règles |
| Confidentialité | Aucun événement inutile ou contenu de saisie sensible n'est journalisé |

Un avis **No-Go** ou **Go avec réserves** est prononcé si le moteur exige du code
spécifique important pour chaque scénario, produit des évaluations incohérentes,
ne permet pas la reprise ou reste inutilisable pour le public débutant.

## 12. Hors périmètre du prototype

- reproduction visuelle exacte de produits tiers ;
- navigation sur Internet réel ;
- téléchargement ou exécution de fichiers réels ;
- synchronisation complète hors ligne ;
- intelligence artificielle ;
- outil auteur visuel complet ;
- examen certifiant ;
- analyse de fraude ;
- application mobile native ;
- scénarios Word, Excel et PowerPoint.

## 13. Décisions à valider avant le code

1. Valider les deux consignes et les états finaux.
2. Confirmer que l'utilisation des indices n'enlève pas de points au Lot 0.
3. Valider le seuil de réussite de 80 points.
4. Valider le fonctionnement sur ordinateur en priorité.
5. Confirmer l'utilisation d'une interface entièrement originale.
6. Valider Vue.js 3 avec TypeScript pour le simulateur.
7. Valider Django REST Framework pour l'API.

Après validation, l'implémentation commencera par le schéma de scénario, le
modèle d'état et l'évaluateur en mémoire, avant la base de données et l'interface
graphique.

## 14. Suivi de l'implémentation — 6 octobre 2026

Les sections précédentes décrivent le périmètre de référence. Le Lot 0 n'est
pas encore clôturé : un premier scénario de fichiers fonctionne de bout en
bout, tandis que le scénario navigateur et la recette débutants restent à faire.

### Première étape : fiabilisation du moteur

- Les événements sont validés avant mutation : type d'action, champs requis,
  identifiants texte, noms et absence de champs inconnus. Les entrées invalides
  reçues par l'API renvoient une erreur 400 sans événement ni checkpoint ajouté.
- Le renvoi d'un identifiant d'événement avec un contenu différent est refusé.
  Le renvoi du même événement conserve son comportement idempotent.
- Le schéma de scénario vérifie les types, les actions prises en charge, les
  opérateurs et leurs paramètres, le barème et les conditions de réussite.
  L'état initial doit former une arborescence valide : racine, parents dossiers,
  identifiants uniques, noms sans doublon dans un dossier et absence de cycles.
- `FILES-001` v2 utilise le critère `item_named` pour les 25 points du nom :
  un fichier `rapport.txt` peut obtenir ces points quel que soit son emplacement.
  Les 35 points d'emplacement et la condition obligatoire restent distincts.
  Un dossier portant ce nom ne satisfait pas le critère du fichier.
- La v1 est conservée sans modification. La commande `seed_prototype` installe
  la v2 ; seules les nouvelles tentatives utilisent automatiquement cette version.
- Les écritures de versions via `save()` et `objects.create()` valident la
  définition et sa cohérence avec les métadonnées. Une version publiée ne peut
  plus changer de définition, de numéro, de scénario, de schéma ou de date de
  publication, y compris après archivage ; le retour au brouillon est interdit.
  Les écritures ORM en masse sont bloquées pour éviter de contourner ces règles.
  Cette protection applicative ne couvre pas des modifications SQL directes.

Les tests de régression couvrent les erreurs d'entrée et leur absence d'effet,
les barèmes v1/v2, la conservation des anciennes tentatives, l'immutabilité et
les écritures partielles. Exécution : `python manage.py test`.

### Deuxième étape : reprise et indices progressifs

- Après connexion ou rechargement, l'accueil propose les tentatives en cours
  de l'utilisateur. « Reprendre » restaure les fichiers du dernier checkpoint,
  les consignes de la version d'origine et les indices déjà consultés.
  L'explorateur rouvre Accueil ; le dossier affiché et les saisies non envoyées
  ne sont pas sauvegardés.
- « Revenir aux exercices » permet de quitter une tentative sans la soumettre.
  Chaque action confirmée par le serveur est déjà sauvegardée. Une nouvelle
  tentative peut être créée séparément, sans supprimer les anciennes.
- « Afficher un indice » révèle le prochain indice de la version de la tentative.
  Le nombre consulté est affiché, sans retrait de points. Les indices restent
  visibles après reprise et après soumission ; aucune nouvelle demande n'est
  acceptée lorsque la tentative est terminée ou que les indices sont épuisés.
- Chaque indice produit un événement `hint.requested` et un checkpoint dans la
  transaction de la tentative. Une demande rejouée avec le même identifiant
  n'ajoute pas d'indice. L'interface conserve cet identifiant lors d'une erreur
  pour permettre une nouvelle demande sans double comptage.
- API : `GET /api/v1/scenarios/<code>/attempts/` liste les tentatives en cours
  du compte ; `GET /api/v1/attempts/<id>/` restaure le détail ;
  `POST /api/v1/attempts/<id>/hint/` reçoit `client_event_id`.
  Le contrôle du propriétaire s'applique au détail et aux indices.
- Les tests API couvrent l'isolation des comptes, la reprise avec une ancienne
  version archivée, l'idempotence, les limites d'indices, les collisions
  d'identifiants et un résultat de 100 points après utilisation d'un indice.

Vérification dans Chrome 153 effectuée le 6 octobre 2026, par automatisation
du navigateur avec un profil temporaire et un compte apprenant dédié :

- Connexion réelle via le proxy Vite, avec session et protection CSRF.
- Création de Formation, consultation d'un indice, rechargement et reprise :
  le dossier et l'indice sont conservés.
- Création d'exercice.txt, renommage en rapport.txt et déplacement dans Formation.
- Consultation d'un deuxième indice puis soumission : réussite à 100/100.
- Après soumission, demande d'indice désactivée et tentative retirée de la
  liste des exercices en cours.
- Déconnexion conservée après rechargement ; aucune exception JavaScript détectée.

Cette vérification complète les 48 tests Django et le build Vue déjà passants.
Elle ne remplace pas la recette manuelle au clavier, multi-navigateurs et avec
des débutants, qui reste à réaliser. L'isolation entre comptes est couverte
par les tests API.

### Étapes suivantes

1. Second scénario pour éprouver la réutilisation du moteur.
2. Recette clavier, tests avec des débutants et décision Go/No-Go du Lot 0.

L'annulation, les deux méthodes de déplacement et les autres critères de la
section 11 restent à vérifier ou à implémenter avant d'annoncer le Lot 0 terminé.
