#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re

from flask import render_template, url_for, session, redirect, current_app
from flask_login import current_user

from sqlalchemy import select, and_, or_, literal_column
from sqlalchemy.orm import aliased
from sqlalchemy.sql import text

from app import db
from app.models import Note, User, Register
from app.mail import send_email
from app.syneml import write_eml

from .tools import view_title, newNote

def find_history(note):
    if note:
        session['note'] = note
    else:
        note = session['note']

    sql = text(
            f"with recursive R as ( \
            select note_id as n, ref_id as r from note_ref where note_id = {note} or ref_id = {note} \
            UNION \
            select note_ref.note_id,note_ref.ref_id from R,note_ref where note_ref.note_id = R.r or note_ref.ref_id = R.n \
            ) \
            select n,r from R"
        )

    d_nids = db.session.execute(sql).all()

    nids = [note]
    for nid in d_nids:
        nids += nid

    nids = list(set(nids))

    return Note.id.in_(nids)


def register_filter(rg,h_note = None):
    fn = []

    if rg[0] == 'mat':
        fn.append(Note.reg=='mat')
        if not session['showAll']:
            fn.append(Note.state < 6)
        
        omt = []
        omt.append(and_(Note.state == 1,Note.next_in_matters(current_user)))
        omt.append(Note.contains_read(current_user.alias))
        omt.append(Note.sender.has(User.id==current_user.id))

        fn.append(or_(*omt))
    elif rg[0] == 'des':
        fn.append(Note.reg!='mat')
        fn.append(Note.state>1)
        fn.append(Note.state<5)
    elif rg[0] == 'box':
        fn.append(Note.reg!='mat')
        fn.append(Note.flow=='out')
        fn.append(Note.state==1)
    elif rg[2] in ['','pending']: # Register not for cls
        # First no permanentes
        if not 'permanente' in current_user.groups:
            fn.append(Note.permanent==False)
        
        # For pendings and for the rest
        if rg[2] == 'pending':
            fn.append(or_( Note.sender.has(User.id==current_user.id), Note.receiver.any(User.id==current_user.id) ))
            if not session['showAll']:
                fn.append(Note.state < 6)
        else:
            fn.append(or_( Note.state>=5,Note.sender.has(User.id==current_user.id) )) # Only notes with state >= 5 or the ones with sender = current_user

        # Registers involve. One in particular or all the ones I can see.
        if rg[0] == 'all':
            fn.append(Note.register_id.in_([reg.id for reg in current_user.all_registers])) # No minutas
        else:
            register = db.session.scalar(select(Register).where(Register.alias==rg[0]))
            fn.append(Note.register==register)

        # Flow of the notes. If all no filter needed
        if rg[1] != 'all':    
            fn.append(Note.flow==rg[1])

        # For the history of the note
        if h_note:
            fn.append(find_history(h_note)) 

    elif rg[2] != '': # The register of a center
        register = db.session.scalar(select(Register).where(Register.alias==rg[0]))
        fn.append(Note.register==register)
        
        if rg[1] == 'in': # show notes to the ctr. Flow==out for database
            fn.append(Note.receiver.any(User.alias==rg[2]))
            fn.append(Note.state>=5)
            if not session['showAll']:
                ctr_fn = db.session.scalar(select(User).where(User.alias==rg[2]))
                fn.append(Note.is_done(ctr_fn))
        else:
            fn.append(Note.sender.has(User.alias==rg[2]))
    
    # Find filter in fullkey, sender, receivers or content
    if 'filter_notes' in session:
        ft = session['filter_notes']
        tags = re.findall(r'#\w+',ft)
        ft = re.sub(r'#\w+','',ft)
        ofn = []
        for tag in tags:
            ofn.append(Note.contains_tag(tag.replace('#','').strip()))

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

                    
        fn.append(or_(*ofn))

    return fn

def register_actions(output,args): # Actions like new note, update read/state, update files...
    note = args.get('note')
    reg = args.get('reg')
    page = args.get('page')
    rg = reg.split("_")

    # If the note was mark read
    read_id = args.get('read')
    if read_id:
        nt = db.session.scalar(select(Note).where(Note.id==read_id))
        nt.updateRead(current_user)
        return "lasturl"

    if "newout" in output:
        newNote(current_user,reg)
    elif "addfiles" in output: # To update files in folder
        nt = db.session.scalar(select(Note).where(Note.id==output['addfiles']))
        nt.updateFiles()
    elif 'sendmail' in output: # Only in Outbox. When you click send mail
        tosendnotes = db.session.scalars(select(Note).where(Note.flow=='out',Note.state==1))
        
        for nt in tosendnotes:
            if not 'personal' in nt.register.groups: # Only for not personal calendars
                if not nt.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{nt.year}/{nt.reg} out"):
                    continue

            if 'folder' in nt.register.groups: # Note for asr. We just copy it to the right folder
                nt.copy(f"/team-folders/Mail {nt.register.alias}/Mail to {nt.register.alias}") # I have to add this to the register database!!!!! Pending
                nt.state = 6
            
            if 'sake' in nt.register.groups: # note for a ctr (internal sake system). We just change the state.
                nt.state = 6
                for rec in nt.receiver:
                    if rec.email:
                        send_email(f"New mail for {rec.alias}. {nt.comments}","",rec.email)

            db.session.commit()

    if not "notes_filer" in output and not page:
        session['filter_notes'] = ""
    
def notes_view(output,args):
    reg = args.get('reg')
    page = args.get('page', 1, type=int)


def register_view(template,output,args): # Use for all register in/out for cr and ctr, for pendings, for despacho and for outbox
    note = args.get('note')
    reg = args.get('reg')
    h_note = args.get('h_note')
    
    rg = reg.split("_") if reg else [""]

    # Sending to last url
    if reg == 'lasturl':
        return redirect(session['lasturl'])

    # Init this value if needed
    if not "filter_notes" in session:
        session["filter_notes"] = ""
    
    if not "showAll" in session:
        session["showAll"] = False
 
    # Security check for error and users without authority
    rdct = False
    
    if rg[0] != 'all':
        register = db.session.scalar(select(Register).where(Register.alias==rg[0]))
        
        if not reg:
            rdct = True
        elif rg[0] == 'mat':
            rdct = False if 'cr' in current_user.groups else True
        elif rg[2] in ['','pending']:
            if register and register.permissions() == 'notallowed' or not reg:
                rdct = True
        else:
            if not rg[2] in register.get_subregisters():
                rdct = True
        
        if rdct:
            if current_user.all_registers:
                return redirect(url_for('register.register', reg='all_all_pending', page=1))

            registers = db.session.scalars(select(Register).where(Register.active==1)).all()
            for register in registers:
                if 'subregister' in register.groups:
                    for sb in register.get_subregisters():
                        return redirect(url_for('register.register', reg=f'{register.alias}_in_{sb}', page=1))
    # Actions
    rst = register_actions(output,args)

    if rst == "lasturl":
        return redirect(session['lasturl'])


    # First check the filter
    if "notes_filter" in output: 
        session['filter_notes'] = output['notes_filter']
        
        if output['notes_filter'] == "":
            if session['showAll']:
                session['showAll'] = False

    if "showAll" in output:
        session['showAll'] = output['showAll']

    fn = register_filter(rg,h_note)

    page = args.get('page', 1, type=int)
    sender = aliased(User,name="sender_user")
    sql = select(Note).join(Note.sender.of_type(sender))
    
    if rg[2] == "" and rg[1] == "out":
        sql = sql.where(and_(*fn)).order_by(Note.year.desc(),Note.num.desc())
    elif rg[0] == "mat":
        sql = sql.where(and_(*fn)).order_by(Note.matters_order,Note.date.desc(),Note.num.desc())
    else:
        sql = sql.where(and_(*fn)).order_by(Note.date.desc(), Note.num.desc())

    ctr = None
    if not rg[2] in ['','pending']:
        ctr = db.session.scalar(select(User).where(User.alias==rg[2]))
        session['ctr'] = {'alias': ctr.alias, 'date': ctr.date.strftime('%Y-%m-%d')}

    notes = db.paginate(sql, per_page=22)
    
    prev_url = url_for('register.register', reg=reg, page=notes.prev_num) if notes.has_prev else None
    next_url = url_for('register.register', reg=reg, page=notes.next_num) if notes.has_next else None
    
    session['lasturl'] = url_for('register.register',reg=reg,page=page)
    registers = db.session.scalars(select(Register).where(Register.active==1)).all()
    #return render_template('register/main.html',title=view_title(reg,note), notes=notes, reg=reg, page=page, prev_url=prev_url, next_url=next_url, user=current_user, ctr=ctr, registers=registers)
    return render_template(template,title=view_title(reg,note), notes=notes, reg=reg, page=page, prev_url=prev_url, next_url=next_url, user=current_user, ctr=ctr, registers=registers)



