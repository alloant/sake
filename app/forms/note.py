# forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SelectField,DateField,IntegerField, RadioField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms_sqlalchemy.orm import QuerySelectField, QuerySelectMultipleField
from sqlalchemy import select

from app import db
from app.models import Note,User

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class ReceiverForm(FlaskForm):
    receiver = MultiCheckboxField('Receiver',coerce=str)
    submit = SubmitField("Submit")

class NoteForm(FlaskForm):
    #num = IntegerField('Num',validators=[DataRequired()])
    num = IntegerField('Num')
    year = IntegerField('Year',validators=[DataRequired()])
    sender = SelectField('Sender', validators=[DataRequired()])

    receiver = MultiCheckboxField('Receiver',coerce=str)
    #receiver = SelectMultipleField('Receiver', validators=[DataRequired()])
    n_groups = StringField('Groups', validators=[])
    n_date = DateField('Date', validators=[DataRequired()])
    content = StringField('Content', validators=[DataRequired()])
    content_jp = StringField('Content JP', validators=[])
    comments = StringField('Comments', validators=[])
    comments_ctr = StringField('Comments ctr', validators=[])
    proc = SelectField('Procedure', validators=[])
    #proc = StringField('Procedure', validators=[])
    ref = StringField('References', validators=[])

    permanent = BooleanField('Only permanent')

    submit = SubmitField("Submit")
