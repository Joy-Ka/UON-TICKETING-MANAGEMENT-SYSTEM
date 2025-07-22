import os
from datetime import datetime, timedelta
from flask import current_app
from flask_mail import Message
from app import mail, db
from models import Notification, User
from sqlalchemy import text
import logging


import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def send_email_notification(to_email, subject, body, html_body=None):
    """Send email notification using SendGrid API"""
    try:
        message = Mail(
            from_email=os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@icttickets.com'),
            to_emails=to_email,
            subject=subject,
            plain_text_content=body,
            html_content=html_body
        )
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        if response.status_code in [200, 202]:
            logging.info(f"Email sent successfully to {to_email}")
            return True
        else:
            logging.error(f"Failed to send email to {to_email}: Status code {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Exception during email sending to {to_email}: {str(e)}")
        return False

import os
import requests
from datetime import datetime, timedelta
from flask import current_app
from flask_mail import Message
from app import mail, db
from models import Notification, User, Ticket, Department
import logging
import os
from twilio.rest import Client


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

def send_sms_notification(to_phone, message):
    """Send SMS notification using Clickatell One API"""
    try:
        api_key = current_app.config.get('CLICKATELL_API_KEY')
        base_url = current_app.config.get('CLICKATELL_BASE_URL', 'https://platform.clickatell.com')
        if not api_key:
            logging.error("Clickatell API key is missing")
            return False

        # Sanitize phone number: remove spaces and format to international if missing country code
        to_phone = to_phone.replace(" ", "")
        if to_phone.startswith('0'):
            to_phone = '+254' + to_phone[1:]

        url = f"{base_url}/v1/message"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            "content": message,
            "to": [to_phone]
        }

        response = requests.post(url, json=payload, headers=headers)
        logging.debug(f"Clickatell response status: {response.status_code}")
        logging.debug(f"Clickatell response body: {response.text}")

        if response.status_code in [200, 202]:
            try:
                resp_json = response.json()
                if 'messages' in resp_json:
                    for msg in resp_json['messages']:
                        status = msg.get('status')
                        if status and status != '0':
                            logging.warning(f"Message to {to_phone} returned status code {status}")
            except Exception as e:
                logging.error(f"Error parsing Clickatell response JSON: {e}")
            logging.info(f"SMS sent successfully to {to_phone}")
            return True
        else:
            logging.error(f"Failed to send SMS to {to_phone}: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logging.error(f"Exception during SMS sending to {to_phone}: {str(e)}")
        return False

def send_sms(phone_number, message):
    """Send SMS notification using Twilio"""
    try:
        twilio_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        twilio_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        twilio_phone = current_app.config.get('TWILIO_PHONE_NUMBER')

        if not all([twilio_sid, twilio_token, twilio_phone]):
            print("Twilio credentials not configured - SMS not sent")
            return False

        client = Client(twilio_sid, twilio_token)

        # Format phone number (add country code if not present)
        if phone_number and not phone_number.startswith('+'):
            phone_number = '+254' + phone_number.lstrip('0')  # Kenya country code

        message = client.messages.create(
            body=message,
            from_=twilio_phone,
            to=phone_number
        )
        print(f"SMS sent successfully: {message.sid}")
        return True
    except Exception as e:
        print(f"Failed to send SMS: {str(e)}")
        return False

def create_notification(user_id, title, message, ticket_id=None, notification_type='SYSTEM'):
    """Create a new notification for a user"""
    notification = Notification(
        user_id=user_id,
        ticket_id=ticket_id,
        title=title,
        message=message,
        notification_type=notification_type
    )
    db.session.add(notification)

    # Send SMS if notification type is SMS and user has phone number
    if notification_type == 'SMS':
        user = User.query.get(user_id)
        if user and user.phone:
            sms_sent = send_sms(user.phone, message)
            if sms_sent:
                notification.sent_at = datetime.utcnow()

    db.session.commit()
    return notification

def notify_tech_team(ticket):
    """Notify only admin users about a new ticket - they will assign it to tech team"""
    tech_users = User.query.filter_by(role='admin', is_active=True).all()

    for user in tech_users:
        # Create system notification
        create_notification(
            user_id=user.id,
            title=f"New Ticket: {ticket.title}",
            message=f"A new {ticket.priority} priority ticket has been created by {ticket.creator.full_name}",
            ticket_id=ticket.id,
            notification_type='SYSTEM'
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
            create_notification(
                user_id=user.id,
                title=subject,
                message=body,
                ticket_id=ticket.id,
                notification_type='EMAIL'
            )

        # Send SMS notification
        if user.phone:
            sms_message = f"New ticket #{ticket.id} ({ticket.title}) requires your attention."
            create_notification(
                user_id=user.id,
                title=f"New Ticket Notification",
                message=sms_message,
                ticket_id=ticket.id,
                notification_type='SMS'
            )

def notify_ticket_update(ticket, message, exclude_user_id=None):
    """Notify relevant users about ticket updates"""
    users_to_notify = []

    # Always notify the ticket creator
    if ticket.creator.id != exclude_user_id:
        users_to_notify.append(ticket.creator)

    # Notify assigned technicians
    if ticket.assigned_to_ids:
        assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
        for tech_id in assigned_ids:
            if tech_id != exclude_user_id:
                user = User.query.get(tech_id)
                if user:  # Ensure the user exists
                    create_notification(
                        user_id=tech_id,
                        title=f"Ticket Update: {ticket.title}",
                        message=message,
                        ticket_id=ticket.id,
                        notification_type='SYSTEM'
                    )

                     # Send email notification
                    if user.email:
                        subject = f"Ticket Update - #{ticket.id}"
                        create_notification(
                            user_id=user.id,
                            title=subject,
                            message=message,
                            ticket_id=ticket.id,
                            notification_type='EMAIL'
                        )

                    # Send SMS notification
                    if user.phone:
                        create_notification(
                            user_id=user.id,
                            title=f"Ticket Update Notification",
                            message=message,
                            ticket_id=ticket.id,
                            notification_type='SMS'
                        )

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

def migrate_database():
    """Add missing columns to existing database tables"""
    try:
        # Use text() for raw SQL execution with SQLAlchemy 2.x
        from sqlalchemy import text

        # Check if location and unit columns exist in tickets table
        with db.engine.connect() as connection:
            result = connection.execute(text("PRAGMA table_info(tickets)"))
            columns = [row[1] for row in result]

            if 'location' not in columns:
                connection.execute(text("ALTER TABLE tickets ADD COLUMN location VARCHAR(100)"))
                connection.commit()
                logging.info("Added location column to tickets table")

            if 'unit' not in columns:
                connection.execute(text("ALTER TABLE tickets ADD COLUMN unit VARCHAR(50)"))
                connection.commit()
                logging.info("Added unit column to tickets table")

            if 'due_date' not in columns:
                connection.execute(text("ALTER TABLE tickets ADD COLUMN due_date DATETIME"))
                connection.commit()
                logging.info("Added due_date column to tickets table")

            # Check if assigned_to_ids column exists (replacing assigned_to_id)
            if 'assigned_to_ids' not in columns:
                connection.execute(text("ALTER TABLE tickets ADD COLUMN assigned_to_ids TEXT"))
                connection.commit()
                logging.info("Added assigned_to_ids column to tickets table")

                # Migrate data from assigned_to_id to assigned_to_ids if assigned_to_id exists
                if 'assigned_to_id' in columns:
                    connection.execute(text("""
                        UPDATE tickets 
                        SET assigned_to_ids = CAST(assigned_to_id AS TEXT) 
                        WHERE assigned_to_id IS NOT NULL
                    """))
                    connection.commit()
                    logging.info("Migrated assigned_to_id data to assigned_to_ids")

    except Exception as e:
        logging.error(f"Database migration error: {e}")

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