# forms.py

from app.models import User

from wtforms import Form, BooleanField, StringField, PasswordField, validators, SubmitField, IntegerField

class LoginForm(Form):
    alias = StringField('User', [validators.Length(min=2, max=25)])
    password = PasswordField('Password', [validators.DataRequired()])

class RegistrationForm(Form):
    name = StringField('Name', [validators.Length(min=4, max=40)])
    alias = StringField('User', [validators.Length(min=2, max=25)])
    email = StringField('Email Address')
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    u_groups = StringField('Groups')
    active = BooleanField('User is active')
    admin_active = StringField('Admin mode on')
    confirm = PasswordField('Repeat Password')

class UserForm(Form):
    id = IntegerField('id')
    name = StringField('Name', [validators.Length(min=4, max=40)])
    alias = StringField('User', [validators.Length(min=2, max=25)])
    email = StringField('Email Address')
    local_path = StringField('Local folder to download/upload emls')
    u_groups = StringField('Groups')
    active = BooleanField('User is active')
    admin_active = BooleanField('Admin mode on')
   
    submit = SubmitField('Submit')
