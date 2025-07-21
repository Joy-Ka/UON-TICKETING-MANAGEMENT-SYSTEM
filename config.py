import os
from urllib.parse import urlparse

class Config:
    """Base configuration with common settings"""
    SECRET_KEY = os.environ.get("SESSION_SECRET") or "dev_secret_key_change_me"

    # Database configuration
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Mail configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@icttickets.com')

    # SendGrid configuration
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

    # Clickatell SMS configuration
    CLICKATELL_API_KEY = 'n9rqL_BMSIWl_BxogvsAwA=='
    CLICKATELL_BASE_URL = 'https://platform.clickatell.com'

class LocalConfig(Config):
    """Local development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:Jace102020.@localhost:3307/uon_ticketing_db"

class ReplitConfig(Config):
    """Replit environment configuration"""
    DEBUG = True
    # Use PostgreSQL for Replit environment (Replit's native database)
    # Falls back to SQLite if no DATABASE_URL is provided
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///uon_ticketing.db'
    # Bind to 0.0.0.0 for Replit accessibility
    HOST = '0.0.0.0'
    PORT = 5000

    # PostgreSQL specific configuration for better performance
    if os.environ.get('DATABASE_URL') and 'postgresql' in os.environ.get('DATABASE_URL', ''):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_recycle": 300,
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20
        }

def get_config():
    """Return appropriate configuration based on environment"""
    if os.environ.get('REPLIT_ENVIRONMENT'):
        return ReplitConfig()
    else:
        return LocalConfig()