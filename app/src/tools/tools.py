#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

from cryptography.fernet import Fernet

from sqlalchemy import select, func, literal_column, and_
from sqlalchemy.orm import aliased

from flask import session, current_app
from flask_babel import gettext
from flask_login import current_user

from app import db
from app.src.models import User, Note, Register, NoteUser, Group, Tag

def toNewNotesStatus():
    USER = 'pop'
    user = db.session.scalar(select(User).where(User.alias==USER))
    cipher = Fernet(current_app.config['SECRET_KEY'])
    PASSWD = cipher.decrypt(user.get_setting('password_nas'))
    print(PASSWD)


