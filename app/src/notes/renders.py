#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re

from flask import render_template, session, make_response
from flask_login import current_user

from sqlalchemy import select, and_, or_, func, not_

from app import db
from app.src.models import Note, User, Register, File
from app.src.notes.filters import get_notes, get_history, register_filter, get_title
from app.src.inbox.inbox import inbox_main_view

def render_main_body(request,template): 
    output = request.form.to_dict()
    page = request.args.get('page', 1, type=int)
    session['page'] = page
    reg = session['reg']

    if reg[2]:
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        session['ctr'] = {'alias': ctr.alias, 'date': ctr.date.strftime('%Y-%m-%d')}
    else:
        session['ctr'] = {}
    
    if 'filter_option' in output:
        session['filter_option'] = output['filter_option']
    else: 
        if not 'page' in request.args:
            if 'search' in output:
                session['filter_notes'] = output['search']
            else:
                session['filter_notes'] = ''

    notes = get_notes(reg,filter = session['filter_notes'] if 'filter_notes' in session else '')

    if template == 'mobile':
        return render_template('mobile/notes/cards.html', notes=notes, page=page, reg=reg)
    else:
        return render_template('notes/table.html', notes=notes, page=page, reg=reg)

def render_main_title_body(request,template):
    reg = request.args.get('reg','')
    if reg:
        reg = ast.literal_eval(reg)
        session['reg'] = reg
    else:
        reg = session['reg']

    if reg[0] == 'import':
        return inbox_main_view(request)
    else:
        session['filter_notes'] = ''
        if not 'filter_option' in session:
            if reg[0] == 'all' and reg[1] == 'all':
                session['filter_option'] = 'only_notes'
            else:
                session['filter_option'] = 'hide_archived'
        elif reg[0] == 'all' and reg[1] == 'all':
            if not session['filter_option'] in ['only_notes','only_proposals','notes_proposals']:
                session['filter_option'] = 'only_notes'
        else:
            if not session['filter_option'] in ['hide_archived','show_archived']:
                session['filter_option'] = 'hide_archived'
        
        if reg[2]:
            ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
            session['ctr'] = {'alias': ctr.alias, 'date': ctr.date.strftime('%Y-%m-%d')}
        else:
            session['ctr'] = {}

        title = get_title(reg)

        if isinstance(reg[1],int):
            notes = get_history(reg[1])
        else:
            notes = get_notes(reg)
        
        res = make_response(render_template(template,title=title, notes=notes, reg=reg))
    
    res.headers['HX-Trigger'] = 'update-main'

    return res

def render_body_element(reg,note_id,element,template):
    if element == 'row':
        return render_body_row(reg,note_id,template)
    

def get_body_data(info):
    return current_user.data(info,True)

def render_body_row(reg,note_id,template):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    if template == 'mobile':
        return render_template('mobile/notes/card/card.html',note=note, reg=reg, user=current_user)
    else:
        if reg[2]:
            return render_template('notes/table/1_row_ctr.html',note=note, reg=reg, user=current_user)
        else:
            return render_template('notes/table/1_row.html',note=note, reg=reg, user=current_user)

def render_sidebar(element,template):
    theme = '' if session['theme'] == 'light-mode' else '-dark'
    if element:
        reg = session['reg']
        if element == 'pendings':
            element_title = 'Pending'
            icon = f'00-{element}{theme}'
            focus = True if reg[1] == 'pen' else False
        elif element == 'matters':
            element_title = 'Proposals'
            icon = f'00-{element}{theme}'
            focus = True if reg[0] == 'mat' else False
        elif element == 'search':
            element_title = 'Global search'
            icon = f'00-{element}{theme}'
            focus = True if reg[0] == 'all' and reg[1] == 'all' else False
        elif element == 'register':
            element_title = 'Register'
            icon = f'00-{element}{theme}'
            focus = True if not reg[0] in ['mat','des','box','import','all'] and reg[1] != 'pen' else False
        elif element == 'despacho':
            element_title = 'Despacho'
            icon = f'00-{element}{theme}'
            focus = True if reg[0] == 'des' else False
        elif element == 'import':
            element_title = 'Import'
            icon = f'00-{element}{theme}'
            focus = True if reg[0] == 'import' else False
        elif element == 'inbox':
            element_title = 'Inbox'
            icon = f'00-{element}{theme}'
            focus = True if reg[0] == 'box' and reg[1] == 'in' else False
        elif element == 'outbox':
            element_title = 'Outbox'
            icon = f'00-{element}{theme}'
            focus = True if reg[0] == 'box' and reg[1] == 'out' else False
        elif '_' in element:
            ele = element.split('_')
            if ele[2]:
                element_title = f'{ele[2]} {ele[1]}'
                icon = f'ctr/{ele[2]}-{ele[1]}'
            else:
                element_title = f'{ele[0]} {ele[1]}'
                icon = f'ctr/{ele[0]}-{ele[1]}'
            focus = True if ele == reg else False
            element_title = ''
        else:
            element_title = element
            icon = f'00-{element}{theme}'
            focus = False

       
        return render_template(f'sidebar_icon.html',element=element,element_title=element_title,focus=focus,icon=icon)
    else:
        return render_template(f'{template}sidebar.html')


