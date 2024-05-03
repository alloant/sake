#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, render_template_string, redirect, session, flash
from flask_login import current_user

from sqlalchemy import select, and_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, User, Comment, File, Register, get_note_fullkey
from app.forms.note import NoteForm, ReceiverForm, TagForm

def sortable_view(request):
    form = ReceiverForm(request.form)
    order = request.form.keys()
    return ("",204)

def rec_files_view(request):
    return "asdasd"

def edit_receivers_files_view(request):
    output = request.form.to_dict()
    file_id = request.args.get('file')
    save = request.args.get('save')
    file = db.session.scalar(select(File).where(File.id==file_id))
    note = db.session.scalar(select(Note).where(Note.id==file.note_id))
    
    form = ReceiverForm(request.form)

    filter = output['search'] if 'search' in output else ''
    if 'rst_checkbox' in session:
        possibles = session['rst_checkbox']
    else:
        possibles = []

    form.receiver.choices = note.potential_receivers(filter,possibles = possibles)
    
    if request.method == 'POST':
        if 'frst_checkbox' in session:
            for ch in session['fopt_checkbox']:
                if ch[0] in session['frst_checkbox']:
                    session['frst_checkbox'].remove(ch[0])

            session['frst_checkbox'] += form.receiver.data
            form.receiver.data = session['frst_checkbox']
            session['fopt_checkbox'] = form.receiver.choices
        else:
            session['frst_checkbox'] = form.receiver.data
        
        if save:
            file.subject = ",".join([c for c in session['frst_checkbox'] if c])
            db.session.commit()
            return file.subject_html

        return render_template("register/receivers_list.html", form=form)
    else:
        for rec in file.subject.split(","):
            form.receiver.data.append(rec)
        
    
    session['fopt_checkbox'] = form.receiver.choices
    session['frst_checkbox'] = form.receiver.data
    return render_template("register/receivers_form.html", hxpost=f"/edit_receivers_files?file={file.id}", hxtarget=f"recFiles-{file.id}", form=form)

def edit_tags_view(request):
    output = request.form.to_dict()
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    save = request.args.get('save')
    form = TagForm(request.form,obj=note)

    filter = output['search'] if 'search' in output else ''
    
    form.tag.choices = [(tag,tag) for tag in ['sm','sg','sr','ar','desr','Ind','Aso','Asmo','J'] if filter in tag]
    
    if request.method == 'POST':
        if 'rst_tags' in session:
            for ch in session['opt_tags']:
                if ch[0] in session['rst_tags']:
                    session['rst_tags'].remove(ch[0])
            
            session['rst_tags'] += form.tag.data
            form.tag.data = session['rst_tags']
            session['opt_tags'] = form.tag.choices
        else:
            session['rst_tags'] = form.tag.data
        
        if save:
            note.n_tags = ",".join(form.tag.data)

            db.session.commit()
            return note.tag_html(True)

        return render_template("register/tags_list.html",note=note, form=form)
    else:
        form.tag.data = note.tags
        
    
    session['opt_tags'] = form.tag.choices
    session['rst_tags'] = form.tag.data
    return render_template("register/tags_form.html",hxpost=f"/edit_tags?note={note.id}", hxtarget=f"tagRow-{note.id}", form=form)


def edit_receivers_view(request):
    output = request.form.to_dict()
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    save = request.args.get('save')
    form = ReceiverForm(request.form,obj=note)

    filter = output['search'] if 'search' in output else ''
    form.receiver.choices = note.potential_receivers(filter)
    
    if request.method == 'POST':
        if 'rst_checkbox' in session:
            for ch in session['opt_checkbox']:
                if ch[0] in session['rst_checkbox']:
                    session['rst_checkbox'].remove(ch[0])
            
            session['rst_checkbox'] += form.receiver.data
            form.receiver.data = session['rst_checkbox']
            session['opt_checkbox'] = form.receiver.choices
        else:
            session['rst_checkbox'] = form.receiver.data
        
        if save:
            for n,user in enumerate(reversed(note.receiver)):
                if not user.alias in form.receiver.data:
                    note.receiver.remove(user)
            
            for user in session['rst_checkbox']:
                rec = db.session.scalars(select(User).where(User.alias==user)).first()
                if not rec in note.receiver:
                    note.receiver.append(rec)

            db.session.commit()
            return note.dep_html

        return render_template("register/receivers_list.html",note=note, form=form)
    else:
        for rec in note.receiver:
            form.receiver.data.append(rec.alias)
        
    
    session['opt_checkbox'] = form.receiver.choices
    session['rst_checkbox'] = form.receiver.data
    return render_template("register/receivers_form.html",hxpost=f"/edit_receivers?note={note.id}", hxtarget=f"recRow-{note.id}", form=form)

def delete_note_view(request):
    note_id = request.args.get('note')
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
    
    return redirect(session['lasturl'])

def edit_note_view(request):
    output = request.form.to_dict()
    page = request.args.get('page',1,type=int)
    
    despacho = request.args.get('despacho')
    note_id = request.args.get('note')
    note = db.session.scalars(select(Note).where(Note.id==note_id)).first()
    
    alias_ctr = request.args.get('ctr')
    ctr = None
    
    if alias_ctr:
        ctr = db.session.scalar(select(User).where(User.alias==alias_ctr))
        ctr = ctr.id if ctr else None
    else: # No from a ctr then the user has to be in cr
        if not 'cr' in current_user.groups or not note.current_user_can_edit():
            return redirect(session['lasturl'])
    
    #sender = aliased(User,name="sender_user")
    #note = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(Note.id==note_id)).first()
    despacho = True if despacho and 'despacho' in current_user.groups else False

    
    form = NoteForm(request.form,obj=note)
    form.sender.choices = [note.sender]

    form.proc.choices = ['Ord','Not Ord','Consultivo','Deliberativo']

    
    form.content(disable=True)
    
    filter = output['search'] if 'search' in output else ''

    if note.reg == 'mat':
        form.receiver.choices = note.potential_receivers(filter,note.received_by.split(","))
    else:
        form.receiver.choices = note.potential_receivers(filter)
         
    if request.method == 'POST' and form.validate():
        error = False
        if ctr and note.state > 0 and note.flow == 'out':
            if form.comments_ctr.data != "":
                cm = db.session.scalar(select(Comment).where(and_(Comment.sender_id==ctr,Comment.note_id==note.id)))
                if not cm:
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
    
            if 'rst_checkbox' in session and note.reg != 'mat':
                for ch in session['opt_checkbox']:
                    if ch[0] in session['rst_checkbox']:
                        session['rst_checkbox'].remove(ch[0])

                session['rst_checkbox'] += form.receiver.data
                form.receiver.data = session['rst_checkbox']
                session['opt_checkbox'] = form.receiver.choices
            else:
                session['rst_checkbox'] = form.receiver.data

            if note.reg == 'mat':
                rd = note.read_by.split(',')
                rd += [us for us in form.receiver.data if not us in rd]
                form.receiver.data = rd
                note.received_by = ",".join([r for r in form.receiver.data if r])
        
             
            for n,user in enumerate(reversed(note.receiver)):
                if not user.alias in form.receiver.data:
                    note.receiver.remove(user)
            
            for user in session['rst_checkbox']:
                rec = db.session.scalars(select(User).where(User.alias==user)).first()
                if not rec in note.receiver:
                    note.receiver.append(rec)

            current_refs = []
            if form.ref.data != "" and not isinstance(form.ref.data,list):
                for ref in form.ref.data.split(","):
                    nt = get_note_fullkey(ref.strip())
                    if nt:
                        if nt.register.alias == 'ctr' or 'cr' in current_user.groups:
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
 
    session['opt_checkbox'] = form.receiver.choices
    session['rst_checkbox'] = form.receiver.data
    registers = db.session.scalars(select(Register).where(Register.active==1)).all()
    if ctr and (note.state > 0 and note.flow == 'in' or note.flow == 'out'):
        return render_template('register/note_form_ctr.html', form=form, note=note, user=current_user, ctr=ctr, registers=registers, despacho=False)
    else:
        return render_template('register/note_form.html', form=form, note=note, user=current_user, ctr=ctr, registers=registers, despacho=despacho)

