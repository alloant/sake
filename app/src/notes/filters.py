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
from app.src.models import Note, User, Register, File, NoteUser, Group
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
            f"with recursive R as ( \
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

    return db.paginate(select(Note).where(Note.id.in_(nids)).order_by(Note.date.desc(), Note.id.desc()), per_page=25)

def register_filter(reg,filter = ""):
    fn = []
    # First filter register notes. Diving for ctr or the rest
    if reg[0] == 'des': # Es despacho
        fn.append(Note.reg!='mat')
        fn.append(Note.flow=='in')
        fn.append(Note.result('num_sign_despacho')<2)
        fn.append(Note.register.has(Register.groups.any(Group.text=='despacho')))
        fn.append(Note.status == 'despacho')
    elif reg[0] == 'box' and reg[1] == 'out': # Es outbox
        fn.append(Note.reg!='mat')
        fn.append(Note.flow=='out')
        fn.append(Note.status=='queued')
    elif reg[0] == 'box' and reg[1] == 'in': # Es outbox
        fn.append(Note.reg!='mat')
        fn.append(Note.flow=='in')
        fn.append(Note.status=='queued')
    elif reg[2]: # Es un subregisterde un ctr
        register = db.session.scalar(select(Register).where(Register.alias==reg[0]))
        fn.append(Note.register_id==register.id)
        if reg[1] == 'in':
            fn.append(Note.status.in_(['sent']))
            fn.append(Note.users.any(NoteUser.user.has(User.alias==reg[2])))
            
            if session['filter_option'] == 'hide_archived':
                ctr_fn = db.session.scalar(select(User).where(User.alias==reg[2]))
                fn.append(not_(Note.result('is_done',ctr_fn)))
        elif reg[1] == 'out':
            fn.append(Note.sender.has(User.alias==reg[2]))
    else: # Es un register
        if reg[0] == 'all': # Here I get all notes from all registers
            if current_user.admin:
                fn.append(Note.register.has(Register.active==1))
            else:
                fn.append(Note.register.has(and_(Register.active==1,Register.permissions!='')))
        else:
            fn.append(Note.register.has(and_(Register.active==1,Register.permissions!='',Register.alias==reg[0])))
    
        if reg[0] == 'mat':
            if session['filter_option'] == 'hide_archived':
                fn.append(not_(Note.archived))
 
            
            ## Proposals I have to do or I have done and are not over
            fn.append(Note.reg=='mat')
            fmt_t = []
            fmt_t.append(Note.result('is_target'))
            fmt_t.append(or_(
                Note.status.in_(['approved','denied']),
                and_(Note.status=='shared',or_(Note.result('is_done'),Note.current_target_order==Note.result('target_order')))
            ))
            fn.append(or_(
                Note.sender.has(User.id==current_user.id),
                and_(*fmt_t)
            ))

        elif reg[0] == 'all' and reg[1] == 'all': # Global search
            if session['filter_option'] == 'only_notes':
                fn.append(Note.reg!='mat')
            elif session['filter_option'] == 'only_proposals':
                fn.append(Note.reg=='mat')
            if not current_user.admin:
                fn.append(Note.status.in_(['registered','approved','sent']))
        else:
            if reg[1] == 'pen':
                fmt_t = []
                fmt_t.append(Note.result('is_target'))
                fmt_t.append(or_(
                    Note.status.in_(['approved','denied']),
                    and_(Note.status=='shared',or_(Note.result('is_done'),Note.current_target_order==Note.result('target_order')))
                ))


                fsrn = []
                fsrn.append(Note.sender_id==current_user.id)
                fsrn.append(and_(Note.has_target(current_user.id),Note.result('num_sign_despacho') > 1))
                fsrn.append(Note.register.has(and_(Register.permissions=='allowed',Register.groups.any(Group.text=='personal'))))
                
                fsr = []
                fsr.append(and_(Note.reg != 'mat', or_(*fsrn)))
                fsr.append(and_(Note.reg == 'mat', or_(Note.sender.has(User.id==current_user.id),and_(*fmt_t))))
                
                fn.append(or_(*fsr))

                if session['filter_option'] == 'hide_archived':
                    fn.append(not_(Note.archived))
                    fn.append(not_(Note.status!='sent'))
                    fn.append(or_(
                        Note.reg!='mat',
                        and_(Note.reg=='mat',not_(Note.result('is_done')))
                    ))
            else:
                fn.append(Note.flow==reg[1])
                if reg[1] == 'in':
                    fn.append(
                        or_(
                            Note.register.has(
                                and_(
                                    Register.permissions,
                                    Register.groups.any(Group.text == 'personal')
                                )
                            ),
                            Note.status=='registered'))
                else:
                    fn.append(or_(Note.sender.has(User.id==current_user.id),Note.status == 'sent'))
            
        if not 'Permanente' in current_user.groups:
            fn.append( or_(Note.permanent==False,Note.sender.has(User.id==current_user.id),Note.has_target(current_user.id) ))

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
                sfn.append( or_(Note.sender.has(User.alias==alias),Note.users.any(NoteUser.user.has(User.alias==alias))) )

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
            ofn.append( Note.has_target(ft) )
            

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
    elif reg[0] == 'mat' or reg[1] == 'pen' and session['filter_option'] == 'hide_archived':
        sql = sql.where(and_(*fn)).order_by(Note.matters_order,Note.date.desc(),Note.num.desc())
    else:
        sql = sql.where(and_(*fn)).order_by(Note.date.desc(), Note.id.desc())
     
    notes = db.paginate(sql, per_page=25)

    return notes



