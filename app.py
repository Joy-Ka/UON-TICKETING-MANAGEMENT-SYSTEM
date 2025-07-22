import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from config import get_config

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
    
    # Load configuration based on environment
    config = get_config()
    app.config.from_object(config)
    
    # Set DATABASE_URL environment variable for MySQL if not already set (local only)
    if not os.environ.get('REPLIT_ENVIRONMENT') and not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "mysql+pymysql://root:Jace102020.@localhost:3307/uon_ticketing_db"
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
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

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Create database tables and initialize data
with app.app_context():
    import models
    db.create_all()
    logging.info("Database tables created successfully")
    
    # Run database migrations for existing tables
    from utils import migrate_database
    migrate_database()
    
    # Initialize default data after tables are created
    from utils import init_default_data
    init_default_data()

import routes  # Import routes to register them with the app
