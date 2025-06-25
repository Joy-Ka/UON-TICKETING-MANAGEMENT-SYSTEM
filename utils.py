import os
from datetime import datetime, timedelta
from flask import current_app
from flask_mail import Message
from app import mail, db
from models import Notification, User
import logging

def send_email_notification(to_email, subject, body, html_body=None):
    """Send email notification"""
    try:
        msg = Message(
            subject=subject,
            recipients=[to_email],
            body=body,
            html=html_body
        )
        mail.send(msg)
        logging.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

def create_notification(user_id, title, message, ticket_id=None, notification_type='SYSTEM'):
    """Create a system notification"""
    notification = Notification(
        user_id=user_id,
        ticket_id=ticket_id,
        title=title,
        message=message,
        notification_type=notification_type
    )
    db.session.add(notification)
    db.session.commit()
    return notification

def notify_tech_team(ticket):
    """Notify all technical team members about a new ticket"""
    tech_users = User.query.filter(User.role.in_(['tech', 'admin']), User.is_active == True).all()
    
    for user in tech_users:
        # Create system notification
        create_notification(
            user_id=user.id,
            title=f"New Ticket: {ticket.title}",
            message=f"A new {ticket.priority} priority ticket has been created by {ticket.creator.full_name}",
            ticket_id=ticket.id
        )
        
        # Send email notification
        if user.email:
            subject = f"New ICT Ticket - {ticket.priority} Priority"
            body = f"""
            A new ticket has been created and requires attention.
            
            Ticket ID: #{ticket.id}
            Title: {ticket.title}
            Priority: {ticket.priority}
            Created by: {ticket.creator.full_name}
            Department: {ticket.creator.department.name if ticket.creator.department else 'N/A'}
            
            Description:
            {ticket.description}
            
            Please log in to the system to respond to this ticket.
            """
            send_email_notification(user.email, subject, body)

def notify_ticket_update(ticket, message, exclude_user_id=None):
    """Notify relevant users about ticket updates"""
    users_to_notify = []
    
    # Always notify the ticket creator
    if ticket.creator.id != exclude_user_id:
        users_to_notify.append(ticket.creator)
    
    # Notify assigned technician
    if ticket.assignee and ticket.assignee.id != exclude_user_id:
        users_to_notify.append(ticket.assignee)
    
    for user in users_to_notify:
        create_notification(
            user_id=user.id,
            title=f"Ticket Update: {ticket.title}",
            message=message,
            ticket_id=ticket.id
        )
        
        # Send email notification
        if user.email:
            subject = f"Ticket Update - #{ticket.id}"
            send_email_notification(user.email, subject, message)

def get_ticket_stats():
    """Get ticket statistics for dashboard"""
    from models import Ticket
    
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter_by(status='OPEN').count()
    in_progress_tickets = Ticket.query.filter_by(status='IN_PROGRESS').count()
    resolved_tickets = Ticket.query.filter_by(status='RESOLVED').count()
    closed_tickets = Ticket.query.filter_by(status='CLOSED').count()
    
    urgent_tickets = Ticket.query.filter_by(priority='URGENT').filter(
        Ticket.status.in_(['OPEN', 'IN_PROGRESS'])
    ).count()
    
    return type('Stats', (), {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'closed_tickets': closed_tickets,
        'urgent_tickets': urgent_tickets,
        'total': total_tickets,
        'open': open_tickets,
        'in_progress': in_progress_tickets,
        'resolved': resolved_tickets,
        'closed': closed_tickets,
        'urgent': urgent_tickets
    })()

def get_monthly_ticket_data():
    """Get monthly ticket data for reports"""
    from models import Ticket
    from sqlalchemy import func, extract
    
    current_year = datetime.now().year
    
    monthly_data = db.session.query(
        extract('month', Ticket.created_at).label('month'),
        func.count(Ticket.id).label('count')
    ).filter(
        extract('year', Ticket.created_at) == current_year
    ).group_by(
        extract('month', Ticket.created_at)
    ).all()
    
    # Convert to dictionary with month names
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    data = {months[i]: 0 for i in range(12)}
    for month, count in monthly_data:
        data[months[int(month) - 1]] = count
    
    return data

def init_default_data():
    """Initialize default departments and admin user"""
    from models import Department, User
    
    # Create default departments
    departments_data = [
        {'name': 'Student Management Unit', 'code': 'SMU'},
        {'name': 'Student Welfare Affairs', 'code': 'SWA'},
        {'name': 'University Health Services', 'code': 'UHS'},
        {'name': 'Communication and Customer Unit', 'code': 'CCU'},
        {'name': 'Confucius Institute', 'code': 'CONFUCIUS'}
    ]
    
    for dept_data in departments_data:
        if not Department.query.filter_by(code=dept_data['code']).first():
            department = Department(**dept_data)
            db.session.add(department)
    
    # Create default admin user
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            email='admin@icttickets.com',
            first_name='System',
            last_name='Administrator',
            role='admin'
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
    
    db.session.commit()
    logging.info("Default data initialized")
