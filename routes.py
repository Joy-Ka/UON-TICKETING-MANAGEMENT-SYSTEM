from flask import render_template, redirect, url_for, flash, request, jsonify, abort, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import uuid
from app import app, db
import models
from models import User, Ticket, Department, TicketComment, Notification, TicketAttachment
from forms import LoginForm, TicketForm, CommentForm, UserForm, AssignTicketForm, UpdateTicketStatusForm, RegistrationForm, TechRegistrationForm, ProfileForm, ChangePasswordForm
from utils import notify_tech_team, notify_ticket_update, get_ticket_stats, get_monthly_ticket_data, init_default_data
import logging

# Initialize default data on first run
with app.app_context():
    init_default_data()

from forms import LoginForm

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    return render_template('combined_index.html', form=form)

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
        # Get tickets assigned to current tech user
        my_tickets = []
        for ticket in Ticket.query.filter(Ticket.assigned_to_ids.isnot(None)).all():
            if str(current_user.id) in ticket.assigned_to_ids.split(','):
                my_tickets.append(ticket)
        
        unassigned_tickets = Ticket.query.filter_by(assigned_to_ids=None, status='OPEN').all()
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
    
    # Set location choices based on department
    if current_user.department:
        dept_code = current_user.department.code
        if dept_code == 'SWA':
            form.unit.choices = [('', 'Select Unit'), ('USHR', 'Upper State House Road (USHR)'), ('LSHR', 'Lower State House Road (LSHR)')]
        elif dept_code in ['UHS', 'CONFUCIUS']:
            form.unit.choices = [('', 'N/A')]
        else:
            form.unit.choices = [('', 'N/A')]
    
    if form.validate_on_submit():
        # Set due date to 3 days from creation
        due_date = datetime.utcnow() + timedelta(days=3)
        
        ticket = Ticket(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            category=form.category.data,
            unit=form.unit.data if form.unit.data else None,
            location=form.location.data if form.location.data else None,
            due_date=due_date,
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
    elif current_user.role == 'tech':
        # Tech users can see tickets assigned to them or unassigned tickets
        is_assigned = False
        if ticket.assigned_to_ids:
            assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
            is_assigned = current_user.id in assigned_ids
        is_unassigned = ticket.assigned_to_ids is None
        if not (is_assigned or is_unassigned):
            abort(403)

    comments = TicketComment.query.filter_by(ticket_id=ticket_id).order_by(TicketComment.created_at.asc()).all()

    # Filter internal comments for non-tech users
    if current_user.role == 'user':
        comments = [c for c in comments if not c.is_internal]

    comment_form = CommentForm()
    assign_form = AssignTicketForm()
    
    # Set status form choices based on user role
    if current_user.role == 'tech':
        # Tech staff can only update to In Progress or Resolved
        status_choices = [
            ('IN_PROGRESS', 'In Progress'),
            ('RESOLVED', 'Resolved')
        ]
    else:
        # Admin and ticket creators can use all statuses
        status_choices = [
            ('OPEN', 'Open'),
            ('IN_PROGRESS', 'In Progress'),
            ('RESOLVED', 'Resolved'),
            ('CLOSED', 'Closed')
        ]
    
    status_form = UpdateTicketStatusForm(choices=status_choices)
    status_form.status.data = ticket.status

    # Add csrf_token to context for template
    from flask_wtf.csrf import generate_csrf

    # Pass generate_csrf function to template so csrf_token() works
    return render_template('ticket_view.html',
                         ticket=ticket,
                         comments=comments,
                         comment_form=comment_form,
                         assign_form=assign_form,
                         status_form=status_form,
                         csrf_token=generate_csrf)

@app.route('/ticket/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    # Check permissions
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'tech':
        # Tech users can comment on tickets assigned to them or unassigned tickets
        is_assigned = False
        if ticket.assigned_to_ids:
            assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
            is_assigned = current_user.id in assigned_ids
        is_unassigned = ticket.assigned_to_ids is None
        if not (is_assigned or is_unassigned):
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
    if current_user.role != 'admin':
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)
    form = AssignTicketForm()

    if form.validate_on_submit():
        # Add new assignment to existing assignments
        new_tech_id = form.assigned_to_id.data
        if ticket.assigned_to_ids:
            assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
            if new_tech_id not in assigned_ids:
                assigned_ids.append(new_tech_id)
                ticket.assigned_to_ids = ','.join(map(str, assigned_ids))
        else:
            ticket.assigned_to_ids = str(new_tech_id)
        
        if ticket.status == 'OPEN':
            ticket.status = 'IN_PROGRESS'
        db.session.commit()

        # Notify assigned user and ticket creator
        assignee = User.query.get(new_tech_id)
        message = f"Ticket #{ticket.id} has been assigned to {assignee.full_name}"
        notify_ticket_update(ticket, message, exclude_user_id=current_user.id)

        flash(f'Ticket assigned to {assignee.full_name}', 'success')

    return redirect(url_for('view_ticket', ticket_id=ticket_id))

@app.route('/ticket/<int:ticket_id>/status', methods=['POST'])
@login_required
def update_ticket_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Check permissions
    is_admin = current_user.role == 'admin'
    is_creator = ticket.created_by_id == current_user.id
    is_assigned_tech = False
    
    if current_user.role == 'tech' and ticket.assigned_to_ids:
        assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
        is_assigned_tech = current_user.id in assigned_ids
    
    # Allow access for admin, creator, or assigned tech
    if not (is_admin or is_creator or is_assigned_tech):
        abort(403)

    form = UpdateTicketStatusForm()

    if form.validate_on_submit():
        old_status = ticket.status
        new_status = form.status.data
        
        # Restrict tech staff from closing tickets - only creators and admins can close
        if current_user.role == 'tech' and new_status == 'CLOSED':
            flash('Only ticket creators can close tickets.', 'danger')
            return redirect(url_for('view_ticket', ticket_id=ticket_id))
        
        ticket.status = new_status

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

    # Check if current user is assigned to the ticket
    is_assigned = False
    if ticket.assigned_to_ids:
        assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
        is_assigned = current_user.id in assigned_ids

    if not is_assigned:
        flash('You cannot take this ticket because you are not assigned to it.', 'danger')
        return redirect(url_for('view_ticket', ticket_id=ticket_id))

    # Check if current user is already assigned (redundant but keep for message)
    is_already_assigned = True  # Since user is assigned

    if is_already_assigned:
        flash('Ticket is already assigned to you', 'info')
        return redirect(url_for('view_ticket', ticket_id=ticket_id))

    # The below code is unreachable now, but keep for completeness
    if not is_already_assigned:
        if ticket.assigned_to_ids:
            assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
            assigned_ids.append(current_user.id)
            ticket.assigned_to_ids = ','.join(map(str, assigned_ids))
        else:
            ticket.assigned_to_ids = str(current_user.id)
        
        if ticket.status == 'OPEN':
            ticket.status = 'IN_PROGRESS'
        db.session.commit()

        # Notify ticket creator
        message = f"{current_user.full_name} has taken ownership of ticket #{ticket.id}"
        notify_ticket_update(ticket, message, exclude_user_id=current_user.id)

        flash('Ticket assigned to you successfully!', 'success')

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
        # This is a simplified approach - in production you'd want to use proper SQL for better performance
        all_tickets = Ticket.query.all()
        filtered_tickets = []
        for ticket in all_tickets:
            is_assigned_to_me = False
            if ticket.assigned_to_ids:
                assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
                is_assigned_to_me = current_user.id in assigned_ids
            is_unassigned = ticket.assigned_to_ids is None
            
            if is_assigned_to_me or is_unassigned:
                filtered_tickets.append(ticket)
        
        # Convert back to query-like object for pagination
        from sqlalchemy import or_
        ticket_ids = [t.id for t in filtered_tickets]
        if ticket_ids:
            query = query.filter(Ticket.id.in_(ticket_ids))
        else:
            query = query.filter(Ticket.id == -1)  # No results

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

    if request.method == 'POST':
        # Check if username or email already exists
        username = request.form.get('username')
        email = request.form.get('email')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('list_users'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('list_users'))

        # Check password confirmation
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('list_users'))

        department_id = request.form.get('department_id')
        if department_id == '0':
            department_id = None
        else:
            department_id = int(department_id)

        user = User(
            username=username,
            email=email,
            phone=request.form.get('phone'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            role=request.form.get('role'),
            department_id=department_id
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'User {user.username} created successfully!', 'success')
        return redirect(url_for('list_users'))

    return redirect(url_for('list_users'))

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

@app.route('/user/<int:user_id>/delete')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        abort(403)

    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('Cannot delete admin user', 'danger')
    else:
        # Check if user has created or assigned tickets
        created_tickets = Ticket.query.filter_by(created_by_id=user.id).count()
        from sqlalchemy import or_
        user_id_str = str(user.id)
        assigned_tickets = Ticket.query.filter(
            or_(
                Ticket.assigned_to_ids == user_id_str,
                Ticket.assigned_to_ids.like(f'{user_id_str},%'),
                Ticket.assigned_to_ids.like(f'%,{user_id_str},%'),
                Ticket.assigned_to_ids.like(f'%,{user_id_str}')
            )
        ).count()
        
        if created_tickets > 0 or assigned_tickets > 0:
            flash(f'Cannot delete user {user.username} because they have associated tickets. Deactivate instead.', 'warning')
        else:
            # Delete notifications related to the user to avoid integrity errors
            Notification.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()
            flash(f'User {user.username} deleted successfully!', 'success')

    return redirect(url_for('list_users'))

@app.route('/reports')
@login_required
def reports():
    # Only allow admin users to access reports
    if current_user.role != 'admin':
        flash('Access denied. Only administrators can view reports.', 'error')
        return redirect(url_for('dashboard'))

    # Get filter parameters from request
    department_filter = request.args.get('department', '')
    staff_filter = request.args.get('staff', '')

    # Import models to make it available in template
    import models

    # Get filtered stats based on department and staff filters
    filtered_stats = get_ticket_stats()
    filtered_tickets = []
    
    if department_filter or staff_filter:
        # Start with all tickets
        all_tickets = Ticket.query.all()
        
        # Apply department filter if specified
        if department_filter:
            dept_filtered_tickets = []
            for ticket in all_tickets:
                if ticket.creator and ticket.creator.department_id == int(department_filter):
                    dept_filtered_tickets.append(ticket)
            all_tickets = dept_filtered_tickets
        
        # Apply staff filter if specified
        if staff_filter:
            staff_filtered_tickets = []
            for ticket in all_tickets:
                if ticket.assigned_to_ids and str(staff_filter) in ticket.assigned_to_ids.split(','):
                    staff_filtered_tickets.append(ticket)
            filtered_tickets = staff_filtered_tickets
        else:
            filtered_tickets = all_tickets
        
        # Calculate filtered statistics
        filtered_stats = type('Stats', (), {
            'total_tickets': len(filtered_tickets),
            'open_tickets': len([t for t in filtered_tickets if t.status == 'OPEN']),
            'in_progress_tickets': len([t for t in filtered_tickets if t.status == 'IN_PROGRESS']),
            'resolved_tickets': len([t for t in filtered_tickets if t.status == 'RESOLVED']),
            'closed_tickets': len([t for t in filtered_tickets if t.status == 'CLOSED']),
            'urgent_tickets': len([t for t in filtered_tickets if t.priority == 'URGENT']),
            'overdue_tickets': len([t for t in filtered_tickets if t.is_overdue]),
            'total': len(filtered_tickets),
            'open': len([t for t in filtered_tickets if t.status == 'OPEN']),
            'in_progress': len([t for t in filtered_tickets if t.status == 'IN_PROGRESS']),
            'resolved': len([t for t in filtered_tickets if t.status == 'RESOLVED']),
            'closed': len([t for t in filtered_tickets if t.status == 'CLOSED']),
            'urgent': len([t for t in filtered_tickets if t.priority == 'URGENT'])
        })()
    
    stats = filtered_stats
    monthly_data = get_monthly_ticket_data()

    # Get all departments and tech users for dropdowns
    departments = Department.query.all()
    tech_users = User.query.filter_by(role='tech', is_active=True).all()

    # Get department statistics based on filtered data
    department_stats = []
    if not department_filter:  # Show all departments when not filtering by department
        for dept in departments:
            # Get tickets for this department considering staff filter
            dept_tickets = []
            for ticket in Ticket.query.all():
                if ticket.creator and ticket.creator.department_id == dept.id:
                    # If staff filter is applied, only include tickets assigned to that staff
                    if staff_filter:
                        if ticket.assigned_to_ids and str(staff_filter) in ticket.assigned_to_ids.split(','):
                            dept_tickets.append(ticket)
                    else:
                        dept_tickets.append(ticket)
            
            total_count = len(dept_tickets)
            open_count = len([t for t in dept_tickets if t.status in ['OPEN', 'IN_PROGRESS']])
            resolved_count = len([t for t in dept_tickets if t.status in ['RESOLVED', 'CLOSED']])

            if total_count > 0:  # Only include departments with tickets
                dept_stat = type('DeptStat', (), {
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code,
                    'total_count': total_count,
                    'open_count': open_count,
                    'resolved_count': resolved_count
                })()
                department_stats.append(dept_stat)
    else:
        # Show filtered department stats
        dept = Department.query.get(department_filter)
        if dept:
            # Use the filtered tickets we already calculated
            total_count = len(filtered_tickets)
            open_count = len([t for t in filtered_tickets if t.status in ['OPEN', 'IN_PROGRESS']])
            resolved_count = len([t for t in filtered_tickets if t.status in ['RESOLVED', 'CLOSED']])

            if total_count > 0:
                dept_stat = type('DeptStat', (), {
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code,
                    'total_count': total_count,
                    'open_count': open_count,
                    'resolved_count': resolved_count
                })()
                department_stats.append(dept_stat)

    # Get technical staff performance data
    tech_stats = []
    if not staff_filter:  # Show all tech stats when not filtering by staff
        for tech in tech_users:
            # Get tickets assigned to this tech user
            assigned_tickets = []
            all_tickets = Ticket.query.filter(Ticket.assigned_to_ids.isnot(None)).all()
            
            for ticket in all_tickets:
                # Check if ticket is assigned to this tech
                if ticket.assigned_to_ids and str(tech.id) in ticket.assigned_to_ids.split(','):
                    # Apply department filter if specified
                    if department_filter:
                        if ticket.creator and ticket.creator.department_id == int(department_filter):
                            assigned_tickets.append(ticket)
                    else:
                        assigned_tickets.append(ticket)
                    
            total_assigned = len(assigned_tickets)
            active_tickets = len([t for t in assigned_tickets if t.status in ['OPEN', 'IN_PROGRESS']])
            resolved_tickets = len([t for t in assigned_tickets if t.status in ['RESOLVED', 'CLOSED']])

            if total_assigned > 0:  # Only show techs with assigned tickets
                tech_stat = type('TechStat', (), {
                    'id': tech.id,
                    'name': tech.full_name,
                    'email': tech.email,
                    'total_assigned': total_assigned,
                    'active_tickets': active_tickets,
                    'resolved_tickets': resolved_tickets,
                    'resolution_rate': (resolved_tickets / total_assigned * 100) if total_assigned > 0 else 0
                })()
                tech_stats.append(tech_stat)
    else:
        # Show filtered tech stats
        tech = User.query.get(staff_filter)
        if tech and tech.role == 'tech' and tech.is_active:
            # Use the filtered tickets we already calculated
            total_assigned = len(filtered_tickets)
            active_tickets = len([t for t in filtered_tickets if t.status in ['OPEN', 'IN_PROGRESS']])
            resolved_tickets = len([t for t in filtered_tickets if t.status in ['RESOLVED', 'CLOSED']])

            tech_stat = type('TechStat', (), {
                'id': tech.id,
                'name': tech.full_name,
                'email': tech.email,
                'total_assigned': total_assigned,
                'active_tickets': active_tickets,
                'resolved_tickets': resolved_tickets,
                'resolution_rate': (resolved_tickets / total_assigned * 100) if total_assigned > 0 else 0
            })()
            tech_stats.append(tech_stat)

    return render_template('reports.html', 
                         stats=stats, 
                         monthly_data=monthly_data,
                         department_stats=department_stats,
                         tech_stats=tech_stats,
                         departments=departments,
                         tech_users=tech_users,
                         current_department=department_filter,
                         current_staff=staff_filter,
                         models=models,
                         User=User, Ticket=Ticket, Department=Department)

@app.route('/reports/print')
@login_required
def print_reports():
    if current_user.role != 'admin':
        abort(403)

    try:
        from datetime import datetime, timedelta

        # Get report parameters
        report_type = request.args.get('type', 'weekly')
        department_filter = request.args.get('department', '')
        staff_filter = request.args.get('staff', '')

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

        # Base tickets query
        tickets_query = db.session.query(Ticket).join(
            User, Ticket.created_by_id == User.id
        ).filter(Ticket.created_at.between(start_date, end_date))

        # Apply department filter
        if department_filter:
            tickets_query = tickets_query.filter(User.department_id == department_filter)

        # Get all tickets first, then apply filters
        all_tickets = tickets_query.all()
        
        # Apply staff filter if specified
        if staff_filter:
            staff_filtered_tickets = []
            for ticket in all_tickets:
                if ticket.assigned_to_ids and str(staff_filter) in ticket.assigned_to_ids.split(','):
                    staff_filtered_tickets.append(ticket)
            tickets = staff_filtered_tickets
        else:
            tickets = all_tickets
        
        # Sort tickets by creation date (newest first)
        tickets.sort(key=lambda t: t.created_at, reverse=True)

        # Get statistics
        stats = get_ticket_stats()

        # Get filtered statistics
        filtered_stats = {
            'total_tickets': len(tickets),
            'open_tickets': len([t for t in tickets if t.status == 'OPEN']),
            'in_progress_tickets': len([t for t in tickets if t.status == 'IN_PROGRESS']),
            'resolved_tickets': len([t for t in tickets if t.status == 'RESOLVED']),
            'closed_tickets': len([t for t in tickets if t.status == 'CLOSED']),
            'urgent_tickets': len([t for t in tickets if t.priority == 'URGENT'])
        }

        # Department breakdown with explicit joins
        department_stats = []
        if not department_filter:  # Show all departments if no filter
            departments = Department.query.all()
            for dept in departments:
                dept_tickets_query = db.session.query(Ticket).join(
                    User, Ticket.created_by_id == User.id
                ).filter(
                    User.department_id == dept.id,
                    Ticket.created_at.between(start_date, end_date)
                )

                total = dept_tickets_query.count()
                if total > 0:
                    department_stats.append(type('DeptStat', (), {
                        'department_name': dept.name,
                        'total': total,
                        'open': dept_tickets_query.filter(Ticket.status == 'OPEN').count(),
                        'resolved': dept_tickets_query.filter(Ticket.status == 'RESOLVED').count(),
                        'closed': dept_tickets_query.filter(Ticket.status == 'CLOSED').count()
                    })())

        # Get report title based on filters
        report_title = f"{report_type.title()} Report"
        if department_filter:
            dept = Department.query.get(department_filter)
            report_title += f" - {dept.name}" if dept else ""
        if staff_filter:
            tech = User.query.get(staff_filter)
            report_title += f" - {tech.full_name}" if tech else ""

        return render_template('reports_printable.html', 
                             stats=filtered_stats, 
                             tickets=tickets,
                             department_stats=department_stats,
                             report_type=report_type,
                             report_title=report_title,
                             current_date=now)
    except Exception as e:
        print(f"Reports error: {e}")
        flash('Error generating reports. Please try again.', 'danger')
        return redirect(url_for('reports'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    # Handle profile update
    if request.method == 'POST' and 'update_profile' in request.form:
        if profile_form.validate_on_submit():
            # Check if email is already taken by another user
            existing_user = User.query.filter_by(email=profile_form.email.data).first()
            if existing_user and existing_user.id != current_user.id:
                flash('Email address is already in use by another user.', 'danger')
                return render_template('profile.html', profile_form=profile_form, password_form=password_form)

            # Update user profile
            current_user.first_name = profile_form.first_name.data
            current_user.last_name = profile_form.last_name.data
            current_user.email = profile_form.email.data
            current_user.phone = profile_form.phone.data

            # Only allow department change for regular users (not tech or admin)
            if current_user.role == 'user':
                current_user.department_id = profile_form.department_id.data if profile_form.department_id.data > 0 else None

            current_user.updated_at = datetime.utcnow()
            db.session.commit()

            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))

    # Handle password change
    if request.method == 'POST' and 'change_password' in request.form:
        if password_form.validate_on_submit():
            # Verify current password
            if not current_user.check_password(password_form.current_password.data):
                flash('Current password is incorrect.', 'danger')
                return render_template('profile.html', profile_form=profile_form, password_form=password_form)

            # Update password
            current_user.set_password(password_form.new_password.data)
            current_user.updated_at = datetime.utcnow()
            db.session.commit()

            flash('Password changed successfully!', 'success')
            return redirect(url_for('profile'))

    # Populate department field for GET request
    if current_user.department_id:
        profile_form.department_id.data = current_user.department_id
    else:
        profile_form.department_id.data = 0

    return render_template('profile.html', profile_form=profile_form, password_form=password_form)

@app.route('/api/notifications/mark_read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        abort(403)

    notification.is_read = True
    db.session.commit()

    return jsonify({'success': True})

@app.route('/api/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    return jsonify({'success': True, 'message': 'All notifications marked as read'})

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

@app.route('/admin/test-notifications', methods=['POST'])
@login_required
def test_notifications():
    if current_user.role != 'admin':
        abort(403)

    try:
        from utils import send_sms_notification, send_email_notification

        # Test SMS to admin
        if current_user.phone:
            sms_sent = send_sms_notification(
                current_user.phone, 
                "Test SMS from ICT Ticketing System. SMS notifications are working!"
            )
            if sms_sent:
                flash('Test SMS sent successfully!', 'success')
            else:
                flash('Failed to send test SMS. Check Twilio configuration.', 'warning')
        else:
            flash('No phone number on file for SMS test.', 'info')

        # Test Email to admin
        email_sent = send_email_notification(
            current_user.email,
            "Test Email from ICT Ticketing System",
            "This is a test email to verify that email notifications are working correctly."
        )
        if email_sent:
            flash('Test email sent successfully!', 'success')
        else:
            flash('Failed to send test email. Check SendGrid configuration.', 'warning')

    except Exception as e:
        flash(f'Error testing notifications: {str(e)}', 'danger')

    return redirect(url_for('list_users'))

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

    # Notify assignees if exist
    if ticket.assigned_to_ids:
        from utils import create_notification
        assigned_ids = [int(id.strip()) for id in ticket.assigned_to_ids.split(',') if id.strip()]
        for assignee_id in assigned_ids:
            create_notification(
                user_id=assignee_id,
                title='Ticket Closed',
                message=f'Ticket "{ticket.title}" has been closed by the requester.',
                ticket_id=ticket.id
            )

    flash('Ticket closed successfully!', 'success')
    return redirect(url_for('view_ticket', ticket_id=ticket_id))

@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@login_required
def delete_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Check permissions - admin can delete any ticket, others can only delete their own tickets
    if not (current_user.role == 'admin' or ticket.created_by_id == current_user.id):
        abort(403)
    
    try:
        # Delete associated records first
        TicketComment.query.filter_by(ticket_id=ticket_id).delete()
        Notification.query.filter_by(ticket_id=ticket_id).delete()
        TicketAttachment.query.filter_by(ticket_id=ticket_id).delete()
        
        # Delete the ticket
        db.session.delete(ticket)
        db.session.commit()
        
        flash('Ticket deleted successfully!', 'success')
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete ticket'}), 500

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