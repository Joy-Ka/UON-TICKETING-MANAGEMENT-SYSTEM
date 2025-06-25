from flask import render_template, redirect, url_for, flash, request, jsonify, abort, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import uuid
from app import app, db
import models
from models import User, Ticket, Department, TicketComment, Notification, TicketAttachment
from forms import LoginForm, TicketForm, CommentForm, UserForm, AssignTicketForm, UpdateTicketStatusForm, RegistrationForm, TechRegistrationForm
from utils import notify_tech_team, notify_ticket_update, get_ticket_stats, get_monthly_ticket_data, init_default_data
import logging

# Initialize default data on first run
with app.app_context():
    init_default_data()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/register')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('register_select.html')

@app.route('/register/department', methods=['GET', 'POST'])
def register_department():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username or email already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register_department.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email address already registered. Please use a different email.', 'danger')
            return render_template('register_department.html', form=form)
        
        # Create new department user
        dept_id = form.department_id.data if form.department_id.data != 0 else None
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='user',
            department_id=dept_id
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash(f'Registration successful! Welcome {user.full_name}. You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_department.html', form=form)

@app.route('/register/tech', methods=['GET', 'POST'])
def register_tech():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = TechRegistrationForm()
    if form.validate_on_submit():
        # Check if username or email already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register_tech.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email address already registered. Please use a different email.', 'danger')
            return render_template('register_tech.html', form=form)
        
        # Create new technical staff user (needs admin approval)
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='tech',
            is_active=False  # Requires admin approval
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        # Notify administrators about new tech registration
        admin_users = User.query.filter_by(role='admin', is_active=True).all()
        for admin in admin_users:
            from utils import create_notification
            create_notification(
                user_id=admin.id,
                title='New Technical Staff Registration',
                message=f'{user.full_name} ({form.position.data}) has registered as technical staff and is awaiting approval.'
            )
        
        flash('Registration submitted successfully! Your account is pending administrator approval. You will be notified via email once approved.', 'info')
        return redirect(url_for('login'))
    
    return render_template('register_tech.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_ticket_stats()
    
    if current_user.role == 'admin':
        # Admin dashboard
        recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()
        unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return render_template('dashboard_admin.html', 
                             stats=stats, 
                             recent_tickets=recent_tickets,
                             unread_notifications=unread_notifications,
                             User=User, Ticket=Ticket, Department=Department)
    
    elif current_user.role == 'tech':
        # Technical staff dashboard
        my_tickets = Ticket.query.filter_by(assigned_to_id=current_user.id).all()
        unassigned_tickets = Ticket.query.filter_by(assigned_to_id=None, status='OPEN').all()
        unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return render_template('dashboard_tech.html',
                             stats=stats,
                             my_tickets=my_tickets,
                             unassigned_tickets=unassigned_tickets,
                             unread_notifications=unread_notifications)
    
    else:
        # Department user dashboard
        my_tickets = Ticket.query.filter_by(created_by_id=current_user.id).all()
        unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return render_template('dashboard_user.html',
                             my_tickets=my_tickets,
                             unread_notifications=unread_notifications)

@app.route('/ticket/create', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if current_user.role not in ['user', 'admin']:
        flash('You do not have permission to create tickets', 'danger')
        return redirect(url_for('dashboard'))
    
    form = TicketForm()
    if form.validate_on_submit():
        ticket = Ticket(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            category=form.category.data,
            created_by_id=current_user.id
        )
        db.session.add(ticket)
        db.session.commit()
        
        # Handle file attachments
        if form.attachments.data:
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in form.attachments.data:
                if file and file.filename:
                    # Generate unique filename
                    file_ext = os.path.splitext(file.filename)[1]
                    unique_filename = f"{uuid.uuid4()}{file_ext}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    
                    # Save file
                    file.save(file_path)
                    
                    # Create attachment record
                    attachment = TicketAttachment(
                        ticket_id=ticket.id,
                        filename=unique_filename,
                        original_filename=file.filename,
                        file_size=os.path.getsize(file_path),
                        file_type=file.content_type or 'application/octet-stream',
                        uploaded_by_id=current_user.id,
                        upload_path=file_path
                    )
                    db.session.add(attachment)
            
            db.session.commit()
        
        # Notify technical team
        notify_tech_team(ticket)
        
        flash('Ticket created successfully!', 'success')
        return redirect(url_for('view_ticket', ticket_id=ticket.id))
    
    return render_template('ticket_create.html', form=form)

@app.route('/ticket/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Check permissions
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    
    comments = TicketComment.query.filter_by(ticket_id=ticket_id).order_by(TicketComment.created_at.asc()).all()
    
    # Filter internal comments for non-tech users
    if current_user.role == 'user':
        comments = [c for c in comments if not c.is_internal]
    
    comment_form = CommentForm()
    assign_form = AssignTicketForm()
    status_form = UpdateTicketStatusForm()
    status_form.status.data = ticket.status
    
    return render_template('ticket_view.html',
                         ticket=ticket,
                         comments=comments,
                         comment_form=comment_form,
                         assign_form=assign_form,
                         status_form=status_form)

@app.route('/ticket/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Check permissions
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    
    form = CommentForm()
    if form.validate_on_submit():
        comment = TicketComment(
            ticket_id=ticket_id,
            user_id=current_user.id,
            comment=form.comment.data,
            is_internal=form.is_internal.data if current_user.role in ['tech', 'admin'] else False
        )
        db.session.add(comment)
        db.session.commit()
        
        # Notify relevant users
        message = f"{current_user.full_name} added a comment to ticket #{ticket.id}"
        notify_ticket_update(ticket, message, exclude_user_id=current_user.id)
        
        flash('Comment added successfully!', 'success')
    
    return redirect(url_for('view_ticket', ticket_id=ticket_id))

@app.route('/ticket/<int:ticket_id>/assign', methods=['POST'])
@login_required
def assign_ticket(ticket_id):
    if current_user.role not in ['tech', 'admin']:
        abort(403)
    
    ticket = Ticket.query.get_or_404(ticket_id)
    form = AssignTicketForm()
    
    if form.validate_on_submit():
        ticket.assigned_to_id = form.assigned_to_id.data
        if ticket.status == 'OPEN':
            ticket.status = 'IN_PROGRESS'
        db.session.commit()
        
        # Notify assigned user and ticket creator
        assignee = User.query.get(form.assigned_to_id.data)
        message = f"Ticket #{ticket.id} has been assigned to {assignee.full_name}"
        notify_ticket_update(ticket, message, exclude_user_id=current_user.id)
        
        flash(f'Ticket assigned to {assignee.full_name}', 'success')
    
    return redirect(url_for('view_ticket', ticket_id=ticket_id))

@app.route('/ticket/<int:ticket_id>/status', methods=['POST'])
@login_required
def update_ticket_status(ticket_id):
    if current_user.role not in ['tech', 'admin']:
        abort(403)
    
    ticket = Ticket.query.get_or_404(ticket_id)
    form = UpdateTicketStatusForm()
    
    if form.validate_on_submit():
        old_status = ticket.status
        ticket.status = form.status.data
        
        if form.status.data == 'RESOLVED' and old_status != 'RESOLVED':
            ticket.resolved_at = datetime.utcnow()
        elif form.status.data == 'CLOSED' and old_status != 'CLOSED':
            ticket.closed_at = datetime.utcnow()
        
        db.session.commit()
        
        # Notify relevant users
        message = f"Ticket #{ticket.id} status updated from {old_status} to {ticket.status}"
        notify_ticket_update(ticket, message, exclude_user_id=current_user.id)
        
        flash('Ticket status updated successfully!', 'success')
    
    return redirect(url_for('view_ticket', ticket_id=ticket_id))

@app.route('/ticket/<int:ticket_id>/take')
@login_required
def take_ticket(ticket_id):
    if current_user.role not in ['tech', 'admin']:
        abort(403)
    
    ticket = Ticket.query.get_or_404(ticket_id)
    
    if ticket.assigned_to_id is None:
        ticket.assigned_to_id = current_user.id
        if ticket.status == 'OPEN':
            ticket.status = 'IN_PROGRESS'
        db.session.commit()
        
        # Notify ticket creator
        message = f"{current_user.full_name} has taken ownership of ticket #{ticket.id}"
        notify_ticket_update(ticket, message, exclude_user_id=current_user.id)
        
        flash('Ticket assigned to you successfully!', 'success')
    else:
        flash('Ticket is already assigned to someone else', 'warning')
    
    return redirect(url_for('view_ticket', ticket_id=ticket_id))

@app.route('/tickets')
@login_required
def list_tickets():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    
    query = Ticket.query
    
    # Apply role-based filtering
    if current_user.role == 'user':
        query = query.filter_by(created_by_id=current_user.id)
    elif current_user.role == 'tech':
        # Show assigned tickets and unassigned tickets
        query = query.filter(
            (Ticket.assigned_to_id == current_user.id) |
            (Ticket.assigned_to_id == None)
        )
    
    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    
    tickets = query.order_by(Ticket.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('ticket_list.html', tickets=tickets)

@app.route('/users')
@login_required
def list_users():
    if current_user.role != 'admin':
        abort(403)
    
    users = User.query.all()
    return render_template('user_management.html', users=users, User=User, Department=Department)

@app.route('/user/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        abort(403)
    
    form = UserForm()
    if form.validate_on_submit():
        # Check if username or email already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return render_template('user_management.html', form=form, edit_mode=False, 
                                 users=User.query.all(), User=User, Department=Department)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already exists', 'danger')
            return render_template('user_management.html', form=form, edit_mode=False, 
                                 users=User.query.all(), User=User, Department=Department)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            phone=form.phone.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=form.role.data,
            department_id=form.department_id.data if form.department_id.data > 0 else None
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {user.username} created successfully!', 'success')
        return redirect(url_for('list_users'))
    
    users = User.query.all()
    return render_template('user_management.html', form=form, users=users, edit_mode=False, 
                         User=User, Department=Department)

@app.route('/user/<int:user_id>/toggle')
@login_required
def toggle_user_status(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('Cannot deactivate admin user', 'danger')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.username} {status} successfully!', 'success')
    
    return redirect(url_for('list_users'))

@app.route('/reports')
@login_required
def reports():
    if current_user.role not in ['admin', 'tech']:
        abort(403)
    
    stats = get_ticket_stats()
    monthly_data = get_monthly_ticket_data()
    
    return render_template('reports.html', stats=stats, monthly_data=monthly_data, 
                         User=User, Ticket=Ticket, Department=Department, models=models)

@app.route('/reports/print')
@login_required
def print_reports():
    if current_user.role not in ['admin', 'tech']:
        abort(403)
    
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Get report parameters
        report_type = request.args.get('type', 'weekly')  # daily, weekly, monthly
        
        # Calculate date range
        now = datetime.now()
        if report_type == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif report_type == 'weekly':
            start_date = now - timedelta(days=7)
            end_date = now
        else:  # monthly
            start_date = now - timedelta(days=30)
            end_date = now
        
        # Get tickets for the period
        tickets = Ticket.query.filter(
            Ticket.created_at.between(start_date, end_date)
        ).order_by(Ticket.created_at.desc()).all()
        
        # Get statistics
        stats = get_ticket_stats()
        
        # Simple department breakdown without complex joins
        department_stats = []
        departments = Department.query.all()
        
        for dept in departments:
            # Explicit join condition to avoid AmbiguousForeignKeysError
            tickets_for_dept = models.Ticket.query.join(
                models.User, models.Ticket.created_by_id == models.User.id
            ).filter(
                models.User.department_id == dept.id,
                models.Ticket.created_at.between(start_date, end_date)
            )
            
            total = tickets_for_dept.count()
            open_count = tickets_for_dept.filter(models.Ticket.status == 'OPEN').count()
            resolved_count = tickets_for_dept.filter(models.Ticket.status == 'RESOLVED').count()
            closed_count = tickets_for_dept.filter(models.Ticket.status == 'CLOSED').count()
            
            if total > 0:  # Only include departments with tickets
                department_stats.append(type('DeptStat', (), {
                    'department_name': dept.name,
                    'total': total,
                    'open': open_count,
                    'resolved': resolved_count,
                    'closed': closed_count
                })())
        
        # Pass department_stats to template and remove query logic from template
        return render_template('reports_printable.html', 
                             stats=stats, 
                             tickets=tickets,
                             department_stats=department_stats,
                             report_type=report_type,
                             current_date=now)
    except Exception as e:
        print(f"Reports error: {e}")
        flash('Error generating reports. Please try again.', 'danger')
        return redirect(url_for('reports'))



@app.route('/api/notifications/mark_read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        abort(403)
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/notifications')
@login_required
def list_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/admin/approve-tech-users')
@login_required
def approve_tech_users():
    if current_user.role != 'admin':
        abort(403)
    
    pending_users = User.query.filter_by(role='tech', is_active=False).all()
    return render_template('approve_tech_users.html', pending_users=pending_users)

@app.route('/admin/approve-tech-user/<int:user_id>', methods=['POST'])
@login_required
def approve_tech_user(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    if user.role == 'tech' and not user.is_active:
        user.is_active = True
        db.session.commit()
        
        # Create notification for approved user
        from utils import create_notification
        create_notification(
            user_id=user.id,
            title='Account Approved',
            message='Your technical staff account has been approved. You can now log in and access the system.'
        )
        
        flash(f'Technical staff {user.full_name} has been approved successfully!', 'success')
    else:
        flash('Invalid user or user is already active.', 'danger')
    
    return redirect(url_for('approve_tech_users'))

@app.route('/admin/reject-tech-user/<int:user_id>', methods=['POST'])
@login_required
def reject_tech_user(user_id):
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    if user.role == 'tech' and not user.is_active:
        # Delete the user application
        db.session.delete(user)
        db.session.commit()
        
        flash(f'Technical staff application for {user.full_name} has been rejected and removed.', 'info')
    else:
        flash('Invalid user or user is already active.', 'danger')
    
    return redirect(url_for('approve_tech_users'))

@app.route('/download/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    attachment = TicketAttachment.query.get_or_404(attachment_id)
    ticket = attachment.ticket
    
    # Check permissions - admin, tech, or ticket creator can download
    if current_user.role not in ['admin', 'tech'] and ticket.created_by_id != current_user.id:
        abort(403)
    
    # Check if file exists
    if not os.path.exists(attachment.upload_path):
        flash('File not found.', 'danger')
        return redirect(url_for('view_ticket', ticket_id=ticket.id))
    
    directory = os.path.dirname(attachment.upload_path)
    filename = os.path.basename(attachment.upload_path)
    
    return send_from_directory(directory, filename, as_attachment=True, 
                             download_name=attachment.original_filename)

@app.route('/ticket/<int:ticket_id>/close', methods=['POST'])
@login_required  
def close_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Only ticket creator (department user) can close tickets
    if ticket.created_by_id != current_user.id:
        flash('Only the ticket creator can close this ticket.', 'danger')
        return redirect(url_for('view_ticket', ticket_id=ticket_id))
    
    ticket.status = 'CLOSED'
    ticket.closed_at = datetime.utcnow()
    db.session.commit()
    
    # Notify assignee if exists
    if ticket.assigned_to_id:
        from utils import create_notification
        create_notification(
            user_id=ticket.assigned_to_id,
            title='Ticket Closed',
            message=f'Ticket "{ticket.title}" has been closed by the requester.',
            ticket_id=ticket.id
        )
    
    flash('Ticket closed successfully!', 'success')
    return redirect(url_for('view_ticket', ticket_id=ticket_id))

# Error handlers
@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
