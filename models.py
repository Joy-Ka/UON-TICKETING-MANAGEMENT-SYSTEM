from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'tech', 'admin'
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    department = db.relationship('Department', backref='users')
    created_tickets = db.relationship('Ticket', foreign_keys='Ticket.created_by_id', backref='creator')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<User {self.username}>'

class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Department {self.name}>'

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(10), nullable=False)  # 'URGENT', 'HIGH', 'MEDIUM', 'LOW'
    status = db.Column(db.String(20), default='OPEN')  # 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'
    category = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    unit = db.Column(db.String(50), nullable=True)  # For SWA departments (USHR, LSHR)
    
    # Foreign keys
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_ids = db.Column(db.Text, nullable=True)  # Store comma-separated IDs for multiple assignments
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    
    @property
    def assigned_techs(self):
        """Get list of assigned technicians"""
        if not self.assigned_to_ids:
            return []
        ids = [int(id.strip()) for id in self.assigned_to_ids.split(',') if id.strip()]
        return User.query.filter(User.id.in_(ids)).all()
    
    @property
    def assignee(self):
        """Get primary assignee for backward compatibility"""
        techs = self.assigned_techs
        return techs[0] if techs else None
    
    @property
    def is_overdue(self):
        """Check if ticket is overdue"""
        if not self.due_date:
            return False
        return datetime.utcnow() > self.due_date and self.status not in ['RESOLVED', 'CLOSED']
    
    @property
    def status_display(self):
        """Display status with overdue indicator"""
        if self.is_overdue:
            return 'EXPIRED'
        elif self.due_date and datetime.utcnow() > (self.due_date - timedelta(days=1)) and self.status not in ['RESOLVED', 'CLOSED']:
            return 'DUE'
        return self.status
    
    # Relationships
    comments = db.relationship('TicketComment', backref='ticket', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='ticket', cascade='all, delete-orphan')
    
    @property
    def priority_color(self):
        colors = {
            'URGENT': 'danger',
            'HIGH': 'warning', 
            'MEDIUM': 'info',
            'LOW': 'success'
        }
        return colors.get(self.priority, 'secondary')
    
    @property
    def status_color(self):
        colors = {
            'OPEN': 'primary',
            'IN_PROGRESS': 'warning',
            'RESOLVED': 'info',
            'CLOSED': 'success'
        }
        return colors.get(self.status, 'secondary')
    
    def __repr__(self):
        return f'<Ticket {self.title}>'

class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)  # Internal notes for tech team
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='comments')
    
    def __repr__(self):
        return f'<TicketComment {self.id}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(20), nullable=False)  # 'EMAIL', 'SMS', 'SYSTEM'
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.title}>'


class TicketAttachment(db.Model):
    __tablename__ = 'ticket_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.String(100), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    upload_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    ticket = db.relationship('Ticket', backref='attachments')
    uploaded_by = db.relationship('User', backref='uploaded_files')
    
    def __repr__(self):
        return f'<TicketAttachment {self.original_filename}>'
