# forms.py

from flask_wtf import FlaskForm
from flask_babel import gettext
from wtforms import StringField, BooleanField, SelectField, DateField, IntegerField, RadioField, SubmitField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms_sqlalchemy.orm import QuerySelectField, QuerySelectMultipleField

from sqlalchemy import select

from app import db
from app.src.models import Note,User


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class ReceiverForm(FlaskForm):
    receiver = MultiCheckboxField(gettext('Receiver'),coerce=str)
    submit = SubmitField(gettext("Save"))

class TagForm(FlaskForm):
    tag = MultiCheckboxField(gettext('Tag'),coerce=str)
    submit = SubmitField(gettext("Save"))

class NoteForm(FlaskForm):
    #num = IntegerField('Num',validators=[DataRequired()])
    num = IntegerField(gettext('Number'))
    year = IntegerField(gettext('Year'),validators=[DataRequired()])
    sender = SelectField(gettext('Sender'), validators=[DataRequired()])

    receiver = MultiCheckboxField(gettext('Receiver'),coerce=str)
    #receiver = SelectMultipleField('Receiver', validators=[DataRequired()])
    n_groups = StringField(gettext('Groups'), validators=[])
    n_date = DateField(gettext('Date'), validators=[DataRequired()])
    content = StringField(gettext('Subject'), validators=[DataRequired()])
    content_jp = StringField(gettext('Subject Japanese'), validators=[])
    comments = TextAreaField(gettext('Comments'), validators=[])
    comments_ctr = StringField(gettext('Comments ctr'), validators=[])
    proc = SelectField(gettext('Procedure'), validators=[])
    #proc = StringField('Procedure', validators=[])
    ref = StringField(gettext('References'), validators=[])

    permanent = BooleanField(gettext('Only permanent'))

    submit = SubmitField(gettext("Save"))
