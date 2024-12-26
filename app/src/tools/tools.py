#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

from sqlalchemy import select, func, literal_column, and_
from sqlalchemy.orm import aliased

from flask import session, current_app
from flask_babel import gettext
from flask_login import current_user

from app import db
from app.src.models import User, Note, Register, NoteStatus, Group

from app.src.tools.mail import send_email, send_emails

def toNewNotesStatus():

    users = db.session.scalars(select(User)).all()
    ctrs = db.session.scalars(select(User).where(User.contains_group('ctr'))).all()
    registers = db.session.scalars(select(Register)).all()
    groups = db.session.scalars(select(Group)).all()

    for user in users:
        user.set_setting('password',user.password)
        user.set_setting('password_nas',user.password_nas)

        if 'notifications' in user.groups:
            user.set_setting('notifications',True)

        if 'of' in user.u_groups.split(','):
            user.category = 'of'
            for reg in registers:
                if 'despacho' in reg.groups:
                    reg.set_user_access('viewer',user)
                elif reg.alias == 'mat':
                    reg.set_user_access('viewer_contact',user)
                elif f'e_{reg.alias}' in user.groups:
                    reg.set_user_access('editor',user)
        elif 'cr' in user.u_groups.split(','):
            user.category = 'dr'
            for reg in registers:
                if 'despacho' in reg.groups:
                    reg.set_user_access('reader',user)
                elif reg.alias == 'mat':
                    reg.set_user_access('viewer_contact',user)
                elif f'e_{reg.alias}' in user.groups:
                    reg.set_user_access('editor',user)
        elif 'ctr' in user.u_groups.split(','):
            print('user:',user.alias)
            user.category = 'ctr'
            for reg in registers:
                if reg.alias == 'ctr':
                    reg.set_user_access('contact',user)
        elif 'sake' in user.u_groups.split(','):
            user.category = 'cl'
        else:
            user.category = 'contact'
            for reg in registers:
                if f'ct_{reg.alias}' in user.groups:
                    reg.set_user_access('contact',user)
        
        for ctr in ctrs:
            if f'v_ctr_{ctr.alias}' in user.groups:
                if not ctr in user.ctrs:
                    user.ctrs.append(ctr)

        for user_group in user.u_groups.split(','):
            for group in groups:
                if group.text.lower() == user_group:
                    user.add_group(group.text)
        
        db.session.commit()



def nextNumReg(rg,target=None):
    # Get new number for the note. Here getting the las number in that register
    sender = aliased(User,name="sender_user")
    if rg[0] == 'mat':
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg=='mat',Note.year==datetime.today().year,Note.sender.has(User.id==current_user.id)))) )
    elif rg[0] == 'vc' and target == 'asr':
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(Note.num>250,Note.reg==rg[0],Note.year==datetime.today().year,Note.flow=='out')) )
    elif rg[2]:
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.year==datetime.today().year,literal_column(f"sender_user.alias = '{rg[2]}'"),Note.flow=='in'))) )
    else:
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg==rg[0],Note.year==datetime.today().year,Note.flow=='out'))) )
    
    # Now adding +1 to num or start numeration of the year
    if num:
        num += 1
    elif rg[2]:
        num = 1
    elif rg[0] == 'cg':
        num = 1
    elif rg[0] == 'asr' or rg[0] == 'vc' and target == 'asr':
        num = 250
    elif rg[0] == 'ctr':
        num = 1000
    elif rg[0] == 'r':
        num = 2000
    else: # it is a ctr making the first note of the year
        num = 1

    return num

def delete_note(note_id):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    for file in note.files:
        db.session.delete(file)
    
    for ref in note.ref:
        note.ref.remove(ref)
    
    for comment in note.comments_ctr:
        db.session.delete(comment)

    #for rec in note.receiver:
    #    note.receiver.remove(rec)

    for status in note.status:
        db.session.delete(status)
    
    db.session.commit()

    note.delete_folder()

    db.session.delete(note)
    db.session.commit()


def newNote(user, reg, ref = None, target = None):
    num = nextNumReg(reg,target)
    
    register = db.session.scalar(select(Register).where(Register.alias==reg[0]))

    # Creating the note. We need to know the register it bellows. This note could have been created by a cr dr or a cl member
    if reg[2]: # New note made by a cl member. It's a note for cr from ctr 
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        nt = Note(num=num,sender_id=ctr.id,reg=reg[0],register=register)
    else: # Note created by a cr dr
        nt = Note(num=num,sender_id=user.id,reg=reg[0],register=register)
   
    if reg[0] == 'vc' and target == 'asr':
        asr = db.session.scalar(select(User).where(User.alias==target))
        nt.receiver.append(asr)
    
    contacts = register.get_contacts()
    if len(contacts) == 1: # There is only one possibility I add it from the beginning
        nt.receiver.append(contacts[0])

    if ref:
        if type(ref) == Note:
            if nt.register.alias == 'mat':
                nt.content = f"{ref.content}"
                nt.content_jp = f"{ref.content_jp}"
            else:
                nt.content = f"Re: {ref.content}" if ref.content else ''
                nt.content_jp = f"件名: {ref.content_jp}" if ref.content_jp else ''
            nt.n_tags = ref.n_tags
            
            if nt.register.alias == 'mat':
                rb = []
                for rec in ref.receiver:
                    if rec != current_user and 'sake' in rec.groups:
                        rb.append(rec.alias)
                nt.received_by = ','.join([r for r in rb if r])
            if ref.register.alias == 'mat':
                if ref.ref:
                    nt.ref = ref.ref + [ref]
                    if ref.ref[0].register == register:
                        if f'ct_{register.alias}' in ref.ref[0].sender.groups:
                            nt.receiver.append(ref.ref[0].sender)
                else:
                    nt.ref.append(ref)
            else:
                nt.ref.append(ref)
        else:
            for irf in ref.split(","):
                rf = db.session.scalar(select(Note).where(Note.id==irf))
                if rf.reg == 'mat':
                    for r in rf.ref:
                        nt.ref.append(r)
                else:
                    nt.ref.append(rf)

    db.session.add(nt)
    rst = db.session.commit()

def sendmail(note_id=None):
    if note_id:
        tosendnotes = db.session.scalars(select(Note).where(Note.id==note_id))
    else:
        tosendnotes = db.session.scalars(select(Note).where(and_(Note.flow=='out',Note.state==1,Note.reg!='mat')))
    
    for nt in tosendnotes:
        if not 'personal' in nt.register.groups: # Only for not personal calendars
            if nt.state < 6: #If the state is already 6 then the notes have already been moved
                if not nt.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{nt.year}/{nt.reg} out"):
                    continue

        if 'folder' in nt.register.groups: # Note for asr. We just copy it to the right folder
            nt.copy(f"/team-folders/Mail {nt.register.alias}/Mail to {nt.register.alias}") # I have to add this to the register database!!!!! Pending
            nt.state = 6
        
        if 'sake' in nt.register.groups: # note for a ctr (internal sake system). We just change the state.
            nt.state = 6
            send_emails(nt)

        db.session.commit()

