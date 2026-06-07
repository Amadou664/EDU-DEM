from io import BytesIO
import smtplib
import json
import base64
from email.message import EmailMessage
from flask import current_app
from flask import render_template
from models import EtablissementConfig

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

try:
    import qrcode
except ImportError:
    qrcode = None


def render_pdf(template_name, **context):
    if pisa is None:
        return None
    html = render_template(template_name, **context)
    output = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=output)
    if pisa_status.err:
        return None
    output.seek(0)
    return output


def send_email(to_email, subject, body, attachment_bytes=None, attachment_filename=None):
    if not to_email:
        return False, 'Adresse email du parent manquante.'

    server = current_app.config.get('MAIL_SERVER')
    port = current_app.config.get('MAIL_PORT', 587)
    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    if not server:
        settings = EtablissementConfig.query.first()
        if settings:
            server = server or settings.mail_server
            port = port or settings.mail_port or 587
            username = username or settings.mail_username
            password = password or settings.mail_password
            use_tls = settings.mail_use_tls if settings.mail_use_tls is not None else use_tls
            sender = sender or settings.mail_default_sender

    if not server or not sender:
        return False, 'Serveur email non configuré. Vérifiez les paramètres SMTP.'

    if isinstance(use_tls, str):
        use_tls = use_tls.lower() in ('true', '1', 'yes', 'on')

    message = EmailMessage()
    message['From'] = sender
    message['To'] = to_email
    message['Subject'] = subject
    message.set_content(body)

    if attachment_bytes is not None and attachment_filename:
        maintype = 'application'
        subtype = 'pdf' if attachment_filename.lower().endswith('.pdf') else 'octet-stream'
        message.add_attachment(attachment_bytes, maintype=maintype, subtype=subtype, filename=attachment_filename)

    try:
        with smtplib.SMTP(server, int(port), timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True, 'Notification envoyée.'
    except Exception as exc:
        return False, f'Erreur email: {exc}'


def make_qr_data_uri(payload):
    if qrcode is None:
        return None
    image = qrcode.make(json.dumps(payload, ensure_ascii=False))
    output = BytesIO()
    image.save(output, format='PNG')
    encoded = base64.b64encode(output.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'
