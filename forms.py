from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, FloatField, IntegerField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    mot_de_passe = PasswordField('Mot de passe', validators=[DataRequired()])
    submit = SubmitField('Connexion')

class UserForm(FlaskForm):
    nom = StringField('Nom', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    mot_de_passe = PasswordField('Mot de passe', validators=[Optional(), Length(min=6)])
    role = SelectField('Rôle', choices=[('administrateur', 'Administrateur'), ('professeur', 'Professeur'), ('etudiant', 'Étudiant'), ('parent', 'Parent')], validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class StudentForm(FlaskForm):
    matricule = StringField('Matricule', validators=[DataRequired(), Length(max=80)])
    nom = StringField('Nom', validators=[DataRequired(), Length(max=120)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=120)])
    date_naissance = StringField('Date de naissance', validators=[DataRequired(), Length(max=20)])
    sexe = SelectField('Sexe', choices=[('Masculin', 'Masculin'), ('Féminin', 'Féminin')], validators=[DataRequired()])
    adresse = TextAreaField('Adresse', validators=[Optional(), Length(max=255)])
    telephone = StringField('Téléphone', validators=[Optional(), Length(max=50)])
    email = StringField('Email', validators=[Optional(), Email()])
    classe_id = SelectField('Classe', coerce=int, validators=[Optional()])
    nom_parent = StringField('Nom du parent', validators=[Optional(), Length(max=120)])
    email_parent = StringField('Email du parent', validators=[Optional(), Email(), Length(max=120)])
    telephone_parent = StringField('Téléphone du parent', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Enregistrer')

class ProfessorForm(FlaskForm):
    matricule = StringField('Matricule enseignant', validators=[DataRequired(), Length(max=80)])
    nom = StringField('Nom', validators=[DataRequired(), Length(max=120)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=120)])
    telephone = StringField('Téléphone', validators=[Optional(), Length(max=50)])
    email = StringField('Email', validators=[Optional(), Email()])
    adresse = TextAreaField('Adresse', validators=[Optional(), Length(max=255)])
    matiere_id = SelectField('Matière', coerce=int, validators=[Optional()])
    date_recrutement = StringField('Date recrutement', validators=[Optional(), Length(max=30)])
    submit = SubmitField('Enregistrer')

class ClassForm(FlaskForm):
    nom_classe = StringField('Nom de la classe', validators=[DataRequired(), Length(max=100)])
    niveau = StringField('Niveau', validators=[DataRequired(), Length(max=80)])
    effectif = IntegerField('Effectif', validators=[Optional()])
    submit = SubmitField('Enregistrer')

class SubjectForm(FlaskForm):
    code = StringField('Code matière', validators=[DataRequired(), Length(max=80)])
    nom_matiere = StringField('Nom de la matière', validators=[DataRequired(), Length(max=120)])
    coefficient = FloatField('Coefficient', validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class NoteForm(FlaskForm):
    etudiant_id = SelectField('Étudiant', coerce=int, validators=[DataRequired()])
    matiere_id = SelectField('Matière', coerce=int, validators=[DataRequired()])
    valeur = FloatField('Note', validators=[DataRequired(), NumberRange(min=0, max=20, message='La note doit être entre 0 et 20.')])
    type_note = SelectField('Type de note', choices=[('Devoir', 'Devoir'), ('Interrogation', 'Interrogation'), ('Examen', 'Examen'), ('Travaux pratiques', 'Travaux pratiques')], validators=[DataRequired()])
    date_note = StringField('Date', validators=[DataRequired(), Length(max=20)])
    semestre = SelectField('Semestre', choices=[('Semestre 1', 'Semestre 1'), ('Semestre 2', 'Semestre 2')], validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class AbsenceForm(FlaskForm):
    etudiant_id = SelectField('Étudiant', coerce=int, validators=[DataRequired()])
    date_absence = StringField('Date', validators=[DataRequired(), Length(max=20)])
    heure = StringField('Heure', validators=[Optional(), Length(max=20)])
    heure_arrivee = StringField('Heure arrivée', validators=[Optional(), Length(max=20)])
    statut = SelectField('Statut', choices=[('Absent', 'Absent'), ('Retard', 'Retard')], validators=[DataRequired()])
    motif = StringField('Motif', validators=[Optional(), Length(max=255)])
    justification = SelectField('Justification', choices=[('Justifiée', 'Justifiée'), ('Non justifiée', 'Non justifiée')], validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class TimetableForm(FlaskForm):
    classe_id = SelectField('Classe', coerce=int, validators=[DataRequired()])
    jour = SelectField('Jour', choices=[('Lundi', 'Lundi'), ('Mardi', 'Mardi'), ('Mercredi', 'Mercredi'), ('Jeudi', 'Jeudi'), ('Vendredi', 'Vendredi'), ('Samedi', 'Samedi')], validators=[DataRequired()])
    heure_debut = StringField('Heure début', validators=[DataRequired(), Length(max=20)])
    heure_fin = StringField('Heure fin', validators=[DataRequired(), Length(max=20)])
    matiere_id = SelectField('Matière', coerce=int, validators=[DataRequired()])
    salle = StringField('Salle', validators=[DataRequired(), Length(max=100)])
    professeur_id = SelectField('Professeur', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class SalleForm(FlaskForm):
    numero = StringField('Numéro salle', validators=[DataRequired(), Length(max=80)])
    capacite = IntegerField('Capacité', validators=[DataRequired()])
    type_salle = SelectField('Type', choices=[('Salle normale', 'Salle normale'), ('Laboratoire', 'Laboratoire'), ('Informatique', 'Informatique')], validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class PaiementForm(FlaskForm):
    etudiant_id = SelectField('Étudiant', coerce=int, validators=[DataRequired()])
    montant = FloatField('Montant', validators=[DataRequired()])
    date_paiement = StringField('Date', validators=[DataRequired(), Length(max=20)])
    type_paiement = SelectField('Type paiement', choices=[('Espèces', 'Espèces'), ('Carte', 'Carte'), ('Transfert', 'Transfert')], validators=[DataRequired()])
    submit = SubmitField('Enregistrer')

class EtablissementForm(FlaskForm):
    nom = StringField("Nom de l'établissement", validators=[DataRequired(), Length(max=160)])
    adresse = TextAreaField('Adresse', validators=[Optional(), Length(max=255)])
    telephone = StringField('Téléphone', validators=[Optional(), Length(max=80)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    frais_scolarite = FloatField('Montant minimum exigé pour accéder aux notes', validators=[Optional()])
    mail_server = StringField('Serveur SMTP', validators=[Optional(), Length(max=255)])
    mail_port = IntegerField('Port SMTP', validators=[Optional()])
    mail_username = StringField('Nom utilisateur SMTP', validators=[Optional(), Length(max=120)])
    mail_password = PasswordField('Mot de passe SMTP', validators=[Optional(), Length(max=255)])
    mail_use_tls = SelectField('Utiliser TLS', choices=[('true', 'Oui'), ('false', 'Non')], validators=[Optional()])
    mail_default_sender = StringField('Email expéditeur', validators=[Optional(), Email(), Length(max=120)])
    logo = FileField('Logo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images uniquement.')])
    submit = SubmitField('Enregistrer')

class MouvementEtudiantForm(FlaskForm):
    etudiant_id = SelectField('Étudiant', coerce=int, validators=[DataRequired()])
    type_mouvement = SelectField('Type', choices=[('Entrée', 'Entrée'), ('Sortie', 'Sortie')], validators=[DataRequired()])
    montant = FloatField('Montant', validators=[Optional()])
    date_mouvement = StringField('Date', validators=[DataRequired(), Length(max=20)])
    heure_mouvement = StringField('Heure', validators=[DataRequired(), Length(max=20)])
    motif = StringField('Motif', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Enregistrer')

class MessageForm(FlaskForm):
    titre = StringField('Titre', validators=[DataRequired(), Length(max=160)])
    contenu = TextAreaField('Message', validators=[DataRequired()])
    destinataire_role = SelectField('Destinataire', choices=[('tous', 'Tous'), ('etudiant', 'Étudiants'), ('parent', 'Parents'), ('professeur', 'Professeurs')], validators=[DataRequired()])
    etudiant_id = SelectField('Étudiant précis', coerce=int, validators=[Optional()])
    submit = SubmitField('Publier')
