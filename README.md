# Système de Gestion Scolaire (SGS)

Projet de gestion scolaire complet avec :

- Gestion des utilisateurs, rôles et permissions
- Gestion des étudiants, professeurs, classes, matières
- Suivi des notes et des absences
- Génération de bulletins imprimables et export PDF
- Tableau de bord statistique
- Gestion des emplois du temps et des salles
- Rapports et export

## Installation

1. Créez un environnement Python :

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Installez les dépendances :

```bash
pip install -r requirements.txt
```

3. Lancez l'application :

```bash
python app.py
```

4. Ouvrez le navigateur sur `http://127.0.0.1:5000`.

## Accès initial

Un utilisateur admin est créé automatiquement s'il n'existe pas :

- Email : `admin@example.com`
- Mot de passe : `admin123`

Vous pouvez changer ces valeurs avec les variables d'environnement `ADMIN_EMAIL` et `ADMIN_PASSWORD`.

## Structure du projet

- `app.py` : point d'entrée de l'application
- `models.py` : définition des tables
- `forms.py` : formulaires Flask-WTF
- `templates/` : pages HTML avec Bootstrap
- `static/` : ressources CSS/JS

## Fonctionnalités

- Authentification sécurisée et gestion des rôles
- CRUD : étudiants, professeurs, classes, matières, notes, absences
- Génération de bulletins et calcul des moyennes
- Emplois du temps et salles
- Tableau de bord et rapports
- Export PDF des bulletins

> Ce projet est un prototype complet pour démarrer le développement d'un Système de Gestion Scolaire moderne.
