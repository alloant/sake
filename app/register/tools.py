#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

from sqlalchemy import select, func, literal_column, and_
from sqlalchemy.orm import aliased

from flask import session
from flask_babel import gettext
from flask_login import current_user

from app import db
from app.models import User, Note, Register


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

def newNote(user,reg,ref = None):
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
            nt.content = f"Re: {ref.content}"
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


def view_title(reg,note=None):
    rg = reg.split('_')
    dark = '-dark' if session['theme'] == 'dark-mode' else ''
    
    if rg[0] == 'des': # Despacho
        return [f'static/icons/00-despacho{dark}.svg',gettext(u'Despacho')]
    elif rg[2] == 'pending': # For my notes list
        return [f'static/icons/00-pendings{dark}.svg',gettext(u'Pending')]
    elif rg[0] == 'box' and rg[1] == 'out': # Outbox
        return [f'static/icons/00-outbox{dark}.svg',gettext(u'Outbox cr')] 
    elif rg[2] != '': # All the suregisters for the centers
        return [f"static/icons/ctr/{rg[2]}-{rg[1]}.svg",f"{gettext('Notes from')} {rg[2]} {gettext('to cr')}" if rg[1] == 'out' else f"{gettext('Notes from cr to')} {rg[2]}"]
    elif rg[0] == 'all': # History note, also pendings has the same but we already check that before
        return ['static/icons/sake.svg',gettext(u"Notes history")]
    elif rg[0] == 'mat':
        return [f'static/icons/00-minutas{dark}.svg',gettext('Matters')]
    else:
        return [f'static/icons/ctr/{rg[0]}-{rg[1]}.svg',f"{rg[0]} {rg[1]}"]

