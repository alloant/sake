#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

from cryptography.fernet import Fernet

from sqlalchemy import select, func, literal_column, and_, not_, or_
from sqlalchemy.orm import aliased

from flask import session, current_app
from flask_babel import gettext
from flask_login import current_user

from app import db
from app.src.models import User, Note, Register, NoteUser, Group, Tag

def toNewNotesStatus():
    user = db.session.scalar(select(User).where(User.alias=='tak'))
    register = db.session.scalar(select(Register).where(Register.alias=='ctr'))
    notes = db.session.scalars(select(Note).where(Note.result('is_read',user)==False,Note.reg=='ctr',Note.status=='registered',Note.permanent==False)).all()

    for i,note in enumerate(notes):
        print(i,note.fullkey,note.content,note.date)

    rst = db.session.scalar(select(func.count(Note.id)).where(Note.status=='registered',Note.permanent==False,Note.result('access').in_(['reader','editor']),Note.register_id==register.id,not_(Note.result('is_read',user))))

    print('result:',rst)


def get_password():
    USER = 'pop'
    user = db.session.scalar(select(User).where(User.alias==USER))
    cipher = Fernet(current_app.config['SECRET_KEY'])
    PASSWD = cipher.decrypt(user.get_setting('password_nas'))
    print(PASSWD)


