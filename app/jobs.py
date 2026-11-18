import click

from .extensions import db
from .models.placement import Placement
from .models.user import User


def register(app):
    @app.cli.command("nightly-integrity")
    def nightly_integrity():
        """Re-checks every record against the previous checkpoint. Emails coordinators on a problem."""
        from .services import audit_chain
        from .services.notifications import send_email
        bad = []
        for (sid,) in db.session.query(Placement.student_id).all():
            r = audit_chain.run_check(sid)
            if not r.ok:
                bad.append(f"{db.session.get(User, sid).full_name}: problem found at event {r.problem_seq}")
        click.echo(f"Checked. {len(bad)} problem(s).")
        if bad:
            for c in User.query.filter_by(role="coordinator", status="active"):
                send_email(c.email, "SIWES integrity problem found", "\n".join(bad))

    @app.cli.command("nightly-checkpoint")
    def nightly_checkpoint():
        from .services import audit_chain
        cp = audit_chain.make_checkpoint()
        audit_chain.publish(cp)
        click.echo(f"Checkpoint {cp.digest}")

    @app.cli.command("nightly-flags")
    def nightly_flags():
        from .services import detection
        click.echo(f"{detection.scan(since_days=3)} new flag(s).")

    @app.cli.command("daily-reminders")
    def daily_reminders():
        from .services import reminders
        click.echo(f"{reminders.entry_reminders()} reminder(s) sent.")

    @app.cli.command("weekly-supervisor-reminders")
    def weekly_supervisor_reminders():
        from .services import reminders
        click.echo(f"{reminders.supervisor_reminders()} reminder(s) sent.")

    @app.cli.command("check-published")
    @click.option("--digest", prompt=True)
    def check_published(digest):
        """Confirms a digest from a checkpoint email matches what this server holds."""
        from .services import audit_chain
        click.echo("MATCH" if audit_chain.published_matches(digest) else "NO MATCH")