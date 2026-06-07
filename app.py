import os
import csv
import json
from io import BytesIO, StringIO
from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy import text
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Etudiant, Professeur, Classe, Matiere, Note, Absence, Bulletin, EmploiDuTemps, Salle, Paiement, EtablissementConfig, MouvementEtudiant, Message, RessourceCours
from forms import LoginForm, UserForm, StudentForm, ProfessorForm, ClassForm, SubjectForm, NoteForm, AbsenceForm, TimetableForm, SalleForm, PaiementForm, EtablissementForm, MouvementEtudiantForm, MessageForm
from utils import render_pdf, send_email, make_qr_data_uri
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

initialized_database = False

def roles_required(*roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash('Accès refusé.', 'danger')
                return redirect(url_for('dashboard'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

def ensure_column(table_name, column_name, column_definition):
    columns = db.session.execute(text(f'PRAGMA table_info({table_name})')).fetchall()
    if column_name not in {column[1] for column in columns}:
        db.session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}'))
        db.session.commit()

def ensure_schema():
    if not db.engine.url.drivername.startswith('sqlite'):
        return
    ensure_column('etudiants', 'email_parent', 'VARCHAR(120)')
    ensure_column('absences', 'heure_arrivee', 'VARCHAR(20)')
    ensure_column('absences', 'statut', "VARCHAR(30) NOT NULL DEFAULT 'Absent'")
    ensure_column('bulletins', 'is_published', 'BOOLEAN NOT NULL DEFAULT 0')
    ensure_column('bulletins', 'published_at', 'DATETIME')
    ensure_column('bulletins', 'notification_status', "VARCHAR(30) NOT NULL DEFAULT 'Non envoyée'")
    ensure_column('bulletins', 'notification_message', 'VARCHAR(255)')
    ensure_column('mouvements_etudiants', 'montant', 'FLOAT')
    ensure_column('etablissement_config', 'frais_scolarite', 'FLOAT NOT NULL DEFAULT 0.0')
    ensure_column('etablissement_config', 'mail_server', 'VARCHAR(255)')
    ensure_column('etablissement_config', 'mail_port', 'INTEGER NOT NULL DEFAULT 587')
    ensure_column('etablissement_config', 'mail_username', 'VARCHAR(120)')
    ensure_column('etablissement_config', 'mail_password', 'VARCHAR(255)')
    ensure_column('etablissement_config', 'mail_use_tls', 'BOOLEAN NOT NULL DEFAULT 1')
    ensure_column('etablissement_config', 'mail_default_sender', 'VARCHAR(120)')
    # rendre agent_id nullable si nécessaire (SQLite ne supporte facilement ALTER ... DROP NOT NULL)
    columns = db.session.execute(text("PRAGMA table_info(mouvements_etudiants)")).fetchall()
    if 'agent_id' in {col[1] for col in columns}:
        pass

def get_school_settings():
    settings = EtablissementConfig.query.first()
    if settings is None:
        settings = EtablissementConfig(nom='EDU DEM', frais_scolarite=0.0)
        db.session.add(settings)
        db.session.commit()
    return settings


def student_has_paid_sufficiently(etudiant):
    required = get_school_settings().frais_scolarite or 0.0
    total = sum(p.montant for p in etudiant.paiements) if etudiant.paiements else 0.0
    return total >= required, total, required

def initialize_database():
    global initialized_database
    if initialized_database:
        return
    db.create_all()
    ensure_schema()
    get_school_settings()
    admin_email = app.config.get('ADMIN_EMAIL')
    admin_password = app.config.get('ADMIN_PASSWORD')
    admin = User.query.filter_by(email=admin_email).first()
    legacy_admin = User.query.filter_by(email='admin@edupage.local').first()
    if legacy_admin and not admin:
        legacy_admin.email = admin_email
        admin = legacy_admin
    if not admin:
        admin = User(
            nom='Administrateur',
            email=admin_email,
            mot_de_passe=generate_password_hash(admin_password),
            role='administrateur'
        )
        db.session.add(admin)
    db.session.commit()
    initialized_database = True

@app.before_request
def before_request_initialize_database():
    initialize_database()

@app.context_processor
def inject_school_settings():
    if not initialized_database:
        return {'school_settings': None, 'app_name': 'EDU DEM', 'mail_configured': False}
    settings = get_school_settings()
    mail_configured = bool(app.config.get('MAIL_SERVER') or settings.mail_server)
    return {'school_settings': settings, 'app_name': settings.nom or 'EDU DEM', 'mail_configured': mail_configured}

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.mot_de_passe, form.mot_de_passe.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Email ou mot de passe incorrect.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
@roles_required('administrateur', 'professeur')
def dashboard():
    total_etudiants = Etudiant.query.count()
    total_professeurs = Professeur.query.count()
    total_classes = Classe.query.count()
    total_absences = Absence.query.count()
    total_retards = Absence.query.filter_by(statut='Retard').count()
    bulletins_publies = Bulletin.query.filter_by(is_published=True).count()
    entrees_jour = MouvementEtudiant.query.filter_by(type_mouvement='Entrée', date_mouvement=datetime.now().strftime('%Y-%m-%d')).count()
    sorties_jour = MouvementEtudiant.query.filter_by(type_mouvement='Sortie', date_mouvement=datetime.now().strftime('%Y-%m-%d')).count()
    total_paiements = sum(p.montant for p in Paiement.query.all()) if Paiement.query.count() else 0
    total_entrees = sum((m.montant or 0) for m in MouvementEtudiant.query.filter_by(type_mouvement='Entrée').all())
    total_sorties = sum((m.montant or 0) for m in MouvementEtudiant.query.filter_by(type_mouvement='Sortie').all())
    required_payment = get_school_settings().frais_scolarite or 0.0
    etudiants_impayes = 0
    if required_payment > 0:
        for etudiant in Etudiant.query.all():
            total = sum(p.montant for p in etudiant.paiements) if etudiant.paiements else 0
            if total < required_payment:
                etudiants_impayes += 1
    moyenne_generale = 0
    notes = Note.query.all()
    if notes:
        moyenne_generale = sum(n.valeur for n in notes) / len(notes)
    chart_classes = []
    for classe in Classe.query.all():
        chart_classes.append({'label': classe.nom_classe, 'value': len(classe.etudiants)})
    return render_template('dashboard.html', total_etudiants=total_etudiants,
                           total_professeurs=total_professeurs, total_classes=total_classes,
                           total_absences=total_absences, total_retards=total_retards,
                           bulletins_publies=bulletins_publies, entrees_jour=entrees_jour,
                           sorties_jour=sorties_jour, moyenne_generale=round(moyenne_generale, 2),
                           total_paiements=round(total_paiements, 2), total_entrees=round(total_entrees, 2),
                           total_sorties=round(total_sorties, 2), etudiants_impayes=etudiants_impayes,
                           required_payment=required_payment, chart_classes=chart_classes)

def get_current_student():
    return Etudiant.query.filter_by(email=current_user.email).first()

def get_parent_students():
    return Etudiant.query.filter_by(email_parent=current_user.email).all()

def can_user_access_student(etudiant):
    if current_user.role in ['administrateur', 'professeur']:
        return True
    if current_user.role == 'etudiant':
        return etudiant is not None and etudiant.email == current_user.email
    if current_user.role == 'parent':
        return etudiant is not None and etudiant.email_parent == current_user.email
    return False

def student_portal_context(etudiant):
    today = datetime.now()
    jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    jour = jours[today.weekday()]
    emplois = []
    if etudiant.classe_id:
        emplois = EmploiDuTemps.query.filter_by(classe_id=etudiant.classe_id, jour=jour).order_by(EmploiDuTemps.heure_debut).all()
    messages = Message.query.filter(
        (Message.destinataire_role.in_(['tous', 'etudiant'])) |
        (Message.etudiant_id == etudiant.id)
    ).order_by(Message.date_publication.desc()).limit(5).all()
    absences_recentes = Absence.query.filter_by(etudiant_id=etudiant.id).order_by(Absence.id.desc()).limit(5).all()
    paiements = Paiement.query.filter_by(etudiant_id=etudiant.id).order_by(Paiement.id.desc()).all()
    bulletins_recents = Bulletin.query.filter_by(etudiant_id=etudiant.id, is_published=True).order_by(Bulletin.date_generation.desc()).limit(3).all()
    ressources = RessourceCours.query.order_by(RessourceCours.date_publication.desc()).limit(6).all()
    has_paid, total_paid, required = student_has_paid_sufficiently(etudiant)
    if has_paid:
        notes_recentes = Note.query.filter_by(etudiant_id=etudiant.id).order_by(Note.id.desc()).limit(6).all()
        moyenne = compute_student_average(etudiant, 'Semestre 1') or compute_student_average(etudiant, 'Semestre 2')
    else:
        notes_recentes = []
        moyenne = None
    return {
        'etudiant': etudiant,
        'jour': jour,
        'date_jour': today.strftime('%d.%m.'),
        'emplois': emplois,
        'messages': messages,
        'notes_recentes': notes_recentes,
        'absences_recentes': absences_recentes,
        'paiements': paiements[:5],
        'bulletins_recents': bulletins_recents,
        'ressources': ressources,
        'moyenne': round(moyenne, 2) if moyenne is not None else None,
        'blocked_by_payment': not has_paid,
        'total_paid': total_paid,
        'required_payment': required,
    }

@app.route('/student-dashboard')
@app.route('/student-dashboard/<int:student_id>')
@login_required
def student_dashboard(student_id=None):
    if current_user.role == 'etudiant':
        etudiant = get_current_student()
        if etudiant is None:
            flash('Aucune fiche étudiant n’est liée à votre compte email.', 'warning')
            return redirect(url_for('dashboard'))
    elif current_user.role == 'parent':
        enfants = get_parent_students()
        if not enfants:
            flash('Aucun enfant trouvé lié à votre compte parent.', 'warning')
            return redirect(url_for('dashboard'))
        if student_id is None:
            etudiant = enfants[0]
        else:
            etudiant = next((e for e in enfants if e.id == student_id), None)
            if etudiant is None:
                flash('Enfant introuvable.', 'warning')
                return redirect(url_for('student_dashboard'))
    else:
        if student_id is None:
            etudiant = Etudiant.query.order_by(Etudiant.nom).first()
        else:
            etudiant = Etudiant.query.get_or_404(student_id)
    if etudiant is None:
        flash('Ajoutez d’abord un étudiant.', 'warning')
        return redirect(url_for('students'))
    etudiants = []
    if current_user.role == 'administrateur':
        etudiants = Etudiant.query.order_by(Etudiant.nom).all()
    elif current_user.role == 'parent':
        etudiants = get_parent_students()
    return render_template('student_dashboard.html', etudiants=etudiants, **student_portal_context(etudiant))

@app.route('/messages', methods=['GET', 'POST'])
@login_required
def messages():
    form = MessageForm()
    form.etudiant_id.choices = [(0, 'Tous')] + [(e.id, f'{e.matricule} - {e.nom} {e.prenom}') for e in Etudiant.query.order_by(Etudiant.nom).all()]
    if current_user.role in ['administrateur', 'professeur'] and form.validate_on_submit():
        message = Message(
            titre=form.titre.data,
            contenu=form.contenu.data,
            destinataire_role=form.destinataire_role.data,
            etudiant_id=form.etudiant_id.data if form.etudiant_id.data else None
        )
        db.session.add(message)
        db.session.commit()
        flash('Message publié.', 'success')
        return redirect(url_for('messages'))
    messages_list = Message.query.order_by(Message.date_publication.desc()).all()
    return render_template('messages.html', form=form, messages=messages_list)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def settings():
    settings = get_school_settings()
    form = EtablissementForm(obj=settings)
    if request.method == 'GET':
        form.mail_use_tls.data = 'true' if settings.mail_use_tls else 'false'
    if form.validate_on_submit():
        settings.nom = form.nom.data
        settings.adresse = form.adresse.data
        settings.telephone = form.telephone.data
        settings.email = form.email.data
        settings.frais_scolarite = form.frais_scolarite.data or 0.0
        settings.mail_server = form.mail_server.data or settings.mail_server
        settings.mail_port = form.mail_port.data or settings.mail_port
        settings.mail_username = form.mail_username.data or settings.mail_username
        if form.mail_password.data:
            settings.mail_password = form.mail_password.data
        settings.mail_use_tls = form.mail_use_tls.data == 'true'
        settings.mail_default_sender = form.mail_default_sender.data or settings.mail_default_sender
        settings.updated_at = datetime.utcnow()
        logo = form.logo.data
        if logo:
            filename = secure_filename(logo.filename)
            extension = filename.rsplit('.', 1)[-1].lower()
            logo_filename = f'etablissement_logo.{extension}'
            logo.save(os.path.join(app.config['UPLOAD_FOLDER'], logo_filename))
            settings.logo_path = f'uploads/{logo_filename}'
        db.session.commit()
        flash('Paramètres de l’établissement enregistrés.', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', form=form, settings=settings)


@app.route('/settings/test-smtp', methods=['POST'])
@login_required
@roles_required('administrateur')
def test_smtp():
    test_email = request.form.get('test_email') or app.config.get('MAIL_DEFAULT_SENDER')
    subject = 'Test de configuration SMTP - EDU DEM'
    sent, message = send_email(test_email, subject, 'Ceci est un email de test envoyé depuis EDU DEM.')
    flash(message, 'success' if sent else 'danger')
    return redirect(url_for('settings'))

@app.route('/reception', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur', 'professeur')
def reception():
    form = MouvementEtudiantForm()
    form.etudiant_id.choices = [(e.id, f'{e.matricule} - {e.nom} {e.prenom}') for e in Etudiant.query.order_by(Etudiant.nom).all()]
    if request.method == 'GET':
        now = datetime.now()
        form.date_mouvement.data = now.strftime('%Y-%m-%d')
        form.heure_mouvement.data = now.strftime('%H:%M')
    if form.validate_on_submit():
        montant = float(form.montant.data) if form.montant.data else None
        mouvement = MouvementEtudiant(
            etudiant_id=form.etudiant_id.data,
            agent_id=current_user.id,
            montant=montant,
            type_mouvement=form.type_mouvement.data,
            date_mouvement=form.date_mouvement.data,
            heure_mouvement=form.heure_mouvement.data,
            motif=form.motif.data
        )
        db.session.add(mouvement)
        db.session.commit()
        flash('Mouvement enregistré.', 'success')
        return redirect(url_for('reception'))
    mouvements = MouvementEtudiant.query.order_by(MouvementEtudiant.created_at.desc()).limit(80).all()
    return render_template('reception.html', form=form, mouvements=mouvements)

@app.route('/users')
@login_required
@roles_required('administrateur')
def users():
    personnes = User.query.all()
    return render_template('users.html', personnes=personnes)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_user():
    if current_user.role != 'administrateur':
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dashboard'))
    form = UserForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.mot_de_passe.data) if form.mot_de_passe.data else generate_password_hash('secret')
        user = User(nom=form.nom.data, email=form.email.data, mot_de_passe=hashed_password, role=form.role.data)
        db.session.add(user)
        db.session.commit()
        flash('Utilisateur ajouté.', 'success')
        return redirect(url_for('users'))
    return render_template('user_form.html', form=form, title='Ajouter un utilisateur')

@app.route('/students')
@login_required
@roles_required('administrateur', 'professeur')
def students():
    etudiants = Etudiant.query.all()
    return render_template('students.html', etudiants=etudiants)


@app.route('/export/students')
@login_required
@roles_required('administrateur')
def export_students():
    si = StringIO()
    writer = csv.writer(si)
    header = ['matricule','nom','prenom','date_naissance','sexe','adresse','telephone','email','classe_nom','nom_parent','email_parent','telephone_parent']
    writer.writerow(header)
    for e in Etudiant.query.order_by(Etudiant.id).all():
        classe_nom = e.classe.nom_classe if e.classe else ''
        writer.writerow([
            e.matricule or '', e.nom or '', e.prenom or '', e.date_naissance or '', e.sexe or '',
            e.adresse or '', e.telephone or '', e.email or '', classe_nom,
            e.nom_parent or '', e.email_parent or '', e.telephone_parent or ''
        ])
    mem = BytesIO()
    mem.write(si.getvalue().encode('utf-8'))
    mem.seek(0)
    filename = f'etudiants-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'
    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name=filename)


@app.route('/import/students', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def import_students():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('Aucun fichier sélectionné.', 'warning')
            return redirect(url_for('import_students'))
        stream = StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        added = 0
        for row in reader:
            matricule = (row.get('matricule') or '').strip()
            email = (row.get('email') or '').strip()
            existing = None
            if matricule:
                existing = Etudiant.query.filter_by(matricule=matricule).first()
            if not existing and email:
                existing = Etudiant.query.filter_by(email=email).first()
            if existing:
                # update some fields
                existing.nom = row.get('nom') or existing.nom
                existing.prenom = row.get('prenom') or existing.prenom
                existing.telephone = row.get('telephone') or existing.telephone
                existing.email_parent = row.get('email_parent') or existing.email_parent
            else:
                classe_nom = (row.get('classe_nom') or '').strip()
                classe = Classe.query.filter_by(nom_classe=classe_nom).first() if classe_nom else None
                etu = Etudiant(
                    matricule=matricule or None,
                    nom=row.get('nom') or None,
                    prenom=row.get('prenom') or None,
                    date_naissance=row.get('date_naissance') or None,
                    sexe=row.get('sexe') or None,
                    adresse=row.get('adresse') or None,
                    telephone=row.get('telephone') or None,
                    email=email or None,
                    classe_id=classe.id if classe else None,
                    nom_parent=row.get('nom_parent') or None,
                    email_parent=row.get('email_parent') or None,
                    telephone_parent=row.get('telephone_parent') or None
                )
                db.session.add(etu)
                added += 1
        db.session.commit()
        flash(f'Import terminé. {added} nouvel(le)(s) étudiant(s) ajouté(s).', 'success')
        return redirect(url_for('students'))
    return render_template('import_students.html')

@app.route('/students/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_student():
    form = StudentForm()
    form.classe_id.choices = [(0, '---')] + [(c.id, c.nom_classe) for c in Classe.query.all()]
    if form.validate_on_submit():
        etudiant = Etudiant(
            matricule=form.matricule.data,
            nom=form.nom.data,
            prenom=form.prenom.data,
            date_naissance=form.date_naissance.data,
            sexe=form.sexe.data,
            adresse=form.adresse.data,
            telephone=form.telephone.data,
            email=form.email.data,
            classe_id=form.classe_id.data if form.classe_id.data else None,
            nom_parent=form.nom_parent.data,
            email_parent=form.email_parent.data,
            telephone_parent=form.telephone_parent.data
        )
        db.session.add(etudiant)
        db.session.commit()
        flash('Étudiant ajouté.', 'success')
        return redirect(url_for('students'))
    return render_template('student_form.html', form=form, title='Ajouter un étudiant')

@app.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def edit_student(student_id):
    etudiant = Etudiant.query.get_or_404(student_id)
    form = StudentForm(obj=etudiant)
    form.classe_id.choices = [(0, '---')] + [(c.id, c.nom_classe) for c in Classe.query.all()]
    if request.method == 'GET':
        form.classe_id.data = etudiant.classe_id or 0
    if form.validate_on_submit():
        etudiant.matricule = form.matricule.data
        etudiant.nom = form.nom.data
        etudiant.prenom = form.prenom.data
        etudiant.date_naissance = form.date_naissance.data
        etudiant.sexe = form.sexe.data
        etudiant.adresse = form.adresse.data
        etudiant.telephone = form.telephone.data
        etudiant.email = form.email.data
        etudiant.classe_id = form.classe_id.data if form.classe_id.data else None
        etudiant.nom_parent = form.nom_parent.data
        etudiant.email_parent = form.email_parent.data
        etudiant.telephone_parent = form.telephone_parent.data
        db.session.commit()
        flash('Étudiant modifié.', 'success')
        return redirect(url_for('students'))
    return render_template('student_form.html', form=form, title='Modifier un étudiant')

@app.route('/students/delete/<int:student_id>')
@login_required
@roles_required('administrateur')
def delete_student(student_id):
    etudiant = Etudiant.query.get_or_404(student_id)
    db.session.delete(etudiant)
    db.session.commit()
    flash('Étudiant supprimé.', 'success')
    return redirect(url_for('students'))

@app.route('/professors')
@login_required
@roles_required('administrateur', 'professeur')
def professors():
    profs = Professeur.query.all()
    return render_template('professors.html', profs=profs)

@app.route('/professors/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_professor():
    form = ProfessorForm()
    form.matiere_id.choices = [(0, '---')] + [(m.id, m.nom_matiere) for m in Matiere.query.all()]
    if form.validate_on_submit():
        prof = Professeur(
            matricule=form.matricule.data,
            nom=form.nom.data,
            prenom=form.prenom.data,
            telephone=form.telephone.data,
            email=form.email.data,
            adresse=form.adresse.data,
            matiere_id=form.matiere_id.data if form.matiere_id.data else None,
            date_recrutement=form.date_recrutement.data
        )
        db.session.add(prof)
        db.session.commit()
        flash('Professeur ajouté.', 'success')
        return redirect(url_for('professors'))
    return render_template('professor_form.html', form=form, title='Ajouter un professeur')

@app.route('/classes')
@login_required
@roles_required('administrateur', 'professeur')
def classes():
    classes_list = Classe.query.all()
    return render_template('classes.html', classes=classes_list)

@app.route('/classes/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_class():
    form = ClassForm()
    if form.validate_on_submit():
        classe = Classe(nom_classe=form.nom_classe.data, niveau=form.niveau.data, effectif=form.effectif.data or 0)
        db.session.add(classe)
        db.session.commit()
        flash('Classe ajoutée.', 'success')
        return redirect(url_for('classes'))
    return render_template('class_form.html', form=form, title='Ajouter une classe')

@app.route('/subjects')
@login_required
@roles_required('administrateur', 'professeur')
def subjects():
    matieres = Matiere.query.all()
    return render_template('subjects.html', matieres=matieres)

@app.route('/subjects/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        matiere = Matiere(code=form.code.data, nom_matiere=form.nom_matiere.data, coefficient=form.coefficient.data)
        db.session.add(matiere)
        db.session.commit()
        flash('Matière ajoutée.', 'success')
        return redirect(url_for('subjects'))
    return render_template('subject_form.html', form=form, title='Ajouter une matière')

@app.route('/notes')
@login_required
def notes():
    if current_user.role in ['administrateur', 'professeur']:
        notes_list = Note.query.all()
        return render_template('notes.html', notes=notes_list)
    if current_user.role == 'etudiant':
        etudiant = Etudiant.query.filter_by(email=current_user.email).first()
        if etudiant is None:
            flash('Aucune fiche étudiant trouvée.', 'warning')
            return redirect(url_for('dashboard'))
        has_paid, total_paid, required = student_has_paid_sufficiently(etudiant)
        if not has_paid:
            flash(f"Accès aux notes restreint : payez {required:.2f} CFA minimum pour afficher vos notes.", 'warning')
            return redirect(url_for('student_dashboard'))
        notes_list = Note.query.filter_by(etudiant_id=etudiant.id).all()
        return render_template('notes.html', notes=notes_list)
    if current_user.role == 'parent':
        enfants = get_parent_students()
        if not enfants:
            flash('Aucun enfant trouvé lié à votre compte parent.', 'warning')
            return redirect(url_for('dashboard'))
        enfant_ids = [e.id for e in enfants]
        notes_list = Note.query.filter(Note.etudiant_id.in_(enfant_ids)).all()
        return render_template('notes.html', notes=notes_list)
    flash('Accès refusé.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/notes/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur', 'professeur')
def add_note():
    form = NoteForm()
    form.etudiant_id.choices = [(e.id, f'{e.matricule} - {e.nom} {e.prenom}') for e in Etudiant.query.all()]
    form.matiere_id.choices = [(m.id, m.nom_matiere) for m in Matiere.query.all()]
    if form.validate_on_submit():
        note = Note(etudiant_id=form.etudiant_id.data, matiere_id=form.matiere_id.data, valeur=form.valeur.data,
                    type_note=form.type_note.data, date_note=form.date_note.data, semestre=form.semestre.data)
        db.session.add(note)
        db.session.commit()
        flash('Note ajoutée.', 'success')
        return redirect(url_for('notes'))
    return render_template('note_form.html', form=form, title='Ajouter une note')

@app.route('/absences')
@login_required
def absences():
    if current_user.role in ['administrateur', 'professeur']:
        absences_list = Absence.query.all()
        return render_template('absences.html', absences=absences_list)
    if current_user.role == 'etudiant':
        etudiant = Etudiant.query.filter_by(email=current_user.email).first()
        if etudiant is None:
            flash('Aucune fiche étudiant trouvée.', 'warning')
            return redirect(url_for('dashboard'))
        absences_list = Absence.query.filter_by(etudiant_id=etudiant.id).all()
        return render_template('absences.html', absences=absences_list)
    if current_user.role == 'parent':
        enfants = get_parent_students()
        if not enfants:
            flash('Aucun enfant trouvé lié à votre compte parent.', 'warning')
            return redirect(url_for('dashboard'))
        enfant_ids = [e.id for e in enfants]
        absences_list = Absence.query.filter(Absence.etudiant_id.in_(enfant_ids)).all()
        return render_template('absences.html', absences=absences_list)
    flash('Accès refusé.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/absences/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur', 'professeur')
def add_absence():
    form = AbsenceForm()
    form.etudiant_id.choices = [(e.id, f'{e.matricule} - {e.nom} {e.prenom}') for e in Etudiant.query.all()]
    if form.validate_on_submit():
        absence = Absence(
            etudiant_id=form.etudiant_id.data,
            date_absence=form.date_absence.data,
            heure=form.heure.data,
            heure_arrivee=form.heure_arrivee.data,
            statut=form.statut.data,
            motif=form.motif.data,
            justification=form.justification.data
        )
        db.session.add(absence)
        db.session.commit()
        flash('Absence ajoutée.', 'success')
        return redirect(url_for('absences'))
    return render_template('absence_form.html', form=form, title='Ajouter une absence')

@app.route('/bulletins')
@login_required
def bulletins():
    if current_user.role in ['administrateur', 'professeur']:
        etudiants = Etudiant.query.all()
        bulletins_list = Bulletin.query.order_by(Bulletin.date_generation.desc()).all()
        return render_template('bulletins.html', etudiants=etudiants, bulletins=bulletins_list)
    if current_user.role == 'etudiant':
        etudiants = [Etudiant.query.filter_by(email=current_user.email).first()]
    elif current_user.role == 'parent':
        etudiants = get_parent_students()
    else:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dashboard'))
    etudiants = [e for e in etudiants if e is not None]
    if not etudiants:
        flash('Aucune fiche étudiant trouvée.', 'warning')
        return redirect(url_for('dashboard'))
    etudiant = etudiants[0]
    has_paid, _, required = student_has_paid_sufficiently(etudiant)
    if not has_paid:
        flash(f"Accès aux bulletins restreint : payez {required:.2f} CFA minimum.", 'warning')
        return redirect(url_for('student_dashboard'))
    enfant_ids = [e.id for e in etudiants]
    bulletins_list = Bulletin.query.filter(Bulletin.etudiant_id.in_(enfant_ids), Bulletin.is_published == True).order_by(Bulletin.date_generation.desc()).all()
    return render_template('bulletins.html', etudiants=etudiants, bulletins=bulletins_list)

def compute_bulletin_data(etudiant, semestre):
    notes = Note.query.filter_by(etudiant_id=etudiant.id, semestre=semestre).all()
    matiere_data = []
    total_coeff = 0
    total_points = 0
    for matiere in Matiere.query.all():
        notes_matiere = [n for n in notes if n.matiere_id == matiere.id]
        if not notes_matiere:
            continue
        moyenne_matiere = sum(n.valeur for n in notes_matiere) / len(notes_matiere)
        points = moyenne_matiere * matiere.coefficient
        total_coeff += matiere.coefficient
        total_points += points
        matiere_data.append({
            'matiere': matiere.nom_matiere,
            'coefficient': matiere.coefficient,
            'moyenne': round(moyenne_matiere, 2),
            'notes': notes_matiere
        })
    moyenne_generale = round(total_points / total_coeff, 2) if total_coeff else 0
    all_students = Etudiant.query.filter_by(classe_id=etudiant.classe_id).all() if etudiant.classe_id else Etudiant.query.all()
    rang = 1
    classe_moyennes = []
    for etud in all_students:
        moyenne_etud = compute_student_average(etud, semestre)
        if moyenne_etud is not None:
            classe_moyennes.append((etud.id, moyenne_etud))
    classe_moyennes.sort(key=lambda x: x[1], reverse=True)
    for idx, pair in enumerate(classe_moyennes, start=1):
        if pair[0] == etudiant.id:
            rang = idx
            break
    mention = 'Insuffisant'
    if moyenne_generale >= 16:
        mention = 'Très Bien'
    elif moyenne_generale >= 14:
        mention = 'Bien'
    elif moyenne_generale >= 12:
        mention = 'Assez Bien'
    elif moyenne_generale >= 10:
        mention = 'Passable'
    qr_payload = {
        'application': 'EDU DEM',
        'matricule': etudiant.matricule,
        'nom': etudiant.nom,
        'prenom': etudiant.prenom,
        'classe': etudiant.classe.nom_classe if etudiant.classe else None,
        'semestre': semestre,
        'moyenne_generale': moyenne_generale,
        'rang': rang,
        'mention': mention,
    }
    return {
        'matiere_data': matiere_data,
        'moyenne_generale': moyenne_generale,
        'rang': rang,
        'mention': mention,
        'qr_code': make_qr_data_uri(qr_payload),
        'school': get_school_settings()
    }

def compute_student_average(etudiant, semestre):
    notes = Note.query.filter_by(etudiant_id=etudiant.id, semestre=semestre).all()
    if not notes:
        return None
    total_coeff = 0
    total_points = 0
    for matiere in Matiere.query.all():
        notes_matiere = [n for n in notes if n.matiere_id == matiere.id]
        if not notes_matiere:
            continue
        moyenne_matiere = sum(n.valeur for n in notes_matiere) / len(notes_matiere)
        total_coeff += matiere.coefficient
        total_points += moyenne_matiere * matiere.coefficient
    return total_points / total_coeff if total_coeff else None

def notify_parent_for_bulletin(bulletin):
    etudiant = bulletin.etudiant
    subject = f'Bulletin publié - {etudiant.nom} {etudiant.prenom} - {bulletin.semestre}'
    body = (
        f'Bonjour {etudiant.nom_parent or ""},\n\n'
        f'Le bulletin de {etudiant.nom} {etudiant.prenom} pour {bulletin.semestre} a été publié.\n'
        f'Moyenne générale: {bulletin.moyenne_generale}/20\n'
        f'Rang: {bulletin.rang}\n\n'
        "Veuillez vous rapprocher de l'administration ou consulter la plateforme pour plus de détails.\n"
    )
    # keep backward-compatible: send a simple notification (no attachment)
    sent, message = send_email(etudiant.email_parent, subject, body)
    bulletin.notification_status = 'Envoyée' if sent else 'Échec'
    bulletin.notification_message = message[:255]
    return sent, message

@app.route('/bulletins/generate', methods=['POST'])
@login_required
@roles_required('administrateur', 'professeur')
def generate_bulletin():
    etudiant_id = request.form.get('etudiant_id', type=int)
    semestre = request.form.get('semestre')
    etudiant = Etudiant.query.get_or_404(etudiant_id)
    data = compute_bulletin_data(etudiant, semestre)
    bulletin = Bulletin.query.filter_by(etudiant_id=etudiant.id, semestre=semestre).first()
    if bulletin is None:
        bulletin = Bulletin(etudiant_id=etudiant.id, semestre=semestre, moyenne_generale=data['moyenne_generale'], rang=data['rang'])
        db.session.add(bulletin)
    else:
        bulletin.moyenne_generale = data['moyenne_generale']
        bulletin.rang = data['rang']
        bulletin.date_generation = datetime.utcnow()
        bulletin.is_published = False
        bulletin.published_at = None
        bulletin.notification_status = 'Non envoyée'
        bulletin.notification_message = None
    db.session.commit()
    flash('Bulletin généré.', 'success')
    return render_template('bulletin.html', etudiant=etudiant, semestre=semestre, **data)

@app.route('/bulletins/publish/<int:bulletin_id>', methods=['POST'])
@login_required
@roles_required('administrateur', 'professeur')
def publish_bulletin(bulletin_id):
    bulletin = Bulletin.query.get_or_404(bulletin_id)
    bulletin.is_published = True
    bulletin.published_at = datetime.utcnow()
    # try to generate PDF and attach to email when sending to parent
    etudiant = bulletin.etudiant
    data = compute_bulletin_data(etudiant, bulletin.semestre)
    has_paid, total_paid, required_payment = student_has_paid_sufficiently(etudiant)
    settings = get_school_settings()
    logo_file_path = None
    logo_data_uri = None
    if settings and settings.logo_path:
        logo_abs = os.path.join(app.root_path, 'static', settings.logo_path)
        if os.path.exists(logo_abs):
            try:
                import base64
                ext = os.path.splitext(logo_abs)[1].lower().lstrip('.')
                with open(logo_abs, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('ascii')
                    logo_data_uri = f'data:image/{ext};base64,' + encoded
            except Exception:
                logo_data_uri = None
    pdf = render_pdf(
        'bulletin_print.html',
        etudiant=etudiant,
        semestre=bulletin.semestre,
        logo_file_path=logo_file_path,
        logo_data_uri=logo_data_uri,
        total_paid=total_paid,
        required_payment=required_payment,
        **data
    )
    if pdf is not None:
        pdf_bytes = pdf.read()
        sent, message = send_email(etudiant.email_parent, f'Bulletin {bulletin.semestre} - {etudiant.nom} {etudiant.prenom}',
                                   f'Bonjour {etudiant.nom_parent or ""},\n\nVeuillez trouver ci-joint le bulletin de {etudiant.nom} {etudiant.prenom}.',
                                   attachment_bytes=pdf_bytes, attachment_filename=f'bulletin_{etudiant.matricule}_{bulletin.semestre}.pdf')
    else:
        sent, message = notify_parent_for_bulletin(bulletin)
    bulletin.notification_status = 'Envoyée' if sent else 'Échec'
    bulletin.notification_message = message[:255]
    db.session.commit()
    flash(message, 'success' if sent else 'warning')
    return redirect(url_for('bulletins'))


@app.route('/bulletins/retry/<int:bulletin_id>', methods=['POST'])
@login_required
@roles_required('administrateur', 'professeur')
def retry_bulletin(bulletin_id):
    bulletin = Bulletin.query.get_or_404(bulletin_id)
    etudiant = bulletin.etudiant
    data = compute_bulletin_data(etudiant, bulletin.semestre)
    has_paid, total_paid, required_payment = student_has_paid_sufficiently(etudiant)
    # regenerate PDF and resend
    pdf = render_pdf(
        'bulletin_print.html',
        etudiant=etudiant,
        semestre=bulletin.semestre,
        total_paid=total_paid,
        required_payment=required_payment,
        **data
    )
    if pdf is None:
        flash('Impossible de générer le PDF pour envoi.', 'danger')
        return redirect(url_for('bulletins'))
    pdf_bytes = pdf.read()
    sent, message = send_email(etudiant.email_parent, f'Bulletin {bulletin.semestre} - {etudiant.nom} {etudiant.prenom}',
                               f'Bonjour {etudiant.nom_parent or ""},\n\nVeuillez trouver ci-joint le bulletin de {etudiant.nom} {etudiant.prenom}.',
                               attachment_bytes=pdf_bytes, attachment_filename=f'bulletin_{etudiant.matricule}_{bulletin.semestre}.pdf')
    bulletin.notification_status = 'Envoyée' if sent else 'Échec'
    bulletin.notification_message = message[:255]
    db.session.commit()
    flash(message, 'success' if sent else 'danger')
    return redirect(url_for('bulletins'))

@app.route('/bulletins/print/<int:bulletin_id>')
@login_required
def print_bulletin(bulletin_id):
    bulletin = Bulletin.query.get_or_404(bulletin_id)
    etudiant = bulletin.etudiant
    if current_user.role == 'etudiant':
        if current_user.email != etudiant.email:
            flash('Accès refusé.', 'danger')
            return redirect(url_for('dashboard'))
        has_paid, _, required = student_has_paid_sufficiently(etudiant)
        if not has_paid:
            flash(f"Accès au bulletin restreint : payez {required:.2f} CFA minimum.", 'warning')
            return redirect(url_for('student_dashboard'))
    elif current_user.role == 'parent':
        enfants = get_parent_students()
        if not enfants or bulletin.etudiant_id not in [e.id for e in enfants]:
            flash('Accès refusé.', 'danger')
            return redirect(url_for('dashboard'))
    data = compute_bulletin_data(etudiant, bulletin.semestre)
    return render_template('bulletin.html', etudiant=etudiant, semestre=bulletin.semestre, **data)

@app.route('/bulletins/pdf/<int:bulletin_id>')
@login_required
def bulletin_pdf(bulletin_id):
    bulletin = Bulletin.query.get_or_404(bulletin_id)
    etudiant = bulletin.etudiant
    if current_user.role == 'etudiant':
        if current_user.email != etudiant.email:
            flash('Accès refusé.', 'danger')
            return redirect(url_for('dashboard'))
        has_paid, _, required = student_has_paid_sufficiently(etudiant)
        if not has_paid:
            flash(f"Accès au bulletin PDF restreint : payez {required:.2f} CFA minimum.", 'warning')
            return redirect(url_for('student_dashboard'))
    elif current_user.role == 'parent':
        enfants = get_parent_students()
        if not enfants or bulletin.etudiant_id not in [e.id for e in enfants]:
            flash('Accès refusé.', 'danger')
            return redirect(url_for('dashboard'))
    data = compute_bulletin_data(etudiant, bulletin.semestre)
    has_paid, total_paid, required_payment = student_has_paid_sufficiently(etudiant)
    pdf = render_pdf(
        'bulletin_print.html',
        etudiant=etudiant,
        semestre=bulletin.semestre,
        total_paid=total_paid,
        required_payment=required_payment,
        **data
    )
    if pdf is None:
        flash('Impossible de générer le PDF.', 'danger')
        return redirect(url_for('bulletins'))
    return send_file(pdf, mimetype='application/pdf', download_name=f'bulletin_{etudiant.matricule}_{bulletin.semestre}.pdf')

@app.route('/timetable')
@login_required
def timetable():
    emplois = EmploiDuTemps.query.all()
    return render_template('timetable.html', emplois=emplois)

@app.route('/timetable/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_timetable():
    form = TimetableForm()
    form.classe_id.choices = [(c.id, c.nom_classe) for c in Classe.query.all()]
    form.matiere_id.choices = [(m.id, m.nom_matiere) for m in Matiere.query.all()]
    form.professeur_id.choices = [(p.id, f'{p.nom} {p.prenom}') for p in Professeur.query.all()]
    if form.validate_on_submit():
        emploi = EmploiDuTemps(
            classe_id=form.classe_id.data,
            jour=form.jour.data,
            heure_debut=form.heure_debut.data,
            heure_fin=form.heure_fin.data,
            matiere_id=form.matiere_id.data,
            salle=form.salle.data,
            professeur_id=form.professeur_id.data
        )
        db.session.add(emploi)
        db.session.commit()
        flash('Emploi du temps ajouté.', 'success')
        return redirect(url_for('timetable'))
    return render_template('timetable_form.html', form=form, title='Ajouter un emploi du temps')

@app.route('/rooms')
@login_required
def rooms():
    salles = Salle.query.all()
    return render_template('rooms.html', salles=salles)

@app.route('/rooms/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_room():
    form = SalleForm()
    if form.validate_on_submit():
        salle = Salle(numero=form.numero.data, capacite=form.capacite.data, type_salle=form.type_salle.data)
        db.session.add(salle)
        db.session.commit()
        flash('Salle ajoutée.', 'success')
        return redirect(url_for('rooms'))
    return render_template('room_form.html', form=form, title='Ajouter une salle')

@app.route('/payments')
@login_required
def payments():
    if current_user.role in ['administrateur', 'professeur']:
        paiements = Paiement.query.join(Etudiant).all()
    elif current_user.role == 'etudiant':
        etudiant = Etudiant.query.filter_by(email=current_user.email).first()
        if etudiant is None:
            flash('Aucune fiche étudiant trouvée.', 'warning')
            return redirect(url_for('dashboard'))
        paiements = Paiement.query.filter_by(etudiant_id=etudiant.id).all()
    elif current_user.role == 'parent':
        enfants = get_parent_students()
        if not enfants:
            flash('Aucun enfant trouvé lié à votre compte parent.', 'warning')
            return redirect(url_for('dashboard'))
        enfant_ids = [e.id for e in enfants]
        paiements = Paiement.query.join(Etudiant).filter(Paiement.etudiant_id.in_(enfant_ids)).all()
    else:
        flash('Accès refusé.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('payments.html', paiements=paiements)

@app.route('/export/payments')
@login_required
@roles_required('administrateur')
def export_payments():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['matricule', 'nom', 'prenom', 'montant', 'type_paiement', 'date_paiement'])
    for paiement in Paiement.query.order_by(Paiement.date_paiement.desc()).all():
        etu = paiement.etudiant
        writer.writerow([
            etu.matricule if etu else '',
            etu.nom if etu else '',
            etu.prenom if etu else '',
            paiement.montant,
            paiement.type_paiement,
            paiement.date_paiement
        ])
    mem = BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='paiements.csv')

@app.route('/import/payments', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def import_payments():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('Aucun fichier sélectionné.', 'warning')
            return redirect(url_for('import_payments'))
        content = file.stream.read().decode('utf-8')
        reader = csv.DictReader(StringIO(content))
        imported = 0
        for row in reader:
            matricule = (row.get('matricule') or '').strip()
            if not matricule:
                continue
            etudiant = Etudiant.query.filter_by(matricule=matricule).first()
            if not etudiant:
                continue
            paiement = Paiement(
                etudiant_id=etudiant.id,
                montant=float(row.get('montant') or 0),
                date_paiement=row.get('date_paiement') or '',
                type_paiement=row.get('type_paiement') or 'Inconnu'
            )
            db.session.add(paiement)
            imported += 1
        db.session.commit()
        flash(f'{imported} paiement(s) importé(s).', 'success')
        return redirect(url_for('payments'))
    return render_template('import_payments.html')

@app.route('/payments/add', methods=['GET', 'POST'])
@login_required
@roles_required('administrateur')
def add_payment():
    form = PaiementForm()
    form.etudiant_id.choices = [(e.id, f'{e.matricule} - {e.nom} {e.prenom}') for e in Etudiant.query.all()]
    if form.validate_on_submit():
        paiement = Paiement(
            etudiant_id=form.etudiant_id.data,
            montant=form.montant.data,
            date_paiement=form.date_paiement.data,
            type_paiement=form.type_paiement.data
        )
        db.session.add(paiement)
        db.session.commit()
        flash('Paiement ajouté.', 'success')
        return redirect(url_for('payments'))
    return render_template('payment_form.html', form=form, title='Ajouter un paiement')

@app.route('/reports')
@login_required
@roles_required('administrateur', 'professeur')
def reports():
    stats = {
        'etudiants': Etudiant.query.count(),
        'professeurs': Professeur.query.count(),
        'classes': Classe.query.count(),
        'matieres': Matiere.query.count(),
        'bulletins': Bulletin.query.count(),
        'absences': Absence.query.count()
    }
    return render_template('reports.html', stats=stats)

def model_to_dict(obj, fields):
    return {field: getattr(obj, field) for field in fields}

@app.route('/data-tools')
@login_required
@roles_required('administrateur')
def data_tools():
    return render_template('data_tools.html')

@app.route('/data-tools/export/json')
@login_required
@roles_required('administrateur')
def export_json():
    payload = {
        'etablissement': [model_to_dict(e, ['id', 'nom', 'adresse', 'telephone', 'email', 'logo_path']) for e in EtablissementConfig.query.all()],
        'utilisateurs': [model_to_dict(u, ['id', 'nom', 'email', 'role']) for u in User.query.all()],
        'classes': [model_to_dict(c, ['id', 'nom_classe', 'niveau', 'effectif']) for c in Classe.query.all()],
        'etudiants': [model_to_dict(e, ['id', 'matricule', 'nom', 'prenom', 'date_naissance', 'sexe', 'adresse', 'telephone', 'email', 'classe_id', 'nom_parent', 'email_parent', 'telephone_parent']) for e in Etudiant.query.all()],
        'professeurs': [model_to_dict(p, ['id', 'matricule', 'nom', 'prenom', 'telephone', 'email', 'adresse', 'matiere_id', 'date_recrutement']) for p in Professeur.query.all()],
        'matieres': [model_to_dict(m, ['id', 'code', 'nom_matiere', 'coefficient']) for m in Matiere.query.all()],
        'notes': [model_to_dict(n, ['id', 'etudiant_id', 'matiere_id', 'valeur', 'type_note', 'date_note', 'semestre']) for n in Note.query.all()],
        'absences': [model_to_dict(a, ['id', 'etudiant_id', 'date_absence', 'heure', 'heure_arrivee', 'statut', 'motif', 'justification']) for a in Absence.query.all()],
        'paiements': [model_to_dict(p, ['id', 'etudiant_id', 'montant', 'date_paiement', 'type_paiement']) for p in Paiement.query.all()],
        'mouvements': [model_to_dict(m, ['id', 'etudiant_id', 'agent_id', 'type_mouvement', 'date_mouvement', 'heure_mouvement', 'motif']) for m in MouvementEtudiant.query.all()],
        'messages': [model_to_dict(m, ['id', 'titre', 'contenu', 'destinataire_role', 'etudiant_id']) for m in Message.query.all()],
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    return send_file(BytesIO(data), mimetype='application/json', as_attachment=True, download_name='edu_dem_export.json')

@app.route('/data-tools/export/students.csv')
@login_required
@roles_required('administrateur')
def export_students_csv():
    output = StringIO()
    fields = ['matricule', 'nom', 'prenom', 'date_naissance', 'sexe', 'adresse', 'telephone', 'email', 'classe_id', 'nom_parent', 'email_parent', 'telephone_parent']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for etudiant in Etudiant.query.order_by(Etudiant.nom).all():
        writer.writerow(model_to_dict(etudiant, fields))
    return send_file(BytesIO(output.getvalue().encode('utf-8-sig')), mimetype='text/csv', as_attachment=True, download_name='etudiants.csv')

@app.route('/data-tools/import/students.csv', methods=['POST'])
@login_required
@roles_required('administrateur')
def import_students_csv():
    file = request.files.get('students_csv')
    if not file:
        flash('Sélectionnez un fichier CSV.', 'warning')
        return redirect(url_for('data_tools'))
    content = file.read().decode('utf-8-sig')
    reader = csv.DictReader(StringIO(content))
    imported = 0
    for row in reader:
        matricule = (row.get('matricule') or '').strip()
        if not matricule:
            continue
        etudiant = Etudiant.query.filter_by(matricule=matricule).first()
        if etudiant is None:
            etudiant = Etudiant(matricule=matricule, nom='', prenom='', date_naissance='', sexe='Masculin')
            db.session.add(etudiant)
        for field in ['nom', 'prenom', 'date_naissance', 'sexe', 'adresse', 'telephone', 'email', 'nom_parent', 'email_parent', 'telephone_parent']:
            if field in row:
                setattr(etudiant, field, row.get(field) or '')
        classe_id = row.get('classe_id')
        etudiant.classe_id = int(classe_id) if classe_id else None
        imported += 1
    db.session.commit()
    flash(f'{imported} étudiant(s) importé(s) ou mis à jour.', 'success')
    return redirect(url_for('data_tools'))

if __name__ == '__main__':
    with app.app_context():
        initialize_database()
    app.run(debug=False)
