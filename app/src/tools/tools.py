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
from app.src.models import User, Note, Register, NoteStatus

from app.src.tools.mail import send_email, send_emails

def toNewNotesStatus():
    notes = db.session.scalars(select(Note).where(Note.reg!='mat')).all()

    for note in notes:
        #Now the receivers
        for rec in note.receiver:
            status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==rec.id))
            if not status:
                status = NoteStatus(note_id=note.id,user_id=rec.id,target=True)
                db.session.add(status)
            else:
                status.target = True

        for alias in note.read_by.split(','):
            if alias[:4] == 'des_' and note.flow == 'in':
                user = db.session.scalar(select(User).where(User.alias==alias[4:]))
                if not user:
                    continue
                status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==user.id))
                if not status:
                    status = NoteStatus(note_id=note.id,user_id=user.id,sign_despacho=True)
                    db.session.add(status)
                else:
                    status.sign_despacho = True
            else:
                user = db.session.scalar(select(User).where(User.alias==alias))
                if not user:
                    continue
                status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==user.id))
                if not status:
                    status = NoteStatus(note_id=note.id,user_id=user.id,read=True)
                    db.session.add(status)
                else:
                    status.read = True

        #Here the is_done for the ctr which is kept in recevied_by
        for alias in note.received_by.split(','):
            user = db.session.scalar(select(User).where(User.alias==alias)) #Esto es un ctr
            if not user:
                continue
            status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==user.id))
            if not status:
                status = NoteStatus(note_id=note.id,user_id=user.id,target_acted=True)
                db.session.add(status)
            else:
                status.target_acted = True

        for comment in note.comments_ctr:
            status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==comment.sender_id))
            if not status:
                status = NoteStatus(note_id=note.id,user_id=comment.sender_id,comment=comment.comment)
                db.session.add(status)
            else:
                status.comment = comment.comment

        # Change the date of files to the date of the note if all are the same
        if note.register.alias != 'mat':
            change_date_files = True
            for file in note.files:
                if file.date != note.files_date:
                    change_date_files = False

            if change_date_files:
                for file in note.files:
                    if not 'ref' in file.path.lower():
                        file.date = note.n_date

    proposals = db.session.scalars(select(Note).where(Note.reg=='mat')).all()

    for note in proposals:
        for alias in note.read_by.split(','):
            user = db.session.scalar(select(User).where(User.alias==alias))
            if not user:
                continue
            status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==user.id))
            if not status:
                status = NoteStatus(note_id=note.id,user_id=user.id,target_acted=True)
                db.session.add(status)
            else:
                status.target_acted = True

        for i,alias in enumerate(note.received_by.split(',')):
            user = db.session.scalar(select(User).where(User.alias==alias))
            if not user:
                continue
            status = db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==note.id,NoteStatus.user_id==user.id))
            if not status:
                status = NoteStatus(note_id=note.id,user_id=user.id,target=True,target_order=i)
                db.session.add(status)
            else:
                status.target = True
                status.target_order = i



    db.session.commit()


def nextNumReg(rg):
    # Get new number for the note. Here getting the las number in that register
    sender = aliased(User,name="sender_user")
    if rg[0] == 'mat':
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg=='mat',Note.year==datetime.today().year,Note.sender.has(User.id==current_user.id)))) )
    elif not rg[2] in ['','pending']:
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.year==datetime.today().year,literal_column(f"sender_user.alias = '{rg[2]}'"),Note.flow=='in'))) )
    else:
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg==rg[0],Note.year==datetime.today().year,Note.flow=='out'))) )
    
    # Now adding +1 to num or start numeration of the year
    if num:
        num += 1
    elif rg[0] == 'cg':
        num = 1
    elif rg[0] == 'asr':
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

    for rec in note.receiver:
        note.receiver.remove(rec)

    
    note.delete_folder()

    db.session.delete(note)
    db.session.commit()


def newNote(user, reg, ref = None):
    num = nextNumReg(reg)
    
    register = db.session.scalar(select(Register).where(Register.alias==reg[0]))

    # Creating the note. We need to know the register it bellows. This note could have been created by a cr dr or a cl member
    if reg[2]: # New note made by a cl member. It's a note for cr from ctr 
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        nt = Note(num=num,sender_id=ctr.id,reg=reg[0],register=register)
    else: # Note created by a cr dr
        nt = Note(num=num,sender_id=user.id,reg=reg[0],register=register)
    
    
    contacts = register.get_contacts()
    if len(contacts) == 1: # There is only one possibility I add it from the beginning
        nt.receiver.append(contacts[0])

    if ref:
        if type(ref) == Note:
            if nt.register.alias == 'mat':
                nt.content = f"{ref.content}"
                nt.content_jp = f"{ref.content_jp}"
            else:
                nt.content = f"Re: {ref.content}"
                nt.content_jp = f"件名: {ref.content_jp}"
            nt.n_tags = ref.n_tags
            
            if nt.register.alias == 'mat':
                rb = []
                for rec in ref.receiver:
                    if rec != current_user:
                        rb.append(rec.alias)
                nt.received_by = ','.join([r for r in rb if r])
            if ref.register.alias == 'mat':
                if ref.ref:
                    nt.ref = ref.ref + [ref]
                    if ref.ref[0].register == register:
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

