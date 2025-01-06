#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

from sqlalchemy import select, func, literal_column, and_
from sqlalchemy.orm import aliased

from flask import session, current_app
from flask_babel import gettext
from flask_login import current_user

from app import db
from app.src.models import User, Note, Register, NoteUser, Group, Tag

def toNewNotesStatus():

    notes = db.session.scalars(select(Note)).all()
    users = db.session.scalars(select(User)).all()
    ctrs = db.session.scalars(select(User).where(User.category=='ctr')).all()
    registers = db.session.scalars(select(Register)).all()
    groups = db.session.scalars(select(Group)).all()

    for note in notes:
        for tag in note.n_tags.split(','):
            note.add_tag(tag)

    db.session.commit()
