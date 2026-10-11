# Parcours pratique : fichiers, navigateur, messagerie

Date : 7 octobre 2026.

## Direction retenue

L'ordre demandé par le porteur du projet est : **explorateur de fichiers →
navigateur Internet → messagerie**, puis les autres parcours bureautiques.
L'expérience repose sur des manipulations dans des interfaces simulées : une
consigne, une action observable, une vérification explicable et une correction
possible. Les périmètres détaillés ci-dessous constituent une proposition de
réalisation, et non des fonctionnalités déjà toutes livrées.

Ce parcours précise la priorité de développement. Il ne signifie pas que le
socle LMS multi-organisations ou le MVP commercial du cahier des charges sont
terminés. Le navigateur est déjà prévu par le prototype du Lot 0 ; la messagerie
est l'extension suivante demandée, à planifier après sa validation.

## Ce que les références apportent

- [Playhooky — explorateur](https://www.playhooky.fr/jeux/explorateur-de-fichiers/) :
  référence pour la manipulation directe, le panneau de mission, le retour de
  vérification et la progression. La page et sa logique JavaScript publique ont
  été examinées ; aucun code ou actif graphique de ce site n'est intégré au projet.
- [OpenClassrooms — Naviguez sur Internet](https://openclassrooms.com/fr/courses/5870011-naviguez-sur-internet) :
  parcours en libre accès, sans prérequis, articulant services en ligne et recherche.
  Le [chapitre navigateur](https://openclassrooms.com/fr/courses/5870011-naviguez-sur-internet/6006711-utilisez-les-fonctionnalites-de-votre-navigateur)
  traite notamment de l'historique, des onglets et des favoris. C'est une base de
  progression pédagogique, pas la preuve d'un simulateur intégré identique au nôtre.
- [ANCT — explorateur](https://lesbases.anct.gouv.fr/ressources/decouverte-de-l-ordinateur-explorateur-de-fichiers)
  et [gestion des dossiers](https://lesbases.anct.gouv.fr/ressources/decouverte-de-l-ordinateur-gestion-des-dossiers) :
  supports sur les fichiers, extensions, tailles et dossiers, dont la corbeille.
  Ces fiches aident à définir les notions à pratiquer.
- [Genially fourni](https://view.genially.com/67cc10c7bf30ed62febf3a49) :
  la lecture n'a pas abouti avec l'outil de consultation. Son contenu interactif
  et son système de correction ne sont donc pas confirmés.

## Une expérience commune

Chaque simulateur conserve le même cadre :

1. Choisir une mission et lire un objectif court.
2. Agir dans l'application simulée avec des commandes familières.
3. Obtenir des indices progressifs si nécessaire.
4. Cliquer sur « Vérifier mon travail » pour connaître les écarts.
5. Corriger et vérifier à nouveau, sans clôturer la tentative.
6. Terminer la mission pour enregistrer le résultat final, puis poursuivre.

Trois formes d'accompagnement sont proposées : découverte avec aide explicite,
entraînement avec indices à la demande, puis mission de synthèse. La difficulté
augmente par les tâches et le guidage, pas seulement par un nombre de clics.
Le fonctionnement standard ne dépend pas de l'IA.

Le score pédagogique porte sur les critères annoncés. Si une compétence exige
un geste précis (copier, répondre, utiliser un nouvel onglet), on vérifie aussi
l'événement correspondant. On distingue donc résultat correct et geste observé.

## 1. Explorateur de fichiers

### Implémenté au 7 octobre, recette visuelle restant à faire

- Trois missions : arborescence, noms de fichiers, classement.
- Barre latérale, fil d'Ariane, vues vignettes/liste et propriétés simples.
- Création, renommage, déplacement par glisser-déposer ou couper/coller.
- Menu contextuel, raccourcis Entrée, F2, Ctrl/Cmd+X et Ctrl/Cmd+V.
- Suppression d'un fichier ou d'un dossier vide avec confirmation.
- Vérification intermédiaire, résultat final, reprise, indices et recommencement.
- Score de parcours calculé à partir des réussites sauvegardées, sans additionner
  plusieurs fois les répétitions de la même mission.

La suppression actuelle retire l'élément de l'état simulé. **Elle ne constitue
pas une corbeille**. Copier/coller, restauration depuis la corbeille, annulation
et sélection multiple ne sont pas encore implémentés.

### Compléments pour couvrir les gestes demandés

| Compétence | Mission proposée | Preuve attendue |
|---|---|---|
| Copier sans déplacer | Copier une fiche de Documents vers Formation | Original conservé, copie distincte dans la destination, action de copie observée |
| Déplacer | Ranger une photo dans Images | Même fichier dans la destination, absent du dossier source |
| Utiliser la corbeille | Supprimer un brouillon puis le restaurer | Passage dans la corbeille et restauration au bon emplacement |
| Comprendre une extension | Choisir l'image à joindre | Identification correcte du type, sans assimiler renommage et conversion |

La taille affichée dans un exercice doit provenir de métadonnées de scénario.
Aucune taille fictivement calculée à partir du nom du fichier ne doit être
présentée comme une mesure réelle.

## 2. Navigateur Internet

Une interface de navigateur OfficeLab comportera une barre d'adresse, des
onglets, Retour/Suivant, Actualiser et des pages pédagogiques internes.

| Étape | Mission proposée | Ce que la correction vérifie |
|---|---|---|
| Atteindre un site | Saisir formation.officelab.test | Adresse normalisée, page attendue chargée |
| Se repérer | Ouvrir le catalogue puis revenir à l'accueil | Liens suivis et retour dans l'historique de l'onglet |
| Gérer les onglets | Consulter deux formations en parallèle | Second onglet ouvert, sélection correcte, première page conservée |
| Retrouver une page | Ajouter une formation aux favoris puis la rouvrir | Favori enregistré et utilisé |
| Rechercher | Trouver une information dans un moteur simulé | Requête pertinente, résultat consulté, réponse attendue |
| Vérifier une information | Comparer deux sources préparées | Choix justifié par les indices fournis : auteur, date, domaine, contenu |
| Télécharger | Télécharger programme.pdf puis le retrouver | Document virtuel présent dans Téléchargements |

La première livraison doit couvrir adresse, navigation, onglets et reprise :
elle permet de réaliser le scénario déjà spécifié dans `prototype-simulation.md`.
Les favoris, la recherche et le téléchargement complètent ensuite ce module.

La barre d'adresse du simulateur ne remplace pas celle du vrai navigateur.
Les adresses et résultats initiaux sont contrôlés et internes : pas d'ouverture
arbitraire de sites réels ni de dépendance à un classement Google en direct.
Une extension ne transforme pas le contenu : renommer `.jpg` en `.pdf` ne produit
pas un PDF valide. Les scénarios doivent enseigner cette différence.

L'historique et la position Retour/Suivant appartiennent à chaque onglet.
Fermer un onglet, actualiser ou rouvrir une tentative doivent avoir un effet
précis et couvert par les tests.

## 3. Messagerie

Le troisième environnement sera un webmail simulé : réception, lecture,
composition, brouillons, envoyés, pièces jointes et classement.

| Étape | Mission proposée | Ce que la correction vérifie |
|---|---|---|
| Lire | Retrouver une convocation | Message consulté et information identifiée |
| Composer | Écrire une demande au formateur | Destinataire prévu, objet et éléments de contenu annoncés |
| Répondre | Confirmer une présence | Réponse liée au bon message, destinataire correct |
| Joindre | Envoyer programme.pdf au destinataire fictif | Identité et type de la pièce jointe, contenu requis et destinataire |
| Comprendre les destinataires | Ajouter une personne en copie | Différence entre À, Cc et Cci appliquée à la consigne |
| Organiser | Retrouver, classer ou supprimer un message | Message conservé dans le dossier demandé ou restauré |
| Repérer une tentative de phishing | Signaler un faux message | Indices d'alerte identifiés et action de signalement |

La première livraison couvre lire, composer, répondre, enregistrer un brouillon
et joindre un fichier virtuel. Les autres gestes viennent dans les missions
suivantes. Un simple champ de texte rempli ne suffit pas à prouver une compétence :
les critères doivent vérifier les éléments demandés et le contexte du message.

Le bouton « Envoyer » enregistre un **envoi simulé**. Aucun compte Gmail/Outlook,
aucun mot de passe de messagerie réel ni aucun transport SMTP n'est nécessaire.
L'interface doit indiquer clairement le contexte d'entraînement.

## Missions transversales

Exemple de mission de synthèse à développer après les trois modules :

1. Consulter un site de formation simulé.
2. Télécharger sa fiche dans Téléchargements.
3. Créer Documents/Formation et y déplacer la fiche.
4. Ouvrir la messagerie et répondre à un formateur fictif.
5. Joindre cette fiche et simuler l'envoi.

Le même fichier doit garder une identité stable d'une étape à l'autre. Une
copie crée un nouvel identifiant ; un déplacement conserve l'identifiant.
Chaque tentative doit posséder un état initial reproductible : on ne dépendra
pas arbitrairement d'un exercice ancien que l'apprenant aurait effacé.

Pour les missions indépendantes, fournir les fichiers nécessaires dans l'état
initial. Pour une mission transversale, conserver un espace de travail partagé
au sein de la tentative, avec états fichiers/navigateur/messagerie. La reprise
restaure ensemble ces trois états. Ce mécanisme est à concevoir et n'existe pas
encore dans le code actuel.

## Conséquences sur l'architecture

Le code a été inspecté : `SimulationState`, les handlers de `SimulationEngine`,
la validation des états et `_restore_engine` sont encore spécialisés dans les
fichiers. Ajouter une interface navigateur seule ne suffirait pas.

Avant de développer le navigateur :

- Introduire un contrat de runtime : valider une définition, initialiser,
  appliquer une action, sérialiser/restaurer et évaluer les critères propres
  au domaine.
- Conserver les services communs : authentification, propriétaire, version de
  scénario, tentative, événements idempotents, checkpoints, indices, vérification
  intermédiaire et soumission.
- Prévoir des états distincts : arborescence pour les fichiers ; onglets,
  historiques, favoris et pages pour le navigateur ; dossiers de messages,
  brouillons et pièces jointes pour la messagerie.
- Conserver un évaluateur déterministe côté serveur, avec des opérateurs
  spécialisés appelés par le même cycle d'évaluation.
- Séparer le composant de chaque simulateur du panneau pédagogique commun.
  Le catalogue devra décrire les modules et leurs missions ; le manifeste
  actuel `TRAINING_CODES` ne représente que le premier parcours fichiers.
- Tester la compatibilité des anciens checkpoints avant toute migration de
  leur format. Ne pas réinterpréter une ancienne tentative avec de nouvelles règles.

## Ordre de réalisation et preuves de sortie

1. **Explorateur** : vérifier visuellement la refonte, corriger les interactions,
   compléter copie et corbeille, tester au clavier et auprès de débutants.
2. **Socle multi-runtime** : extraire le contrat commun sans casser les fichiers.
3. **Navigateur initial** : adresse, liens, historique, onglets, correction et reprise.
4. **Navigateur étendu** : favoris, recherche préparée et téléchargement virtuel.
5. **Messagerie initiale** : lire, composer, répondre, brouillon et pièce jointe.
6. **Synthèse** : relier les trois environnements dans une même mission.

À chaque étape : chemin principal, chemin alternatif, erreur compréhensible,
reprise après interruption, isolation des comptes et fonctionnement au clavier.
Les modules Word, Excel et PowerPoint suivent cette base ; l'IA vient enrichir
l'aide après validation des corrections déterministes.
