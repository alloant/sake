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
    num = IntegerField(gettext('Number'), render_kw={"disabled": True})
    year = IntegerField(gettext('Year'),validators=[DataRequired()], render_kw={"disabled": True})
    sender = SelectField(gettext('Sender'), validators=[DataRequired()], render_kw={"disabled": True})
    reg = SelectField(gettext('Register'), validators=[])

    receiver = MultiCheckboxField(gettext('Receiver'),coerce=str)
    #receiver = SelectMultipleField('Receiver', validators=[DataRequired()])
    n_groups = StringField(gettext('Groups'), validators=[])
    n_date = DateField(gettext('Date'), validators=[DataRequired()], render_kw={"disabled": True})
    content = TextAreaField(gettext('Subject'), validators=[DataRequired()], render_kw={"disabled": True})
    content_jp = TextAreaField(gettext('Subject Japanese'), validators=[], render_kw={"disabled": True})
    comments = TextAreaField(gettext('Comments'), validators=[], render_kw={"disabled": True})
    comments_ctr = StringField(gettext('Comments ctr'), validators=[])
    proc = SelectField(gettext('Procedure'), validators=[], render_kw={"disabled": True})
    #proc = StringField('Procedure', validators=[])
    ref = StringField(gettext('References'), validators=[])

    is_ref = BooleanField(gettext('It is a reference'), render_kw={"disabled": True})
    permanent = BooleanField(gettext('Only permanent'), render_kw={"disabled": True})

    submit = SubmitField(gettext("Save"))

    def set_disabled(self,user,note,reg):
        if note == None:
            self.is_ref.render_kw = {"disabled": False}
            self.n_date.render_kw = {"disabled": False}
            self.year.render_kw = {"disabled": False}
            self.sender.render_kw = {"disabled": False}
            self.content.render_kw = {"disabled": False}
            self.content_jp.render_kw = {"disabled": False}
            self.comments.render_kw = {"disabled": False}
            self.proc.render_kw = {"disabled": False}
            self.permanent.render_kw = {"disabled": False}
        elif user.admin or note.state == 0 or note.permissions('can_edit') or reg[0] in ['box','des']:
            self.n_date.render_kw = {"disabled": False}
            self.content.render_kw = {"disabled": False}
            self.content_jp.render_kw = {"disabled": False}
            self.comments.render_kw = {"disabled": False}
            self.proc.render_kw = {"disabled": False}
            self.permanent.render_kw = {"disabled": False}

