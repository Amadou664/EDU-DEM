from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'utilisateurs'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='etudiant')

    def __repr__(self):
        return f'<User {self.email}>'

class EtablissementConfig(db.Model):
    __tablename__ = 'etablissement_config'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(160), nullable=False, default='EDU DEM')
    adresse = db.Column(db.String(255), nullable=True)
    telephone = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    logo_path = db.Column(db.String(255), nullable=True)
    frais_scolarite = db.Column(db.Float, nullable=False, default=0.0)
    mail_server = db.Column(db.String(255), nullable=True)
    mail_port = db.Column(db.Integer, nullable=False, default=587)
    mail_username = db.Column(db.String(120), nullable=True)
    mail_password = db.Column(db.String(255), nullable=True)
    mail_use_tls = db.Column(db.Boolean, nullable=False, default=True)
    mail_default_sender = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Classe(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    nom_classe = db.Column(db.String(100), nullable=False)
    niveau = db.Column(db.String(80), nullable=False)
    effectif = db.Column(db.Integer, default=0)
    etudiants = db.relationship('Etudiant', backref='classe', lazy=True)
    emplois = db.relationship('EmploiDuTemps', backref='classe', lazy=True)

    def __repr__(self):
        return f'<Classe {self.nom_classe}>'

class Etudiant(db.Model):
    __tablename__ = 'etudiants'
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(80), unique=True, nullable=False)
    nom = db.Column(db.String(120), nullable=False)
    prenom = db.Column(db.String(120), nullable=False)
    date_naissance = db.Column(db.String(20), nullable=False)
    sexe = db.Column(db.String(20), nullable=False)
    adresse = db.Column(db.String(255), nullable=True)
    telephone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    photo = db.Column(db.String(255), nullable=True)
    classe_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    nom_parent = db.Column(db.String(120), nullable=True)
    email_parent = db.Column(db.String(120), nullable=True)
    telephone_parent = db.Column(db.String(50), nullable=True)
    notes = db.relationship('Note', backref='etudiant', lazy=True)
    absences = db.relationship('Absence', backref='etudiant', lazy=True)
    bulletins = db.relationship('Bulletin', backref='etudiant', lazy=True)

    def __repr__(self):
        return f'<Etudiant {self.matricule}>'

class Professeur(db.Model):
    __tablename__ = 'professeurs'
    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(80), unique=True, nullable=False)
    nom = db.Column(db.String(120), nullable=False)
    prenom = db.Column(db.String(120), nullable=False)
    telephone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    adresse = db.Column(db.String(255), nullable=True)
    matiere_id = db.Column(db.Integer, db.ForeignKey('matieres.id'), nullable=True)
    date_recrutement = db.Column(db.String(30), nullable=True)

    def __repr__(self):
        return f'<Professeur {self.nom} {self.prenom}>'

class Matiere(db.Model):
    __tablename__ = 'matieres'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    nom_matiere = db.Column(db.String(120), nullable=False)
    coefficient = db.Column(db.Float, nullable=False, default=1.0)
    professeur = db.relationship('Professeur', backref='matiere', uselist=False)
    notes = db.relationship('Note', backref='matiere', lazy=True)
    emplois = db.relationship('EmploiDuTemps', backref='matiere', lazy=True)

    def __repr__(self):
        return f'<Matiere {self.nom_matiere}>'

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.Integer, primary_key=True)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('etudiants.id'), nullable=False)
    matiere_id = db.Column(db.Integer, db.ForeignKey('matieres.id'), nullable=False)
    valeur = db.Column(db.Float, nullable=False)
    type_note = db.Column(db.String(80), nullable=False)
    date_note = db.Column(db.String(20), nullable=False)
    semestre = db.Column(db.String(20), nullable=False)

    def __repr__(self):
        return f'<Note {self.valeur}>'

class Absence(db.Model):
    __tablename__ = 'absences'
    id = db.Column(db.Integer, primary_key=True)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('etudiants.id'), nullable=False)
    date_absence = db.Column(db.String(20), nullable=False)
    heure = db.Column(db.String(20), nullable=True)
    heure_arrivee = db.Column(db.String(20), nullable=True)
    statut = db.Column(db.String(30), nullable=False, default='Absent')
    motif = db.Column(db.String(255), nullable=True)
    justification = db.Column(db.String(50), nullable=False, default='Non justifiée')

    def __repr__(self):
        return f'<Absence {self.date_absence}>'

class Bulletin(db.Model):
    __tablename__ = 'bulletins'
    id = db.Column(db.Integer, primary_key=True)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('etudiants.id'), nullable=False)
    semestre = db.Column(db.String(20), nullable=False)
    moyenne_generale = db.Column(db.Float, nullable=False)
    rang = db.Column(db.Integer, nullable=False)
    date_generation = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    published_at = db.Column(db.DateTime, nullable=True)
    notification_status = db.Column(db.String(30), nullable=False, default='Non envoyée')
    notification_message = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Bulletin {self.etudiant_id} - {self.semestre}>'

class EmploiDuTemps(db.Model):
    __tablename__ = 'emplois_du_temps'
    id = db.Column(db.Integer, primary_key=True)
    classe_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    jour = db.Column(db.String(50), nullable=False)
    heure_debut = db.Column(db.String(20), nullable=False)
    heure_fin = db.Column(db.String(20), nullable=False)
    matiere_id = db.Column(db.Integer, db.ForeignKey('matieres.id'), nullable=False)
    salle = db.Column(db.String(100), nullable=False)
    professeur_id = db.Column(db.Integer, db.ForeignKey('professeurs.id'), nullable=False)
    professeur = db.relationship('Professeur', backref='emplois')

class Paiement(db.Model):
    __tablename__ = 'paiements'
    id = db.Column(db.Integer, primary_key=True)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('etudiants.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_paiement = db.Column(db.String(20), nullable=False)
    type_paiement = db.Column(db.String(80), nullable=False)
    etudiant = db.relationship('Etudiant', backref='paiements')

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(160), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    destinataire_role = db.Column(db.String(50), nullable=False, default='tous')
    etudiant_id = db.Column(db.Integer, db.ForeignKey('etudiants.id'), nullable=True)
    date_publication = db.Column(db.DateTime, default=datetime.utcnow)
    etudiant = db.relationship('Etudiant', backref='messages')

class RessourceCours(db.Model):
    __tablename__ = 'ressources_cours'
    id = db.Column(db.Integer, primary_key=True)
    matiere_id = db.Column(db.Integer, db.ForeignKey('matieres.id'), nullable=False)
    titre = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    lien = db.Column(db.String(255), nullable=True)
    date_publication = db.Column(db.DateTime, default=datetime.utcnow)
    matiere = db.relationship('Matiere', backref='ressources')

class Salle(db.Model):
    __tablename__ = 'salles'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(80), unique=True, nullable=False)
    capacite = db.Column(db.Integer, nullable=False)
    type_salle = db.Column(db.String(80), nullable=False)

class MouvementEtudiant(db.Model):
    __tablename__ = 'mouvements_etudiants'
    id = db.Column(db.Integer, primary_key=True)
    etudiant_id = db.Column(db.Integer, db.ForeignKey('etudiants.id'), nullable=False)
    # agent_id was previously required; make it nullable so mouvements peuvent représenter des flux financiers
    agent_id = db.Column(db.Integer, db.ForeignKey('utilisateurs.id'), nullable=True)
    # montant pour suivre les entrées/sorties d'argent
    montant = db.Column(db.Float, nullable=True, default=0.0)
    type_mouvement = db.Column(db.String(20), nullable=False)
    date_mouvement = db.Column(db.String(20), nullable=False)
    heure_mouvement = db.Column(db.String(20), nullable=False)
    motif = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    etudiant = db.relationship('Etudiant', backref='mouvements')
    agent = db.relationship('User', backref='mouvements_enregistres')
