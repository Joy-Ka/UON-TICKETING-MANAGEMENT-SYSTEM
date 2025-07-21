from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from models import Department

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class TicketForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=5, max=200)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=10)])
    priority = SelectField('Priority', choices=[
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent')
    ], validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('HARDWARE', 'Hardware'),
        ('SOFTWARE', 'Software'),
        ('NETWORK', 'Network'),
        ('EMAIL', 'Email'),
        ('PRINTER', 'Printer'),
        ('OTHER', 'Other')
    ], validators=[DataRequired()])
    attachments = MultipleFileField('Attachments', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'txt', 'xlsx', 'xls'], 
                   'Only images, documents and spreadsheets are allowed!')
    ])
    attachments = MultipleFileField('Attachments', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'txt', 'xlsx', 'xls'], 
                   'Only images, documents and spreadsheets are allowed!')
    ])

class CommentForm(FlaskForm):
    comment = TextAreaField('Comment', validators=[DataRequired(), Length(min=5)])
    is_internal = BooleanField('Internal Note (Tech Team Only)')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone')
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[
        ('user', 'Department User'),
        ('tech', 'Technical Staff'),
        ('admin', 'Administrator')
    ], validators=[DataRequired()])
    department_id = SelectField('Department', coerce=int)
    
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
        self.department_id.choices.insert(0, (0, 'Select Department'))

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    department_id = SelectField('Department', coerce=int, validators=[DataRequired()], validate_choice=False)
    
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        from models import Department
        self.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
        self.department_id.choices.insert(0, (0, 'Select Your Department'))

class TechRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    position = SelectField('Position', choices=[
        ('attachee', 'Attachee'),
        ('intern', 'Intern'),
        ('technician', 'Technician')
    ], validators=[DataRequired()])

class AssignTicketForm(FlaskForm):
    assigned_to_id = SelectField('Assign To', coerce=int, validators=[DataRequired()])
    
    def __init__(self, *args, **kwargs):
        super(AssignTicketForm, self).__init__(*args, **kwargs)
        from models import User
        tech_users = User.query.filter(User.role.in_(['tech', 'admin'])).all()
        self.assigned_to_id.choices = [(u.id, u.full_name) for u in tech_users]

class UpdateTicketStatusForm(FlaskForm):


class ProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number')
    department_id = SelectField('Department', coerce=int)
    
    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        from models import Department
        self.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
        self.department_id.choices.insert(0, (0, 'No Department'))

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[DataRequired(), EqualTo('new_password', message='Passwords must match')])

    status = SelectField('Status', choices=[
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed')
    ], validators=[DataRequired()])
