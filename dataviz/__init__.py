"""DataViz Dash application factory, created by Naman Sinha."""

__author__ = "Naman Sinha"
__version__ = "0.2.0"

from flask import Flask, jsonify
from pymongo.errors import PyMongoError

from .admin import bp as admin_bp
from .auth import bp as auth_bp
from .config import Config
from .database import init_database
from .routes import bp


def create_app(config_overrides=None):
    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates",
    )
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    init_database(app)
    app.register_blueprint(bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(413)
    def file_too_large(_error):
        max_mb = app.config["MAX_UPLOAD_MB"]
        return jsonify(error=f"File is too large. Maximum size is {max_mb} MB."), 413

    @app.errorhandler(PyMongoError)
    def database_error(error):
        app.logger.exception("MongoDB operation failed", exc_info=error)
        return jsonify(
            error="The database is unavailable. Check your MongoDB connection."
        ), 503

    return app
