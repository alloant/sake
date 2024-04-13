#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, redirect, session, flash
from flask_login import current_user

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, get_ref, Comment, File
from app.forms.note import NoteForm, ReceiverForm

def receivers_form_view(request):
    print('123')
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    form = ReceiverForm(request.form,obj=note)
    form.receiver = note.potential_receivers



    return ""

def edit_receivers_view(request):
    output = request.form.to_dict()
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    form = ReceiverForm(request.form,obj=note)

    filter = output['search'] if 'search' in output else ''

    form.receiver.choices = note.potential_receivers(filter)
    
    if request.method == 'POST':
        return render_template("register/receivers_list.html",note=note, form=form)
    
    return render_template("register/receivers_form.html",note=note, form=form)

def delete_note_view(request):
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    for file in note.files:
        db.session.delete(file)

    for ref in note.ref:
        db.session.delete(ref)

    for rec in note.receiver:
        db.session.delete(rec)
   
    for comment in note.comments_ctr:
        db.session.delete(comment)

    note.delete_folder()

    db.session.delete(note)
    db.session.commit()
    
    return redirect(session['lasturl'])

def edit_note_view(request):
    page = request.args.get('page',1,type=int)
    
    note_id = request.args.get('note')
    alias_ctr = request.args.get('ctr')
    ctr = None
    
    if alias_ctr:
        ctr = db.session.scalar(select(User).where(User.alias==alias_ctr))
        ctr = ctr.id if ctr else None
    else: # No from a ctr then the user has to be in cr
        if not 'cr' in current_user.groups:
            return redirect(session['lasturl'])
    
    #sender = aliased(User,name="sender_user")
    #note = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(Note.id==note_id)).first()
    
    note = db.session.scalars(select(Note).where(Note.id==note_id)).first()
    
    form = NoteForm(request.form,obj=note)
    form.sender.choices = [note.sender]

    form.proc.choices = ['Ord','Not Ord','Consultivo','Deliberativo']

    
    form.content(disable=True)
    
    if note.flow == 'in' or note.reg == 'min':
        form.receiver.choices = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(User.u_groups.regexp_match(r'\bcr\b'),User.active==1)).order_by(User.alias)).all()]
        #form.receiver.choices = [(user.alias,user.fullName) for user in db.session.scalars(select(User).where(and_(User.u_groups.regexp_match(r'\bcr\b'),User.active==1)).order_by(User.alias)).all()]
    elif note.reg in ['vc','vcr']:
        form.receiver.choices = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(User.u_groups.regexp_match(r'\bcg\b'),User.active==1)).order_by(User.alias)).all()]
        form.receiver.choices += [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(User.u_groups.regexp_match(r'\bvc-r\b'),User.active==1)).order_by(User.alias)).all()]
    else:
        #form.receiver.choices = [(user.alias,user.fullName) for user in db.session.scalars(select(User).where(and_(User.u_groups.regexp_match(fr'\b{note.reg}\b'),User.active==1)).order_by(User.alias)).all()]
        form.receiver.choices = [(user.alias,f"{user.alias} ({user.description})") for user in db.session.scalars(select(User).where(and_(User.u_groups.regexp_match(fr'\b{note.reg}\b'),User.active==1)).order_by(User.alias)).all()]
    
     
    if request.method == 'POST' and form.validate():
        error = False
        if ctr and note.state > 0 and note.flow == 'out':
            if form.comments_ctr.data != "":
                cm = db.session.scalar(select(Comment).where(and_(Comment.sender_id==ctr,Comment.note_id==note.id)))
                if not cm:
                    print(ctr,note.id,form.comments_ctr.data)
                    cm = Comment(sender_id=ctr,note_id=note.id,comment=form.comments_ctr.data)
                    db.session.add(cm)
                else:
                    cm.comment = form.comments_ctr.data
        else:
            note.n_date = form.n_date.data
            note.year = form.year.data
            note.content = form.content.data
            note.content_jp = form.content_jp.data
            note.comments = form.comments.data
            note.proc = form.proc.data
            note.permanent = form.permanent.data
            #note.sender = form.sender.data
    
       
            for n,user in enumerate(reversed(note.receiver)):
                if not user.alias in form.receiver.data:
                    note.receiver.remove(user)

            
            for user in form.receiver.data:
                rec = db.session.scalars(select(User).where(User.alias==user)).first()
                if not rec in note.receiver:
                    note.receiver.append(rec)
            

            current_refs = []
            if form.ref.data != "" and not isinstance(form.ref.data,list):
                for ref in form.ref.data.split(","):
                    nt = get_ref(ref.strip())
                    if nt:
                        if nt.reg == 'ctr' or 'cr' in current_user.groups:
                            current_refs.append(nt.fullkey)
                            note.ref.append(nt)
                        else:
                            flash(f"Note {ref} cannot be add")
                            error = True
                    else:
                        flash(f"Note {ref} doesn't exist")
                        error = True

            # Now I remove the notes not in current
            for ref in reversed(note.ref):
                if not ref.fullkey in current_refs:
                    note.ref.remove(ref)
        
        db.session.commit()
        
        if not error:
            return redirect(session['lasturl'])
    
    else:
        form.ref.data = ",".join([r.fullkey for r in note.ref]) if note.ref else "" 
        for rec in note.receiver:
            form.receiver.data.append(rec.alias)
        
        form.permanent.data = note.permanent
        
        form.comments_ctr.data = ""
        for cm in note.comments_ctr:
            if cm.sender_id == ctr:
                form.comments_ctr.data = cm.comment
 
    if ctr and (note.state > 0 and note.flow == 'in' or note.flow == 'out'):
        return render_template('register/note_form_ctr.html', form=form, note=note, user=current_user, ctr=ctr)
    else:
        return render_template('register/note_form.html', form=form, note=note, user=current_user, ctr=ctr)

