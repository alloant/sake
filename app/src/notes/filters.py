#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re
from datetime import datetime

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



def get_history(note):
    nt = db.session.scalar(select(Note).where(Note.id==note))
    refs = [note]
    for ref in nt.ref:
        refs.append(ref.id)

    notes = ",".join([str(r) for r in refs])
    
    sql = text(
            f"wit  h recursive R as ( \
            select note_id as n, ref_id as r from note_ref where note_id in ({notes}) or ref_id in ({notes}) \
            UNION \
            select note_ref.note_id,note_ref.ref_id from R,note_ref where note_ref.note_id = R.r or note_ref.ref_id in (R.n,R.r) or note_ref.note_id in (R.n,R.r)\
            ) \
            select n,r from R"
        )

    d_nids = db.session.execute(sql).all()

    nids = [note]
    for nid in d_nids:
        nids += nid

    nids = list(set(nids))

    return db.session.scalars( select(Note).where(Note.id.in_(nids)).order_by(Note.date.desc(), Note.id.desc()) ).all()

def register_filter(reg,filter = ""):
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
    elif reg[0] == 'box' and reg[1] == 'in': # Es outbox
        fn.append(Note.reg!='mat')
        fn.append(Note.flow=='in')
        fn.append(Note.state==1)
    elif reg[2]: # Es un subregister
        register = db.session.scalar(select(Register).where(Register.alias==reg[0]))
        fn.append(Note.register_id==register.id)
        if reg[1] == 'in':
            fn.append(Note.state==6)
            fn.append(Note.receiver.any(User.alias==reg[2]))
        elif reg[1] == 'out':
            fn.append(Note.sender.has(User.alias==reg[2]))
    
        #if not session['showAll'] and reg[1] == 'in':
        if session['filter_option'] == 'hide_archived' and reg[1] == 'in':
            ctr_fn = db.session.scalar(select(User).where(User.alias==reg[2]))
            fn.append(Note.is_done(ctr_fn))
    else: # Es un register
        if reg[0] == 'all': # Here I get all notes from all registers
            if current_user.admin:
                registers = db.session.scalars(select(Register).where(Register.active==1)).all()
            else:
                registers = db.session.scalars(select(Register).where(and_(Register.permissions=='allowed',Register.active==1))).all()
        else:
            registers = db.session.scalars(select(Register).where(and_(Register.permissions=='allowed',Register.active==1,Register.alias==reg[0]))).all()
    
        #fn.append(Note.register.any(Register.alias.in_(registers)))
        fn.append(Note.register_id.in_([reg.id for reg in registers]))

        if reg[0] == 'mat':
            if session['filter_option'] == 'hide_archived':
                fn.append(Note.state<6)
 
            fmt = []
            fmt.append(and_(Note.state == 1,Note.next_in_matters(current_user.alias)))
            fmt.append(Note.contains_read(current_user.alias))
            fmt.append(Note.sender.has(User.id==current_user.id))
            fn.append(or_(*fmt))
        elif reg[0] == 'all' and reg[1] == 'all':
            if session['filter_option'] == 'only_notes':
                fn.append(Note.reg!='mat')
            elif session['filter_option'] == 'only_proposals':
                fn.append(Note.reg=='mat')
            if not current_user.admin:
                fn.append(Note.state>4)
        else:
            if reg[1] == 'pen':
                fmt = []
                fmt.append(and_(Note.state == 1,Note.next_in_matters(current_user.alias)))
                fmt.append(Note.sender.has(User.id==current_user.id))

                fsrn = []
                fsrn.append(Note.sender_id==current_user.id)
                fsrn.append(and_(Note.receiver.any(User.id==current_user.id),Note.state > 4))
                fsr = []
                fsr.append(and_(or_(*fsrn),Note.reg != 'mat'))
                fsr.append(and_(Note.reg == 'mat',or_(*fmt)))
                fn.append(or_(*fsr))

                if session['filter_option'] == 'hide_archived':
                    fn.append(Note.state<6)
            else:
                fn.append(Note.flow==reg[1])
                if reg[1] == 'in':
                    fn.append(Note.state >= 5)
                else:
                    fn.append(or_(Note.sender.has(User.id==current_user.id),Note.state == 6))
            
        if not 'permanente' in current_user.groups:
            fn.append( or_(Note.permanent==False,Note.sender.has(User.id==current_user.id),Note.receiver.any(User.id==current_user.id)) )

    # Find filter in fullkey, sender, receivers or content
    if filter:
        ft = filter
        
        tags = re.findall(r'#[^ ]*',ft)
        ft = re.sub(r'#[^ ]*','',ft).strip()
        tfn = []

        for tag in tags:
            tfn.append(Note.contains_tag(tag.replace('#','').strip()))
       
        senders = re.findall(r'@[^ ]*',ft)
        ft = re.sub(r'@[^ ]*','',ft).strip()
        sfn = []
        
        for sender in senders:
            alias = sender.replace('@','').strip()
            if reg[0] == 'mat' and alias == current_user.alias:
                sfn.append( Note.sender.has(User.alias==alias) )
            else:
                sfn.append( or_(Note.sender.has(User.alias==alias),Note.receiver.any(User.alias==alias)) )

        files = re.findall(r'file:\w+(?:[.-]\w+)*',ft)
        ft = re.sub(r'file:\w+(?:[.-]\w+)*','',ft).strip()
        ft_files = []
        for file in files:
            ft_files.append(Note.files.any(File.path.contains(file[5:])))

        flows = re.findall(r'flow:[^ ]*',ft)
        ft = re.sub(r'flow:[^ ]*','',ft).strip()
        ft_flows = []
        for flow in flows:
            ft_flows.append(Note.flow==flow[5:])

        dates = re.findall(r'date:[^ ]*',ft)
        ft = re.sub(r'date:[^ ]*','',ft).strip()
        ft_dates = []
        for ddt in dates:
            dt = ddt[5:]
            if '-' in dt:
                dts = dt.split('-')
                try:
                    ft_dates.append(Note.n_date>=datetime.strptime(dts[0],'%d/%m/%Y'))
                    ft_dates.append(Note.n_date<=datetime.strptime(dts[1],'%d/%m/%Y'))
                except:
                    pass
            else:
                try:
                    ft_dates.append(Note.n_date==datetime.strptime(dt,'%d/%m/%Y'))
                except:
                    pass

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

                    
        fn.append( and_( *ft_flows,*ft_dates,*ft_files,*sfn,*tfn,or_(*ofn) ) )
    
    return fn

def get_title(reg):
    dark = '-dark' if session['theme'] == 'dark-mode' else ''
    title = {}
    title['filter'] = False
    title['showAll'] = False
    title['sendmail'] = False
    title['mail_to_despacho'] = False
    title['new'] = False

    if reg[1] == 'pen':
        title['icon'] = f'static/icons/00-pendings{dark}.svg' 
        title['text'] = gettext(u'Pending notes and proposals')
        title['filter'] = True
        title['showAll'] = True
    elif reg[0] == 'import':
        title['icon'] = f'static/icons/00-import{dark}.svg' 
        title['text'] = gettext(u'Import files into Sake')
    elif reg[0] == 'des':
        title['icon'] = f'static/icons/00-despacho{dark}.svg' 
        title['text'] = gettext(u'Despacho')
    elif reg[0] == 'box' and reg[1] == 'out':
        title['icon'] = f'static/icons/00-outbox{dark}.svg' 
        title['text'] = gettext(u'Outbox cr')
        title['sendmail'] = True
    elif reg[0] == 'box' and reg[1] == 'in':
        title['icon'] = f'static/icons/00-inbox{dark}.svg' 
        title['text'] = gettext(u'Inbox cr')
        title['mail_to_despacho'] = True
    elif reg[0] == 'all' and reg[1] == 'all':
        title['icon'] = f'static/icons/00-search{dark}.svg' 
        title['text'] = gettext(u'Search in all notes and proposals')
        title['filter'] = True
        title['showAll'] = True
    elif reg[2]:
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
        title['icon'] = f'static/icons/00-matters{dark}.svg' 
        title['text'] = gettext(u'Proposals')
        title['filter'] = True
        title['showAll'] = True
        title['new'] = True
    else:
        title['icon'] = f'static/icons/ctr/{reg[0]}-{reg[1]}.svg'
        title['text'] = f"{reg[0]} {reg[1]}"
        title['filter'] = True

        if reg[1] == 'out':
            title['new'] = True
    
    return title

def get_notes(reg,filter = ""):
    sender = aliased(User,name="sender_user")
    sql = select(Note).join(Note.sender.of_type(sender))
    
    fn = register_filter(reg,filter)
     
    if not reg[2] and reg[1] == "out":
        sql = sql.where(and_(*fn)).order_by(Note.year.desc(),Note.num.desc())
    elif reg[0] == 'mat' or reg[1] == 'pen':
        sql = sql.where(and_(*fn)).order_by(Note.matters_order,Note.date.desc(),Note.num.desc())
    else:
        sql = sql.where(and_(*fn)).order_by(Note.date.desc(), Note.id.desc())
  
    notes = db.paginate(sql, per_page=22)

    return notes



