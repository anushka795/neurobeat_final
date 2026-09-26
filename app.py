import os
import logging
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "neurobeat-secret-key-dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

@app.template_filter('format_duration')
def format_duration(seconds):
    """Formats active duration in seconds into 'Xm Ys' or 'Xs' without dropping seconds"""
    if seconds is None:
        return "N/A"
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return "N/A"
    if seconds < 0:
        return "N/A"
    m = seconds // 60
    s = seconds % 60
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"

@app.template_filter('format_timer')
def format_timer(seconds):
    """Formats duration into standard timer string 'MM:SS'"""
    if seconds is None:
        return "00:00"
    try:
        seconds = max(0, int(seconds))
    except (ValueError, TypeError):
        return "00:00"
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///neurobeat.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models  # noqa: F401
    db.create_all()
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE clinician_profiles ADD COLUMN profession VARCHAR(100)"))
            conn.commit()
    except Exception:
        pass
    logging.info("Database tables created successfully")
