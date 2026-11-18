def register_blueprints(app):
    from .auth import bp as auth_bp
    from .invite import bp as invite_bp
    from .student import bp as student_bp
    from .supervisor import bp as supervisor_bp
    from .coordinator import bp as coordinator_bp
    from .setup import bp as setup_bp
    from .files import bp as files_bp
    from .verify import bp as verify_bp
    from .meta import bp as meta_bp

    app.register_blueprint(files_bp, url_prefix="/files")
    app.register_blueprint(setup_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(invite_bp, url_prefix="/join")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(supervisor_bp, url_prefix="/supervisor")
    app.register_blueprint(coordinator_bp, url_prefix="/coordinator")
    app.register_blueprint(verify_bp, url_prefix="/v")
    app.register_blueprint(meta_bp)
    # Later: verify