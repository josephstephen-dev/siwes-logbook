import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, body):
    """Returns True if sent. A failure never crashes the page; it is logged."""
    cfg = current_app.config
    if cfg.get("MAIL_BACKEND") == "console":
        print(f"\n===== EMAIL to {to} =====\nSubject: {subject}\n\n{body}\n===== end =====\n",
              flush=True)
        return True
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_FROM"], to, subject
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        port = cfg["MAIL_PORT"]
        server = (smtplib.SMTP_SSL(cfg["MAIL_HOST"], port, timeout=10, context=ctx)
                  if port == 465 else smtplib.SMTP(cfg["MAIL_HOST"], port, timeout=10))
        with server:
            if port != 465:
                server.starttls(context=ctx)
            if cfg["MAIL_USER"]:
                server.login(cfg["MAIL_USER"], cfg["MAIL_PASSWORD"])
            server.send_message(msg)
        return True
    except Exception:
        current_app.logger.exception("Email to %s failed", to)
        return False


def send_verify_email(user):
    from .invitations import public_url
    from .tokens import make_verify_token
    link = public_url("invite.verify_email", token=make_verify_token(user))
    hours = current_app.config["VERIFY_TTL_HOURS"]
    return send_email(
        user.email, "Confirm your SIWES Logbook email",
        f"Hello {user.full_name.split()[0]},\n\n"
        f"Open this link to confirm your email and finish creating your account "
        f"(valid for {hours} hours):\n{link}\n\n"
        "If you did not sign up, ignore this message.")


def send_reset_email(user):
    from .invitations import public_url
    from .tokens import make_reset_token
    link = public_url("auth.reset_password", token=make_reset_token(user))
    minutes = current_app.config["RESET_TTL_MINUTES"]
    return send_email(
        user.email, "Reset your SIWES Logbook password",
        f"Hello {user.full_name.split()[0]},\n\n"
        f"Open this link to choose a new password (valid for {minutes} minutes):\n{link}\n\n"
        "If you did not ask for this, ignore this message.")