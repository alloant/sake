#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, redirect, session, flash
from flask_login import current_user

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, Comment, File
from app.forms.note import NoteForm

def read_note_view(request):
    reg = request.args.get('reg')
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    note.updateRead(current_user)

    return note.content_html(reg)

def state_note_view(request):
    note_id = request.args.get('note')
    reg = request.args.get('reg')
    cancel = request.args.get('cancel',False)
    
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.updateState(reg,current_user,cancel)

    return note.status_html(reg)
   

