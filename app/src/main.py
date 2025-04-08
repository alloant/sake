#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, session, current_app
from flask_login import current_user

from datetime import date

from sqlalchemy import select, update, not_, or_

from app.src.notes.renders import get_title
from app.src.models import Register, Note
from app import db

def wake_up_notes():
    notes = db.session.scalars(select(Note).where(or_(Note.sender_id==current_user.id,Note.has_target(current_user.id)),not_(Note.due_date.is_(None)),Note.due_date<=date.today())).all()

    for note in notes:
        note.due_date = None

    db.session.commit()

def dashboard_view(template):
    if session.get('theme') is None:
        session.permanent = True
        session['theme'] = 'light-mode'

    if session.get('version') is None:
        session.permanent = True
        session['version'] = 'old'
    
    session['link'] = f"https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}"

    wake_up_notes()
    
    if 'reg' in session:
        reg = session['reg']
    else:
        if current_user.category in ['dr','of']:
            reg = ['notes','all','']
        else:
            registers = db.session.scalars(select(Register).where(Register.active==1)).all()
            reg = ''
            for register in registers:
                for subregister in register.get_subregisters():
                    reg = [register.alias,'in',subregister]
                    session['reg'] = reg
                    break
                if reg: break
            
        session['reg'] = reg
    
    title = get_title(reg)
    
    return render_template(template,reg=reg,title=title,sock_server = current_app.config['SOCK_SERVER'])



