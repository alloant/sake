# forms.py

from flask_wtf import FlaskForm
from flask_babel import gettext
from wtforms import StringField, BooleanField, SelectField, DateField, IntegerField, RadioField, SubmitField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms_sqlalchemy.orm import QuerySelectField, QuerySelectMultipleField


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class GroupForm(FlaskForm):
    group = MultiCheckboxField(gettext('Group'),coerce=str)
    submit = SubmitField(gettext("Save"))

class PageForm(FlaskForm):
    title = StringField(gettext('Title'), validators=[])
    category = StringField(gettext('Category'), validators=[])
    text = TextAreaField(gettext('Text'), validators=[])

    submit = SubmitField(gettext("Save"))

    def set_disabled(self,user,note,reg):
        self.category = {"disabled": False}

