#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re

from flask import render_template, session, make_response
from flask_login import current_user

from sqlalchemy import select, and_, or_, func, not_
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased

from flask_babel import gettext

from app import db
from app.src.models import Note, User, Register, File
from app.src.forms.note import NoteForm
from app.src.notes.edit import fill_form_note, extract_form_note

from app.src.tools.tools import newNote, sendmail, delete_note
from app.src.models.nas.nas import copy_path, copy_office_path


def table_body_view(request,template):
    if 'reg' in session:
        page = 1 if not 'page' in session else session['page']
        if isinstance(session['reg'][1],int):
            notes = get_history(session['reg'][1])
        else:
            notes = get_notes(session['reg'],filter = session['filter_notes'] if 'filter_notes' in session else '')

        if template == 'mobile':
            return render_template('mobile/notes/cards.html', notes=notes, page=page, reg=session['reg'])
        else:
            return render_template('notes/table/0_rows.html', notes=notes, page=page, reg=session['reg'])

    return ""


def notes_data_view(request):
    info = request.args.get('info')
    return current_user.data(info,True)


def browse_files_modal(request):
    reg = ast.literal_eval(request.args.get('reg'))
    
    copy = request.args.get("copy","")
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    untitled =[]
    
    if copy == 'true':
        files = request.form.getlist('files_to_copy')
        cont = 0
        for file in files:
            if re.match(r'Untitled\.(odoc|osheet|oslide)',file.split('/')[-1]):
                name = file.split('/')[-1]
                ext = name.split('.')[-1]
                for fn in note.files + untitled:
                    fname = fn if isinstance(fn,str) else fn.path
                    if re.match(fr'{note.folder_name}_*a*[0-9]*\.[a-zA-Z]+',fname):
                        cont += 1

                if cont == 0:
                    copy_office_path(file,f"{note.folder_path}/{note.folder_name}.{ext}")
                else:
                    copy_office_path(file,f"{note.folder_path}/{note.folder_name}_a{cont}.{ext}")
                untitled.append(note.folder_name)
            else:
                copy_path(file,f"{note.folder_path}/{file.split('/')[-1]}")
        
        note.updateFiles()

        if reg[2] and session['version'] == 'old':
            return render_template("notes/table/2_files_old.html",note=note, reg=reg)
        else:
            return render_template("notes/table/2_files.html",note=note, reg=reg)
    
    return render_template("modals/modal_files.html",note=note, reg=reg)

   

