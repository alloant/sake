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



def get_cr_users():
    if not 'cr' in session or len(session['cr']) == 0:
        session['cr'] = [user.id for user in db.session.scalars(select(User).where(User.u_groups.regexp_match('\\bcr\\b')))]

    if not 'ctrs' in session or len(session['ctrs']) == 0 or True:
        ctrs = []
        for g in current_user.groups:
            ctr = g.split("_")
            
            if ctr[0] == 'cl':
                ctr_obj = db.session.scalar(select(User).where(User.alias==ctr[1]))
                ctrs.append([ctr_obj.id,ctr_obj.alias])

        session['ctrs'] = ctrs

def nextNumReg(rg):
    # Get new number for the note. Here getting the las number in that register
    sender = aliased(User,name="sender_user")
    if rg[0] == 'min':
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg=='min',Note.year==datetime.today().year,Note.sender.has(User.id==current_user.id)))) )
    elif rg[0] == 'cl':
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.year==datetime.today().year,literal_column(f"sender_user.alias = '{rg[2]}'"),Note.flow=='in'))) )
    elif rg[0] in ['vc','vcr','dg','cc','desr']:
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg==rg[0],Note.year==datetime.today().year,Note.flow=='out'))) )
    else:
        num = db.session.scalar( select(func.max(literal_column("num"))).select_from(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg==rg[2],Note.year==datetime.today().year,Note.flow=='out'))) )
    
    # Now adding +1 to num or start numeration of the year
    if num:
        num += 1
    elif rg[2] == 'cg':
        num = 1
    elif rg[2] == 'asr':
        num = 250
    elif rg[2] == 'ctr':
        num = 1000
    elif rg[2] == 'r':
        num = 2000
    elif rg[0] == 'min':
        num = 1
    else: # it is a ctr making the first note of the year
        num = 1

    return num

def newNote(user,reg,ref = None):
    rg = reg.split('_')

    num = nextNumReg(rg)
    
    ralias = 'ctr' if rg[0] == 'cl' else rg[2] if rg[0] == 'cr' else rg[0]

    register = db.session.scalar(select(Register).where(Register.alias==ralias))
    print(register)

    # Creating the note. We need to know the register it bellows. This note could have been created by a cr dr or a cl member
    if rg[0] == 'cl': # New note made by a cl member. It's a note for cr from ctr 
        ctr = db.session.scalar(select(User).where(User.alias==rg[2]))
        nt = Note(num=num,sender_id=ctr.id,reg='ctr',register=register)
    elif rg[0] == 'min':
        nt = Note(num=num,sender_id=user.id,reg=rg[0],register=register)
    elif rg[0] in ['vc','vcr','dg','cc','desr']:
        nt = Note(num=num,sender_id=user.id,reg=rg[0],register=register)
    else: # Note created by a cr dr
        nt = Note(num=num,sender_id=user.id,reg=rg[2],register=register)
    
        if rg[2] in ['cg','asr']:
            rec = db.session.scalar(select(User).where(User.alias==rg[2]))
            nt.receiver.append(rec)

    if ref:
        for irf in ref.split(","):
            rf = db.session.scalar(select(Note).where(Note.id==irf))
            if rf.reg == 'min':
                for r in rf.ref:
                    nt.ref.append(r)
            else:
                nt.ref.append(rf)

    db.session.add(nt)
    rst = db.session.commit()


def view_title(reg,note=None):
    rg = reg.split('_')
    dark = '-dark' if session['theme'] == 'dark-mode' else ''
    if rg[0] == 'des':
        return [f'static/icons/00-despacho{dark}.svg',gettext(u'Despacho')]
    elif rg[2] == 'pending':
        return [f'static/icons/00-pendings{dark}.svg',gettext(u'My notes')]
    elif rg[2] != '':
        return [f"static/icons/ctr/{rg[2]}-{rg[1]}.svg",f"{gettext('Notes from')} {rg[2]} {gettext('to cr')}" if rg[1] == 'out' else f"{gettext('Notes from cr to')} {rg[2]}"]
    elif rg[0] == 'box' and rg[1] == 'out':
        return [f'static/icons/00-outbox{dark}.svg',gettext(u'Outbox cr')]
    elif rg[0] == 'cr':
        if rg[1] == 'all':
            return ['static/icons/sake.svg',gettext(u"Notes history")]
        else:
            return [f'static/icons/ctr/{rg[2]}-{rg[1]}.svg',f"{gettext('Notes from')} {rg[2]}" if rg[1] == 'in' else f"{gettext('Notes to')} {rg[2]}"]
    elif rg[0] == 'cl':
        if rg[1] == 'all':
            return ['static/icons/sake.svg',gettext("Notes history")]
        else:
            return [f"static/icons/ctr/{rg[2]}-{rg[1]}.svg",f"{gettext('Notes from')} {rg[2]} {gettext('to cr')}" if rg[1] == 'out' else f"{gettext('Notes from cr to')} {rg[2]}"]
    elif rg[0] == 'min':
        return [f'static/icons/00-minutas{dark}.svg',gettext('Minutas')]
    else:
        return [f'static/icons/ctr/{rg[0]}-{rg[1]}.svg',f"{rg[0]} {rg[1]}"]

