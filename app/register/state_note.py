#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast

from flask import render_template, redirect, session, flash, make_response
from flask_login import current_user

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, Comment, File
from app.forms.note import NoteForm
from xml.etree import ElementTree as ET

def read_note_view(request):
    reg = session['reg'] 
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    note.updateRead(current_user)
    
    res = make_response(note.content_html())
    #res.headers['HX-Trigger'] = 'read-updated'
    res.headers['HX-Trigger'] = 'read-updated'

    return res

    return note.content_html(reg)


def note_row_view(request):
    reg = session['reg'] 
    note_id = request.args.get('note')
    
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    return render_template('table/table_row.html',note=note, reg=reg, user=current_user)


def state_note_view(request):
    reg = session['reg'] 
    note_id = request.args.get('note')
    
    cancel = request.args.get('cancel',False)
    
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.updateState(reg,current_user,cancel)
    
    #<tr id="noteRow-{{note.id}}" class="" hx-swap="outerHTML">
    #if rg[0] == 'mat':
    #    return render_template('register/table_row.html',note=note, reg=reg, user=current_user)
    
    res = make_response(note.status_html())
    res.headers['HX-Trigger'] = f'update-row-{note.id}'

    return res


    return note.status_html(reg)
   
def register_icon_view (request):
    reg = session['reg'] 
    return current_user.register_icon_html(reg)
