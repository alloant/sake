#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, redirect, session, flash, send_file, current_app
from flask_login import current_user

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, Comment
from app.forms.note import NoteForm

from app.syneml import write_eml

def download_view(request):
    note_id = request.args.get('note')
    nt = db.session.scalar(select(Note).where(Note.id==note_id))
    
    if nt.state < 6:
        nt.state = 6
        if nt.reg in ['vc','vcr','dg','cc','desr']:
            rst = nt.move(f"/team-folders/Mail {nt.reg}/Notes/{nt.year}/{nt.reg} out")
        else:
            rst = nt.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{nt.year}/{nt.reg} out")
        db.session.commit()

    if nt.reg in ['cg','dg','cc','desr']:
        rec = "cg@cardumen.lan"
    else:
        rec = ",".join([rec.email for rec in nt.receiver])
    path = f"{current_user.local_path}/Outbox"

    
    return write_eml(rec,nt,path)
    
    #return redirect(session['lasturl'])


