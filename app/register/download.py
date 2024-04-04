#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, redirect, session, flash, send_file
from flask_login import current_user

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, get_ref, Comment
from app.forms.note import NoteForm

from app.syneml import write_eml

def download_view(request):
    note_id = request.args.get('note')
    nt = db.session.scalar(select(Note).where(Note.id==note_id))

    rec = ",".join([rec.email for rec in nt.receiver])
    path = f"{current_user.local_path}/Outbox"

    if nt.state < 6:
        nt.state = 6
        db.session.commit()

    return write_eml(rec,nt,path)
    
    #return redirect(session['lasturl'])


