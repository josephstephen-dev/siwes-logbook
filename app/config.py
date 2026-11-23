import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-secret-change-me'
    HMAC_KEY = os.environ.get("HMAC_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessions: idle timeout of 30 minutes (refreshed on each request)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # "Remember me on this device"
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    INVITE_TTL_HOURS = 72
    SIGNIN_LIMIT = "5 per 5 minutes"
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")  # switch to redis:// in production

    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['josephstep486@gmail.com']
    POSTS_PER_PAGE = 3
    LANGUAGES = [ 'en', 'es' ]

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "console")   # console | smtp
    MAIL_HOST = os.environ.get("MAIL_HOST", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USER = os.environ.get("MAIL_USER", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "SIWES Logbook <no-reply@localhost>")
    VERIFY_TTL_HOURS = 48
    RESET_TTL_MINUTES = 60

    SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "")
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
    JOIN_LIMIT = "100 per hour"          # generous: a whole campus can share one IP
    STAFF_LIMIT = "5 per 15 minutes"

    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "")
    MAX_SKETCHES = 6
    VERIFY_LIMIT = "30 per minute"
    ISSUED_DIR = os.environ.get("ISSUED_DIR", "")
    LOG_FILE = os.environ.get("LOG_FILE", "")
    APP_NAME = os.environ.get("APP_NAME", "SIWES Logbook")

    INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "Alex Ekwueme Federal University, Ndufu-Alike, Ikwo")
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "")
    SUPPORT_PHONE = os.environ.get("SUPPORT_PHONE", "")
    SUPPORT_WHATSAPP = os.environ.get("SUPPORT_WHATSAPP", "")      # digits with country code, no +
    DEFAULT_COUNTRY_CODE = os.environ.get("DEFAULT_COUNTRY_CODE", "234")
    CRON_SECRET = os.environ.get("CRON_SECRET", "")

class DevConfig(Config):
    DEBUG = True


class ProdConfig(Config):
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    # serverless: keep the connection pool tiny
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300,
                                 "pool_size": 1, "max_overflow": 2}


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SIGNIN_LIMIT = "1000 per minute"
    JOIN_LIMIT = "1000 per minute"
    STAFF_LIMIT = "1000 per minute"
    SETUP_TOKEN = "test-setup-token"
    MAIL_BACKEND = "console"
    VERIFY_LIMIT = "1000 per minute"

CONFIGS = {"dev": DevConfig, "prod": ProdConfig, "test": TestConfig}