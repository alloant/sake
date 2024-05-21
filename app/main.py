#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re
from xml.etree import ElementTree as ET

from flask import render_template, session, url_for
from flask_login import current_user

from flask_babel import gettext

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, Register

from app.register.tools import newNote

def register_filter(reg, filter = ""):
    fn = []
    
    # First filter register notes. Diving for ctr or the rest
    if reg[0] == 'des': # Es despacho
        fn.append(Note.reg!='mat')
        fn.append(Note.state>1)
        fn.append(Note.state<5)
    elif reg[0] == 'box' and reg[1] == 'out': # Es outbox
        fn.append(Note.reg!='mat')
        fn.append(Note.flow=='out')
        fn.append(Note.state==1)
    elif reg[2]: # Es un subregister
        register = db.session.scalar(select(Register).where(Register.alias==reg[0]))
        fn.append(Note.register_id==register.id)
        if reg[1] == 'in':
            fn.append(Note.state==6)
            fn.append(Note.receiver.any(User.alias==reg[2]))
        elif reg[1] == 'out':
            fn.append(Note.sender.has(User.alias==reg[2]))
    
        if not session['showAll'] and reg[1] == 'in':
            ctr_fn = db.session.scalar(select(User).where(User.alias==reg[2]))
            fn.append(Note.is_done(ctr_fn))

    else: # Es un register
        if reg[0] == 'all': # Here I get all notes from all registers
            registers = db.session.scalars(select(Register).where(and_(Register.permissions=='allowed',Register.active==1))).all()
        else:
            registers = db.session.scalars(select(Register).where(and_(Register.permissions=='allowed',Register.active==1,Register.alias==reg[0]))).all()
    
        #fn.append(Note.register.any(Register.alias.in_(registers)))
        fn.append(Note.register_id.in_([reg.id for reg in registers]))

        if reg[0] == 'mat':
            if not session['showAll']:
                fn.append(Note.state<6)
        
            fmt = []
            fmt.append(and_(Note.state == 1,Note.next_in_matters(current_user)))
            fmt.append(Note.contains_read(current_user.alias))
            fmt.append(Note.sender.has(User.id==current_user.id))
            fn.append(or_(*fmt))
        else:
            if reg[1] == 'pen':
                fn.append(Note.receiver.any(User.id==current_user.id))
                if not session['showAll']:
                    fn.append(Note.state<6)
            else:
                fn.append(Note.flow==reg[1])
                if not session['showAll'] and reg[1] == 'in':
                    fn.append(Note.state<6)
            
        if not 'permanente' in current_user.groups:
            fn.append( or_(Note.permanent==False,Note.sender.has(User.id==current_user.id),Note.receiver.any(User.id==current_user.id)) )

    # Find filter in fullkey, sender, receivers or content
    if filter:
        ft = filter
        
        tags = re.findall(r'#\w+',ft)
        ft = re.sub(r'#\w+','',ft).strip()
        tfn = []

        for tag in tags:
            tfn.append(Note.contains_tag(tag.replace('#','').strip()))
       
        senders = re.findall(r'@\w+',ft)
        ft = re.sub(r'@\w+','',ft).strip()
        sfn = []

        for sender in senders:
            alias = sender.replace('@','').strip()
            sfn.append( or_(Note.sender.has(User.alias==alias),Note.receiver.any(User.alias==alias)) )
 
        ofn = []
        if ft != "":
            ofn.append( Note.content.contains(ft) )
            ofn.append( Note.sender.has(User.alias==ft) )
            ofn.append( Note.receiver.any(User.alias==ft) )
            

            rst = re.findall(r'\b[a-zA-Z-]* \b\d+\/\d+\b',ft)
            if rst:
                for r in rst:
                    alias = re.search(r'\b[a-zA-Z-]*\b',r).group().replace('-Aes','')
                    nums = re.findall(r'\d+',r)
                    if db.session.scalar(select(User).where(User.alias==alias)):
                        ofn.append(and_(Note.sender.has(User.alias==alias),Note.num==nums[0],Note.year==2000+int(nums[1])))
                    else:
                        ofn.append(and_(Note.num==nums[0],Note.year==2000+int(nums[1])))
            else:
                rst = re.findall(r'\b\d+\/\d+\b',ft)
                if rst:
                    for r in rst:
                        nums = re.findall(r'\d+',r)
                        ofn.append(and_(Note.num==nums[0],Note.year==2000+int(nums[1])))
                else:
                    rst = re.findall(r'\b\d+\b',ft)
                    if rst:
                        for r in rst:
                            ofn.append(Note.num==r)

                    
        fn.append( and_( *sfn,*tfn,or_(*ofn) ) )

    return fn


def get_notes(reg, filter = ""):
    sender = aliased(User,name="sender_user")
    sql = select(Note).join(Note.sender.of_type(sender))
    
    fn = register_filter(reg,filter)
    if reg[2] == "" and reg[1] == "out":
        sql = sql.where(and_(*fn)).order_by(Note.year.desc(),Note.num.desc())
    elif reg[0] == "mat":
        sql = sql.where(and_(*fn)).order_by(Note.matters_order,Note.date.desc(),Note.num.desc())
    else:
        sql = sql.where(and_(*fn)).order_by(Note.date.desc(), Note.id.desc())
   
    notes = db.paginate(sql, per_page=22)
    

    return notes

def action_note_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    newNote(current_user,reg)

    return body_table_view(request)

def dashboard_view(request):
    registers = db.session.scalars(select(Register).where(Register.active==1)).all()
    return render_template('new/dashboard.html', registers=registers)

def body_table_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    showAll = request.args.get('showAll')
    output = request.form.to_dict()
    page = request.args.get('page', 1, type=int)

    if showAll == 'toggle':
        session['showAll'] = not session['showAll']

    notes = get_notes(reg,filter = output['search'] if 'search' in output else '')
        
    return render_template('new/table/table.html', notes=notes, reg=reg)

def main_body_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    print(reg)
    dark = '-dark' if session['theme'] == 'dark-mode' else ''
    
    title = {}
    title['filter'] = False
    title['showAll'] = False
    title['new'] = False

    if reg[1] == 'pen':
        title['icon'] = f'static/icons/00-pendings{dark}.svg' 
        title['text'] = gettext(u'Pending')
        title['filter'] = True
        title['showAll'] = True
    elif reg[0] == 'des':
        title['icon'] = f'static/icons/00-despacho{dark}.svg' 
        title['text'] = gettext(u'Despacho')
    elif reg[0] == 'box' and reg[1] == 'out':
        title['icon'] = f'static/icons/00-outbox{dark}.svg' 
        title['text'] = gettext(u'Outbox cr')
    elif reg[2] != '':
        title['icon'] = f'static/icons/ctr/{reg[2]}-{reg[1]}.svg' 
        if reg[1] == 'in': # Notes from cr to ctr
            title['text'] = f"{gettext('Notes from cr to')} {reg[2]}"
            title['showAll'] = True
        else:
            title['text'] = f"{gettext('Notes from')} {reg[2]} {gettext('to cr')}"
            title['new'] = True
        title['filter'] = True
    elif reg[0] == 'all':
        title['icon'] = f'static/icons/sake.svg' 
        title['text'] = gettext(u'Note history')
    elif reg[0] == 'mat':
        title['icon'] = f'static/icons/00-minutas{dark}.svg' 
        title['text'] = gettext(u'Matters')
        title['filter'] = True
        title['showAll'] = True
        title['new'] = True
    else:
        title['icon'] = f'static/icons/ctr/{reg[0]}-{reg[1]}.svg'
        title['text'] = f"{reg[0]} {reg[1]}"
        title['filter'] = True

        if reg[1] == 'in':
            title['showAll'] = True
        else:
            title['new'] = True

    notes = get_notes(reg)
    
    return render_template('new/body.html',title=title, notes=notes, reg=reg)
