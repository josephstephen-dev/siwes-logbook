import secrets

import click

from .extensions import db
from .models.user import User
from .services.passwords import hash_password


def register(app):
    @app.cli.command("new-setup-token")
    def new_setup_token():
        """Prints a key for claiming a fresh install in the browser."""
        click.echo(f"SETUP_TOKEN={secrets.token_urlsafe(24)}")

    @app.cli.command("reset-coordinator-password")
    @click.option("--email", prompt=True)
    @click.password_option()
    def reset_coordinator_password(email, password):
        """Last resort when no coordinator can sign in. Needs access to the server."""
        user = User.query.filter_by(role="coordinator", email=email.lower()).first()
        if not user:
            raise click.ClickException("No coordinator with that email.")
        user.password_hash = hash_password(password)
        user.status = "active"
        db.session.commit()
        click.echo("Password changed.")

    @app.cli.command("test-email")
    @click.option("--to", prompt=True)
    def test_email(to):
        """Sends one test message so you can check your MAIL_* settings."""
        from .services.notifications import send_email
        ok = send_email(to, "SIWES Logbook test", "If you can read this, email works.")
        click.echo("Sent." if ok else "FAILED. Read the error above and check your MAIL_* settings.")

    @app.cli.command("dev-reset")
    @click.confirmation_option(prompt="This deletes ALL data in the database. Continue?")
    def dev_reset():
        """Development only: wipes every table."""
        if not app.debug:
            raise click.ClickException("Only available in development.")
        db.metadata.reflect(bind=db.engine)
        db.metadata.drop_all(bind=db.engine)
        click.echo("Database wiped. Delete the migrations folder, then run flask db init.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Development only: demo people and logbook data to click through every screen."""
        if not app.debug:
            raise click.ClickException("Only available in development.")
        import random
        from datetime import timedelta

        from .models.placement import Placement
        from .services import approvals, audit_chain, detection, entries, weeks
        from .services.invitations import now

        app.config["MAIL_BACKEND"] = "console"
        if User.query.filter_by(email="amara.demo@example.com").first():
            raise click.ClickException("Demo data already exists. Run flask dev-reset for a clean start.")

        pw = hash_password("Demo-pass-2026")
        words = ("inspected tested cables panel readings register generator workshop welding calibration "
                 "meter safety induction transformer breaker drawings schedule maintenance torque bearing "
                 "lubrication alignment pump motor circuit voltage current report tools bench drill lathe "
                 "procedure checklist fault isolation earthing relay switchgear battery inverter").split()

        def body(seed):
            r = random.Random(seed)
            return "Worked on " + " ".join(r.choice(words) for _ in range(16)) + " under supervision."

        def person(**kw):
            u = User(status="active", password_hash=pw, email_verified_at=now(), **kw)
            db.session.add(u)
            db.session.flush()
            return u

        sup = person(role="supervisor", supervisor_kind="industry", full_name="Chinedu Okafor",
                     email="chinedu.demo@example.com", phone="+2348030000142",
                     company="Northbridge Engineering Ltd.", designation="Maintenance Engineer",
                     verified_at=now())

        def student(name, tag, with_sup=True):
            return person(role="student", full_name=name, matric_number=f"DEMO/2026/{tag}",
                          email=f"{name.split()[0].lower()}.demo@example.com", phone=f"+23480310000{tag}",
                          department="Electrical Engineering", level="300",
                          industry_supervisor_id=sup.id if with_sup else None)

        amara, tobi = student("Amara Okoye", "001"), student("Tobi Balogun", "002")
        zainab, femi = student("Zainab Musa", "003"), student("Femi Adekunle", "004")
        student("Ifeoma Nwosu", "005", with_sup=False)              # no placement on purpose

        real_today = weeks.today
        monday = real_today() - timedelta(days=real_today().weekday())

        def place(st, start, end, company="Northbridge Engineering Ltd."):
            db.session.add(Placement(student_id=st.id, company_name=company,
                                     company_address="18 Foundry Road, Trans-Amadi, Port Harcourt",
                                     school_supervisor="Dr. Kemi Adebayo", start_date=start, end_date=end))
            db.session.commit()

        place(amara, monday - timedelta(days=21), monday - timedelta(days=21) + timedelta(weeks=24))
        place(tobi, monday - timedelta(days=7), monday - timedelta(days=7) + timedelta(weeks=24))
        place(zainab, monday - timedelta(days=14), monday - timedelta(days=9))   # a one-week placement
        place(femi, monday + timedelta(days=28), monday + timedelta(days=28) + timedelta(weeks=24))

        def on_day(d, fn):                 # write an entry "on the day", so it is not marked late
            weeks.today = lambda: d
            try:
                return fn()
            finally:
                weeks.today = real_today

        def fill(st, n, count=6):
            p = st.placement
            for k in range(count):
                d = weeks.week_start(p, n) + timedelta(days=k)
                if d > real_today() or d < p.start_date:
                    continue
                text = body(f"{st.id}-{n}-{k}")
                on_day(d, lambda: entries.record_entry(st, d, text))

        def send(st, n):
            approvals.submit_week(st, weeks.get_week(st, n), st.full_name, True)

        def approve(st, n):
            send(st, n)
            approvals.approve_week(sup, weeks.get_week(st, n), "Good progress this week.",
                                   sup.full_name, sup.designation)

        with app.test_request_context():
            for n in (1, 2):
                fill(amara, n)
                approve(amara, n)
            fill(amara, 3)
            send(amara, 3)
            approvals.return_entry(sup, weeks.get_week(amara, 3),
                                   weeks.week_start(amara.placement, 3) + timedelta(days=3),
                                   "Please add the specific meter readings you recorded.")
            fill(amara, 4, count=3)

            # Tobi's Monday copies Amara's wording on purpose, so the similarity flag has something to find
            p = tobi.placement
            for k in range(6):
                d = weeks.week_start(p, 1) + timedelta(days=k)
                text = (body(f"{amara.id}-1-0") + " and filed the shift report") if k == 0 else body(f"{tobi.id}-1-{k}")
                on_day(d, lambda: entries.record_entry(tobi, d, text))
            send(tobi, 1)

            fill(zainab, 1)
            approve(zainab, 1)

            db.session.commit()
            detection.scan(since_days=3)
            audit_chain.make_checkpoint()
            for st in (amara, tobi, zainab):
                audit_chain.run_check(st.id)

        click.echo("Demo data created. Password for every demo account: Demo-pass-2026")
        click.echo("  Student     amara.demo@example.com  (weeks 1-2 approved, week 3 returned, week 4 in progress)")
        click.echo("  Student     tobi.demo@example.com   (week 1 waiting for approval, one similarity flag)")
        click.echo("  Student     zainab.demo@example.com (one-week placement, fully approved: ready to finalize)")
        click.echo("  Student     femi.demo@example.com   (placement not started)")
        click.echo("  Supervisor  chinedu.demo@example.com (identity confirmed)")

    @app.cli.command("make-icons")
    def make_icons():
        """Creates the app icons (192 and 512 px) in static/img."""
        import os
        from PIL import Image, ImageDraw
        out = os.path.join(app.root_path, "static", "img")
        for size in (192, 512):
            im = Image.new("RGB", (size, size), "#1b5e44")
            d, m = ImageDraw.Draw(im), size // 5
            d.rounded_rectangle([m, m, size - m, size - m], radius=size // 12, outline="white", width=max(4, size // 32))
            for f in (0.42, 0.55):
                y = int(size * f)
                d.line([m + size // 10, y, size - m - size // 10, y], fill="white", width=max(4, size // 40))
            im.save(os.path.join(out, f"icon-{size}.png"))
        click.echo("Icons written to app/static/img/")