from flask import Flask


def create_app():
    app = Flask(__name__)

    app.config.from_object("config.Config")

    from app.routes.main import main_bp
    from app.routes.patients import patients_bp
    from app.routes.doctors import doctors_bp
    from app.routes.appointments import appointments_bp
    from app.routes.departments import departments_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(doctors_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(departments_bp)

    return app
