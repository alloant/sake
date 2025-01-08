#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

from sqlalchemy import select, func, literal_column, and_
from sqlalchemy.orm import aliased

from flask import session, current_app
from flask_login import current_user

from app import db
from app.src.models import User, Note, Register, NoteUser, Group, Tag


def next_num_note(reg,target=None):
    # Get new number for the note. Here getting the las number in that register
    sender = aliased(User,name="sender_user")
    if reg[0] == 'mat':
        num = db.session.scalar(select(func.max(Note.num)).where(
            Note.register.has(Register.alias==reg[0]),
            Note.sender_id==current_user.id,
            Note.year==datetime.today().year
        ))
    elif reg[0] == 'vc' and target == 'asr':
        num = db.session.scalar(select(func.max(Note.num)).where(
            Note.register.has(Register.alias==reg[0]),
            Note.flow=='out',
            Note.year==datetime.today().year,
            Note.num > 250
        ))
    elif reg[2]: #it is a ctr
        num = db.session.scalar(select(func.max(Note.num)).where(
            Note.sender.has(User.alias==reg[2]),
            Note.year==datetime.today().year
        ))
    else:
        num = db.session.scalar(select(func.max(Note.num)).where(
            Note.register.has(Register.alias==reg[0]),
            Note.flow=='out',
            Note.year==datetime.today().year
        ))
    
    # Now adding +1 to num or start numeration of the year
    if num:
        num += 1
    elif reg[2]:
        num = 1
    elif reg[0] == 'cg':
        num = 1
    elif reg[0] == 'asr' or reg[0] == 'vc' and target == 'asr':
        num = 250
    elif reg[0] == 'ctr':
        num = 1000
    elif reg[0] == 'r':
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


def new_note(user, reg, reference = None, target = None, num = None, year = None, date = None, is_ref = False, status = 'draft'):
    if not num:
        num = next_num_note(reg,target)

    if isinstance(reg,list): # New note made by a cl member. It's a note for cr from ctr 
        register = db.session.scalar(select(Register).where(Register.alias==reg[0]))
    else:
        register = db.session.scalar(select(Register).where(Register.alias==reg))

    # Creating the note. We need to know the register it belongs. This note could have been created by a cr dr or a cl member
    if isinstance(reg,str): # New note made by a cl member. It's a note for cr from ctr 
        newnote = Note(num=num,sender_id=user.id,reg=reg,register=register,status=status,is_ref=is_ref)
    elif isinstance(reg,list) and reg[2]: # New note made by a cl member. It's a note for cr from ctr 
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        newnote = Note(num=num,sender_id=ctr.id,reg=reg[0],register=register,status=status,is_ref=is_ref)
    else: # Note created by a cr dr
        newnote = Note(num=num,sender_id=user.id,reg=reg[0],register=register,status=status,is_ref=is_ref)

    if year:
        newnote.year = year
    if date:
        newnote.n_date = date

    db.session.add(newnote)
    db.session.commit()
    newnote.create_folder()
   

    # Information we can get from the references
    if reference:
        if type(reference) == Note:
            refs = [reference]
        else:
            refs = db.session.scalars(select(Note).where(Note.id.in_(reference.split(',')))).all()
    else:
        refs = []

    for ref in refs:
        # Try add content if needed
        if newnote.content == '' and ref.content != '':
            if (newnote.register.alias == 'mat' or newnote.sender.category == 'ctr') and not re.match(r'^Re:',ref.content):
                newnote.content = f"Re: {ref.content}"
                newnote.content_jp = f"件名: {ref.content_jp}" if ref.content_jp else ''
            else:
                newnote.content = f"{ref.content}"
                newnote.content_jp = f"{ref.content_jp}"
        
        ## Add tags if needed
        if not newnote.tags:
            for tag in ref.tags:
                newnote.add_tag(tag.text)

        ## The ref
        newnote.ref.append(ref)

    ## Adding targets only for note going out:
    if newnote.flow == 'out' and refs:
        if newnote.register.alias == 'mat': # It is a proposal. I add the same people assigned to original
            for user in refs[0].receiver:
                if user != current_user and user.category in ['dr','of']:
                    newnote.toggle_status_attr('target',user=user)
        elif reg[0] == 'vc' and target == 'asr': # Special case to add asr as a target in vc notes for notes going out
            asr = db.session.scalar(select(User).where(User.alias==target))
            newnote.receiver.append(asr)
        else:
            contacts = register.get_contacts()
            if len(contacts) == 1: # There is only one possibility I add it from the beginning
                newnote.receiver.append(contacts[0])
            else:
                for rf in refs[0].ref:
                    if rf.register == register and rf.flow == 'in': # I try to guess the target using the firt reference
                        newnote.toggle_status_attr('target',user=rf.sender)
                        break

    rst = db.session.commit()

    return newnote
