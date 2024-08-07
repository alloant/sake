#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re

from flask import render_template, session, make_response
from flask_login import current_user

from sqlalchemy import select, and_, or_, func
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased

from flask_babel import gettext

from app import db
from app.src.models import Note, User, Register, File
from app.src.forms.note import NoteForm
from app.src.notes.edit import fill_form_note, extract_form_note

from app.src.tools.tools import newNote, sendmail, delete_note

def body_table_view(request): 
    reg = ast.literal_eval(request.args.get('reg'))
    showAll = request.args.get('showAll','')
    output = request.form.to_dict()
    page = request.args.get('page', 1, type=int)
    session['page'] = page
    session['reg'] = reg

    if showAll == 'toggle':
        session['showAll'] = not session['showAll'] if 'showAll' in session else False
    else: 
        if not 'page' in request.args:
            if 'search' in output:
                session['filter_notes'] = output['search']
            else:
                session['filter_notes'] = ''

    notes = get_notes(reg,filter = session['filter_notes'] if 'filter_notes' in session else '')

    return render_template('notes/table.html', notes=notes, page=page, reg=reg)

def table_body_view(request):
    if 'reg' in session:
        page = 1 if not 'page' in session else session['page']
        if isinstance(session['reg'][1],int):
            notes = get_history(session['reg'][1])
        else:
            notes = get_notes(session['reg'],filter = session['filter_notes'] if 'filter_notes' in session else '')
    
        return render_template('notes/table_body.html', notes=notes, page=page, reg=session['reg'])

    return ""

def main_body_view(request):
    reg = request.args.get('reg','')
    
    if not 'showAll' in session:
        session['showAll'] = False
    session['filter_notes'] = ''

    if reg:
        reg = ast.literal_eval(reg)
        session['reg'] = reg
    else:
        if 'reg' in session:
            reg = session['reg']
        else:
            if 'cr' in current_user.groups:
                reg = ['all','pen','']
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
   
    if reg[2]:
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        session['ctr'] = {'alias': ctr.alias, 'date': ctr.date.strftime('%Y-%m-%d')}

    title = get_title(reg) 

    if isinstance(reg[1],int):
        notes = get_history(reg[1])
    else:
        notes = get_notes(reg)
    
    return render_template('notes/main.html',title=title, notes=notes, reg=reg)



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
                fmt = []
                fmt.append(and_(Note.state == 1,Note.next_in_matters(current_user)))
                #fmt.append(Note.contains_read(current_user.alias))
                fmt.append(Note.sender.has(User.id==current_user.id))
                fn.append(or_(and_(Note.state >= 5,or_(Note.sender_id==current_user.id,Note.receiver.any(User.id==current_user.id)),Note.reg != 'mat'),and_(Note.reg == 'mat',or_(*fmt))))

                if not session['showAll']:
                    fn.append(Note.state<6)
            else:
                fn.append(Note.flow==reg[1])
                if reg[1] == 'in':
                    fn.append(Note.state >= 5)
                else:
                    fn.append(or_(Note.sender.has(User.id==current_user.id),Note.state == 6))
                #if not session['showAll'] and reg[1] == 'in':
                #    fn.append(Note.state<6)
            
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
            if reg[0] == 'mat' and alias == current_user.alias:
                sfn.append( Note.sender.has(User.alias==alias) )
            else:
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

def get_title(reg):
    dark = '-dark' if session['theme'] == 'dark-mode' else ''
    title = {}
    title['filter'] = False
    title['showAll'] = False
    title['sendmail'] = False
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
        title['sendmail'] = True
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
        title['text'] = gettext(u'Matters')
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
    elif reg[0] == "mat":
        sql = sql.where(and_(*fn)).order_by(Note.matters_order,Note.date.desc(),Note.num.desc())
    else:
        sql = sql.where(and_(*fn)).order_by(Note.date.desc(), Note.id.desc())
  
    notes = db.paginate(sql, per_page=22)

    return notes

def visibility_note_form(reg,note):
    dnone = {'admin':'d-none','permanent':'d-none','date':'d-none','proc':'d-none','content':'d-none','content_jp':'d-none','comments':'d-none','comments_ctr':'d-none','ref':'d-none','rec':'d-none'}

    if reg[2]: # Note in a register of a ctr
        if note.flow == 'out': # Not IN for the ctr, only comments
            dnone['comments_ctr'] = ''
        else:
            dnone['date'] = ''
            dnone['content'] = ''
            dnone['content_jp'] = ''
            dnone['ref'] = ''
    else: # Everything else
        if current_user.admin:
            dnone['admin'] = ''
        
        if note.register.alias == 'mat' and (note.sender_id == current_user.id or current_user.admin):
            dnone['proc'] = ''

        if note.sender_id == current_user.id or 'despacho' in current_user.groups or current_user.admin: # My note, I can change everything
            dnone['permanent'] = ''
            dnone['date'] = ''
            dnone['content'] = ''
            dnone['content_jp'] = ''
            dnone['comments'] = ''
            dnone['ref'] = ''
            dnone['rec'] = ''

    return dnone

def action_note_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    action = request.args.get('action')
    
    match action:
        case 'new':
            newNote(current_user,reg)
        case 'sendmail':
            sendmail()
        case 'delete_note':
            note_id = request.args.get('note')
            delete_note(note_id)
        case 'edit_note':
            note_id = request.args.get('note')
            note = db.session.scalar(select(Note).where(Note.id==note_id))
            output = request.form.to_dict()
            
            filter = output['search'] if 'search' in output else ''
            
            form = NoteForm(request.form,obj=note)
            form = fill_form_note(reg,form,note,filter)

            despacho = True if reg[0] == 'des' else False

            return render_template('modals/modal_edit_note.html',note=note,form=form, reg=reg, dnone=visibility_note_form(reg,note), despacho=despacho)
        case 'edited':
            note_id = request.args.get('note')
            note = db.session.scalar(select(Note).where(Note.id==note_id))
            
            form = NoteForm(request.form,obj=note)
            extract_form_note(reg,form,note)
            
            return note_row_view(request)
    
    res = make_response(body_table_view(request))
    res.headers['HX-Trigger'] = 'update-flash'

    return res

def note_row_view(request):
    
    reg = ast.literal_eval(request.args.get('reg'))
     
    note_id = request.args.get('note')
    
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    if reg[2]:
        return render_template('notes/table_row_subregister.html',note=note, reg=reg, user=current_user)
    else:
        return render_template('notes/table_row.html',note=note, reg=reg, user=current_user)


   
def register_icon_view (request):
    register = request.args.get('reg')
    if register == 'menu_register':
        return render_template('sidebar_menu_register.html')
    else:
        return current_user.register_icon_html(register)
