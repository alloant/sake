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
from app.src.models import User, Note, Register, NoteUser, Group, Tag

def toNewNotesStatus():

    notes = db.session.scalars(select(Note)).all()
    users = db.session.scalars(select(User)).all()
    ctrs = db.session.scalars(select(User).where(User.category=='ctr')).all()
    registers = db.session.scalars(select(Register)).all()
    groups = db.session.scalars(select(Group)).all()

    for note in notes:
        for tag in note.n_tags.split(','):
            note.add_tag(tag)

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

    for user in note.users:
        db.session.delete(user)
    
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
        newnote = Note(num=num,sender_id=ctr.id,reg=reg[0],register=register)
    else: # Note created by a cr dr
        newnote = Note(num=num,sender_id=user.id,reg=reg[0],register=register)
    
    db.session.add(newnote)
    db.session.commit()
   
    if reg[0] == 'vc' and target == 'asr':
        asr = db.session.scalar(select(User).where(User.alias==target))
        newnote.receiver.append(asr)
    
    contacts = register.get_contacts()
    if len(contacts) == 1: # There is only one possibility I add it from the beginning
        newnote.receiver.append(contacts[0])

    if ref:
        if type(ref) == Note:
            if newnote.register.alias == 'mat':
                newnote.content = f"{ref.content}"
                newnote.content_jp = f"{ref.content_jp}"
            else:
                newnote.content = f"Re: {ref.content}" if ref.content else ''
                newnote.content_jp = f"件名: {ref.content_jp}" if ref.content_jp else ''
            
            for tag in ref.tags:
                newnote.add_tag(tag.text)
            
            if newnote.register.alias == 'mat':
                for user in ref.receiver:
                    if user != current_user and user.category in ['dr','of']:
                        newnote.toggle_status_attr('target',user=user)

            if ref.register.alias == 'mat':
                if ref.ref:
                    newnote.ref = ref.ref + [ref] # I add all the refs of the minuta for people to follow better
                else:
                    newnote.ref.append(ref)

            for rf in ref.ref:
                if rf.register == register and rf.flow == 'in': # I try to guess the target using the firt reference
                    newnote.toggle_status_attr('target',user=rf.sender)
                    break
        else:
            for id_ref in ref.split(","):
                rf = db.session.scalar(select(Note).where(Note.id==id_ref))
                if rf.reg == 'mat':
                    for r in rf.ref:
                        newnote.ref.append(r)
                    newnote.ref.append(rf)
                else:
                    newnote.ref.append(rf)

    rst = db.session.commit()
