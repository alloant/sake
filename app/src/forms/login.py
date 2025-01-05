# forms.py

from app.src.models import User
from flask_babel import gettext

from wtforms import Form, BooleanField, StringField, PasswordField, validators, SubmitField, IntegerField, SelectMultipleField
from wtforms.widgets import ListWidget, CheckboxInput

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class LoginForm(Form):
    alias = StringField(gettext('User'), [validators.Length(min=2, max=25)])
    password = PasswordField(gettext('Password'), [validators.DataRequired()])

class RegistrationForm(Form):
    name = StringField(gettext('Name'), [validators.Length(min=4, max=40)])
    alias = StringField(gettext('User'), [validators.Length(min=2, max=25)])
    email = StringField(gettext('Email Address'))
    password = PasswordField(gettext('Password'), [
        validators.DataRequired(),
        validators.EqualTo('confirm', message=gettext('Passwords must match'))
    ])
    active = BooleanField(gettext('User is active'))
    admin_active = StringField(gettext('Admin mode on'))
    confirm = PasswordField(gettext('Repeat Password'))

class UserForm(Form):
    id = IntegerField('id')
    name = StringField(gettext('Name'), [validators.Length(min=4, max=40)])
    alias = StringField(gettext('User'), [validators.Length(min=2, max=25)])
    email = StringField(gettext('Email Address'))
    local_path = StringField(gettext('Local folder to download/upload emls'))
    active = BooleanField(gettext('User is active'))
    admin_active = BooleanField(gettext('Admin mode on'))
    
    notifications_active = BooleanField(gettext('Receive notifications'),default=False)
    
    groups = MultiCheckboxField(gettext('Groups'),coerce=str)
    registers = MultiCheckboxField(gettext('Registers'),coerce=str)
    ctrs = MultiCheckboxField(gettext('ctrs'),coerce=str)
   
    submit = SubmitField(gettext('Submit'))
