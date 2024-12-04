#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import ast
import webbrowser

import asyncio

from flask import render_template, session, flash, Response, make_response, redirect
from flask_login import current_user

from sqlalchemy import select, and_

from app import db, sock_clients
from app.src.models import Note, User, Comment, File, get_note_fullkey
from app.src.forms.note import ReceiverForm, TagForm
from app.src.tools.tools import newNote
from app.src.tools.websocket import send_message

from app.src.models.nas.nas import files_path

def sortable_view(request):
    form = ReceiverForm(request.form)
    order = request.form.keys()
    return ("",204)


def updateSocks(users,msg=''):
    #asyncio.run(send_message({'users':users,'message':msg}))
    global sock_clients
    for i,user in enumerate(users):
        if user.alias in sock_clients and user != current_user:
            umsg = msg if isinstance(msg,str) else msg[i]
            try:
                sock_clients[user.alias].send(f'<div id="sock_id"><span hx-get="/load_socket?msg={umsg}" hx-trigger="load" hx-swap="outerHTML"></span></div>')
            except:
                pass
    

def fill_form_note(reg,form,note, filter = ""):
    if reg[2] or note.flow == 'in':
        form.sender.choices = [note.sender]
    else:
        form.sender.choices = db.session.scalars(select(User).where(and_(User.contains_group('cr'),User.active==1))).all()

    form.proc.choices = ['Routine','Ordinary','Not ordinary','Consultative','Deliberative','Extraordinary']

    if note.reg != 'mat':
        form.receiver.choices = note.potential_receivers(filter)

    form.ref.data = ",".join([r.fullkey for r in note.ref]) if note.ref else ""
    
    
    previous_order = -1
    bar_put = False
    bar_needed = False
    
    for i,status in enumerate(note.status):
        if status.target:
            if note.reg == 'mat' and previous_order != -1 and previous_order == status.target_order: # Two with same order, then is needed
                bar_needed = True

            if bar_needed and not bar_put and note.reg == 'mat' and previous_order != -1 and status.target_order != previous_order:
                form.receiver.data.append('---')
                bar_put = True

            form.receiver.data.append(status.user.alias)

            previous_order = status.target_order
   
    if note.reg == 'mat' and bar_needed and not bar_put:
        form.receiver.data = ['---'] + form.receiver.data

    if note.reg == 'mat':
        form.receiver.choices = note.potential_receivers(filter,form.receiver.data)


    form.permanent.data = note.permanent

    if reg[2]:
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        form.comments_ctr.data = ""
        for cm in note.comments_ctr:
            if cm.sender_id == ctr.id:
                form.comments_ctr.data = cm.comment

    session['opt_checkbox'] = form.receiver.choices
    session['rst_checkbox'] = form.receiver.data

    return form


def extract_form_note(reg,form,note):
    print('Extract form note')
    if reg[2] or note.flow == 'in':
        form.sender.choices = [note.sender]
    else:
        form.sender.choices = db.session.scalars(select(User).where(and_(User.contains_group('cr'),User.active==1))).all()

    form.proc.choices = ['Routine','Ordinary','Not ordinary','Consultative','Deliberative','Extraordinary']

    filter = ''

    if note.reg == 'mat':
        form.receiver.choices = note.potential_receivers(filter,form.receiver.data)
    else:
        form.receiver.choices = note.potential_receivers(filter)

    if reg[2] and note.flow == 'out':
        ctr = db.session.scalar(select(User).where(User.alias==reg[2]))
        cm = db.session.scalar(select(Comment).where(and_(Comment.sender_id==ctr.id,Comment.note_id==note.id)))
        if not cm:
            if form.comments_ctr.data != "":
                cm = Comment(sender_id=ctr.id,note_id=note.id,comment=form.comments_ctr.data)
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

        if 'rst_checkbox' in session and note.reg != 'mat':
            for ch in session['opt_checkbox']:
                if ch[0] in session['rst_checkbox']:
                    session['rst_checkbox'].remove(ch[0])

            session['rst_checkbox'] += form.receiver.data
            form.receiver.data = session['rst_checkbox']
            session['opt_checkbox'] = form.receiver.choices
        else:
            session['rst_checkbox'] = form.receiver.data

        for n,user in enumerate(reversed(note.receiver)):
            if not user.alias in form.receiver.data:
                note.receiver.remove(user)
                note.toggle_status_attr('target',user=user)
       
        for user in session['rst_checkbox']:
            if user == '---':
                continue
            rec = db.session.scalars(select(User).where(User.alias==user)).first()
            if not rec in note.receiver:
                note.receiver.append(rec)
                note.toggle_status_attr('target',user=rec)

        dash_position = session['rst_checkbox'].index('---') if '---' in session['rst_checkbox'] else -1
        for status in note.status:
            pos = session['rst_checkbox'].index(status.user.alias) if status.user.alias in session['rst_checkbox'] else -1
            if pos == -1:
                status.target = False
            else:
                status.target_order = pos if pos > dash_position else dash_position

        if note.reg == 'mat' and note.state == 5:
            for state in note.status:
                if not state.target_acted:
                    note.state = 1
                    break

        current_refs = []
        if form.ref.data != "" and not isinstance(form.ref.data,list):
            for ref in form.ref.data.split(","):
                nt = get_note_fullkey(ref.strip())
                if nt:
                    if nt.register.alias == 'ctr' or 'cr' in current_user.groups:
                        current_refs.append(nt.fullkey)
                        if not nt in note.ref:
                            note.ref.append(nt)
                    else:
                        flash(f"Note {ref} cannot be add",'danger')
                        error = True
                else:
                    flash(f"Note {ref} doesn't exist",'warning')
                    error = True

        # Now I remove the notes not in current
        for ref in reversed(note.ref):
            if not ref.fullkey in current_refs:
                note.ref.remove(ref)
    
    db.session.commit()

    

def files_view(request):
    path = request.args.get("path_folder")
    if path == 'forms':
        path = '/team-folders/Experiencias/Forms for decisions, appointments, etc'
    elif path == 'templates':
        path = f'/team-folders/Data/Templates'
    elif path == 'mydrive':
        path = '/mydrive'
    elif path == 'teams':
        path = '/team-folders'
    elif 'note_' in path:
        nid = int(path.split('_')[1])
        nt = db.session.scalar(select(Note).where(Note.id==nid))
        return render_template("modals/modal_files_list_sake.html",files=nt.files)
    
    if re.match(r'^/mydrive.+',path) or re.match(r'^/team-folders.+',path):
        parent_path = "/".join(path.split("/")[:-1])
        files = [{'type':'dir','name':'...','display_path':parent_path,'permanent_link':''}]
    else:
        files = []

    path_files = files_path(path)

    for file in path_files:
        if file['display_path'][0] != '/':
            file['display_path'] = f"{path}/{file['display_path']}"

    files += path_files
    
    return render_template("modals/modal_files_list_synology.html",files=files)


def reply_note_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    copy = request.args.get("copy","")
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))

    if request.method == 'POST' or reg[2]:
        if not reg[2]:
            reg_new_note = request.form.getlist('reg_new_note')[0]
            if reg_new_note == 'mat':
                new_reg = ['mat','all','']
            else:
                new_reg = [reg_new_note,'out','']
        else:
            new_reg = [reg[0],'out',reg[2]]
        
         
        newNote(current_user,reg=new_reg,ref=note)
        session['reg'] = new_reg
        resp = Response()
        resp.headers["hx-redirect"] = '/'
        return resp
   
    regs = [['mat','New proposal'],['cg','New note to cg'],['asr','New note to asr'],['ctr','New note to ctr'],['r','New note to r']]

    if note.register.alias != 'mat':
        selected = 'mat'
    else:
        selected = 'cg'
        for rf in note.ref:
            if rf.register.alias != 'mat':
                selected = rf.register.alias

    return render_template("modals/modal_reply_note.html",reg=reg,note=note,regs=regs,selected=selected)

def get_files_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
       
    if note.ref:
        files = note.ref[0].files
        return render_template('modals/modal_files_list_sake.html',files=files)
    else:
        path = '/team-folders'
        files = files_path(path)
        return render_template('modals/modal_files_list_synology.html',files=files)




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
            return file.subject_html()

        return render_template("modals/modal_receivers_list.html", form=form)
    else:
        for rec in file.subject.split(","):
            form.receiver.data.append(rec)
        
    
    session['fopt_checkbox'] = form.receiver.choices
    session['frst_checkbox'] = form.receiver.data
    return render_template("modals/modal_receivers.html", hxpost=f"/edit_receivers_files?file={file.id}", hxtarget=f"recFiles-{file.id}", form=form)

def edit_tags_view(request):
    output = request.form.to_dict()
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    save = request.args.get('save')
    form = TagForm(request.form,obj=note)

    filter = output['search'] if 'search' in output else ''
    
    
    form.tag.choices = [(tag,tag) for tag in ['aop','ar','df','dg','dest','desr','stgr','str','sccr','ocsr','minors','vcr','vcsr','sm','sg','sr','sss+','Ind','Aso','Asmo','J'] if filter in tag]

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
            note.n_tags = ",".join([t for t in form.tag.data if t])

            db.session.commit()
            return note.tag_html(True)

        return render_template("modals/modal_tags_list.html",note=note, form=form)
    else:
        form.tag.data = note.tags
        
    
    session['opt_tags'] = form.tag.choices
    session['rst_tags'] = form.tag.data
    return render_template("modals/modal_tags_form.html",hxpost=f"/edit_tags?note={note.id}", hxtarget=f"tagRow-{note.id}", form=form)


def edit_receivers_view(request):
    output = request.form.to_dict()
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    type_save = request.args.get('type')
    save = request.args.get('save')
    form = ReceiverForm(request.form,obj=note)

    filter = output['search'] if 'search' in output else ''
    if type_save == 'permissions':
        form.receiver.choices = note.potential_receivers(filter,only_of=True)
    else:
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
    
         
        if save == '1':
            for n,user in enumerate(reversed(note.receiver)):
                if not user.alias in form.receiver.data:
                    note.receiver.remove(user)
                    note.toggle_status_attr('target',user=user)

            for user in session['rst_checkbox']:
                rec = db.session.scalars(select(User).where(User.alias==user)).first()
                if not rec in note.receiver:
                    note.receiver.append(rec)
                    note.toggle_status_attr('target',user=rec)

            db.session.commit()
            return note.dep_html
        elif save == '2':
            note.privileges = [p for p in session['rst_checkbox'] if p] if session['rst_checkbox'] else ""
            db.session.commit()
            return ""

        return render_template("modals/modal_receivers_list.html",note=note, form=form)
    else:
        if type_save == 'permissions':
            form.receiver.data = note.privileges.split(',')
        else:
            for rec in note.receiver:
                form.receiver.data.append(rec.alias)


    session['opt_checkbox'] = form.receiver.choices
    session['rst_checkbox'] = form.receiver.data

    if type_save == 'permissions':
        return render_template("modals/modal_receivers.html",hxpost=f"/edit_receivers?note={note.id}", hxtarget="", form=form)
    else:
        return render_template("modals/modal_receivers.html",hxpost=f"/edit_receivers?note={note.id}", hxtarget=f"recRow-{note.id}", form=form)

def load_socket_view(request):
    msg = request.args.get('msg',False)
    
    if msg:
        msg = f"'{msg}'"
        res = make_response(f'<span hx-on:htmx:load="sendNotification({msg})" hx-trigger="load"></span>')
    else:
        res = make_response(f'<span></span>')
    res.headers['HX-Trigger'] = 'socket-updated'
    
    return res
