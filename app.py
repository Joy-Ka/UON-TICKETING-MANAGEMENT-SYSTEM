import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
mail = Mail()

def create_app():
    app = Flask(__name__)
    
    # Set DATABASE_URL environment variable for MySQL if not already set
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "mysql+pymysql://root:Jace102020.@localhost:3307/uon_ticketing_db"
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET") or "dev_secret_key_change_me"
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    
    # Database configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Mail configuration
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', '587'))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@icttickets.com')

    # Africa's Talking configuration
    app.config['AFRICASTALKING_USERNAME'] = 'ticketingapp'
    app.config['AFRICASTALKING_API_KEY'] = 'atsk_b6f75c0af4997ba88e976a65c7442df9da5766b7f5e9054ebab41813d5f74078a994e369'

    # Twilio SMS configuration
    import base64
    # Securely decode credentials stored as base64 encoded environment variables
    encoded_sid = os.environ.get('TWILIO_ACCOUNT_SID_ENC')
    encoded_token = os.environ.get('TWILIO_AUTH_TOKEN_ENC')
    twilio_phone = os.environ.get('TWILIO_PHONE_NUMBER', '+1234567890')

    if encoded_sid and encoded_token:
        try:
            decoded_sid = base64.b64decode(encoded_sid).decode('utf-8')
            decoded_token = base64.b64decode(encoded_token).decode('utf-8')
            app.config['TWILIO_ACCOUNT_SID'] = decoded_sid
            app.config['TWILIO_AUTH_TOKEN'] = decoded_token
        except Exception as e:
            app.config['TWILIO_ACCOUNT_SID'] = None
            app.config['TWILIO_AUTH_TOKEN'] = None
            import logging
            logging.error(f"Failed to decode Twilio credentials: {e}")
    else:
        # Fallback to plain environment variables if encoded not set
        app.config['TWILIO_ACCOUNT_SID'] = os.environ.get('TWILIO_ACCOUNT_SID')
        app.config['TWILIO_AUTH_TOKEN'] = os.environ.get('TWILIO_AUTH_TOKEN')

    app.config['TWILIO_PHONE_NUMBER'] = twilio_phone
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Login manager configuration
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Add custom Jinja2 filters
    def nl2br(value):
        """Convert newlines to HTML line breaks"""
        if not value:
            return value
        return value.replace('\n', '<br>\n')
    
    app.jinja_env.filters['nl2br'] = nl2br
    
    # Add tojsonfilter for JavaScript data
    import json
    def tojsonfilter(obj):
        return json.dumps(obj)
    
    app.jinja_env.filters['tojsonfilter'] = tojsonfilter
    
    return app

# Create app instance
app = create_app()

import routes  # Import routes to register them with the app

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    import models
    db.create_all()
    logging.info("Database tables created successfully")
