#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import ast
import webbrowser

from flask import render_template, session, flash, Response, make_response, redirect
from flask_login import current_user

from sqlalchemy import select, and_

from app import db, sock_clients
from app.src.models import Note, User, Comment, File, get_note_fullkey
from app.src.forms.note import ReceiverForm, TagForm
from app.src.tools.tools import newNote

from app.src.models.nas.nas import files_path, copy_path, copy_office_path

def sortable_view(request):
    form = ReceiverForm(request.form)
    order = request.form.keys()
    return ("",204)


def updateSocks(users=False):
    global sock_clients
    for key,ws in sock_clients.items():
        if current_user.alias != key:
            if not users or key in users: 
                try:
                    ws.send('<div id="sock_id"><span hx-get="/load_socket" hx-trigger="load" hx-swap="outerHTML"></div>')
                except:
                    pass

def fill_form_note(reg,form,note, filter = ""):
    if reg[2] or note.flow == 'in':
        form.sender.choices = [note.sender]
    else:
        form.sender.choices = db.session.scalars(select(User).where(and_(User.contains_group('cr'),User.active==1))).all()

    form.proc.choices = ['Routine','Ordinary','Not ordinary','Consultative','Deliberative','Extraordinary']

    if note.reg == 'mat':
        form.receiver.choices = note.potential_receivers(filter,note.received_by.split(","))
    else:
        form.receiver.choices = note.potential_receivers(filter)

    form.ref.data = ",".join([r.fullkey for r in note.ref]) if note.ref else "" 
    
    if note.reg == 'mat':
        form.receiver.data = note.received_by
    else:
        for rec in note.receiver:
            form.receiver.data.append(rec.alias)
    
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
    if reg[2] or note.flow == 'in':
        form.sender.choices = [note.sender]
    else:
        form.sender.choices = db.session.scalars(select(User).where(and_(User.contains_group('cr'),User.active==1))).all()

    form.proc.choices = ['Routine','Ordinary','Not ordinary','Consultative','Deliberative','Extraordinary']

    filter = ''

    if note.reg == 'mat':
        form.receiver.choices = note.potential_receivers(filter,note.received_by.split(","))
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
        #print(form.sender.data)
        #note.sender_id = form.sender.data

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

            if note.read_by != '':
                new_read_by = []
                for rc in form.receiver.data:
                    if rc != '' and rc in note.read_by.split(','):
                        new_read_by.append(rc)
                note.read_by = ",".join([r for r in new_read_by if r])
    
         
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
        path = '/team-folders/Data/Templates'
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

def update_files_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.updateFiles()
    
    res = make_response(note.files_html(reg))
    res.headers['HX-Trigger'] = 'update-flash'

    return res

    return note.files_html(reg)

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
   
    regs = [['mat','To matters'],['cg','To cg'],['asr','To asr'],['ctr','To ctr'],['r','To r']]

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


def browse_files_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    
    copy = request.args.get("copy","")
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    untitled =[]
    if copy == 'true':
        files = request.form.getlist('files_to_copy')
        cont = 0
        for file in files:
            if re.match(r'Untitled\.(odoc|osheet|oslide)',file.split('/')[-1]):
                name = file.split('/')[-1]
                ext = name.split('.')[-1]
                for fn in note.files + untitled:
                    fname = fn if isinstance(fn,str) else fn.path
                    if re.match(fr'{note.folder_name}_*a*[0-9]*\.[a-zA-Z]+',fname):
                        cont += 1

                if cont == 0:
                    copy_office_path(file,f"{note.folder_path}/{note.folder_name}.{ext}")
                else:
                    copy_office_path(file,f"{note.folder_path}/{note.folder_name}_a{cont}.{ext}")
                untitled.append(note.folder_name)
            else:
                copy_path(file,f"{note.folder_path}/{file.split('/')[-1]}")
        
        note.updateFiles()

        return note.files_html(reg)
   
    
    return render_template("modals/modal_files.html",note=note, reg=reg)


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

        return render_template("modals/modal_receivers_list.html",note=note, form=form)
    else:
        for rec in note.receiver:
            form.receiver.data.append(rec.alias)
        
    
    session['opt_checkbox'] = form.receiver.choices
    session['rst_checkbox'] = form.receiver.data
    return render_template("modals/modal_receivers.html",hxpost=f"/edit_receivers?note={note.id}", hxtarget=f"recRow-{note.id}", form=form)


def read_note_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    only_content = request.args.get('only_content',False)
    file_clicked = int(request.args.get('file_clicked',-1))
    
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    if not only_content and not (file_clicked > 0 and note.is_read(current_user)) and note.register.alias != 'mat' and reg[1] != 'out' and not reg[0] in ['des','box']:
        note.updateRead(current_user)
        
        
    res = make_response(note.content_html(reg))
    if file_clicked > 0:
        res.headers['HX-Trigger'] = f'read-updated,content_{note.id},open_file_{file_clicked}'
    else:
        res.headers['HX-Trigger'] = 'read-updated'


    return res

def load_socket_view(request):
    res = make_response('<span></span>')
    res.headers['HX-Trigger'] = 'socket-updated'

    return res


def open_file_view(request):
    #reg = ast.literal_eval(request.args.get('reg'))
    link = request.args.get('link')
    
    #note_id = request.args.get('note')
    #note = db.session.scalar(select(Note).where(Note.id==note_id))
   
    #if reg[1] != 'out' and not reg[0] in ['des','box'] and note.register.alias != 'mat' and not note.is_read(current_user):
    #    note.updateRead(current_user)
    
    #res = make_response(redirect(link))
    #res = Response()
    #res.headers["hx-redirect"] = link
    #response["HX-Redirect"] = "http://example.com/page_to_redirect_to"
    #res.headers['HX-Trigger'] = f'file-opened, content_{note.id}'
    webbrowser.open(link)
    return ""
    return webbrowser.open_new_tab(link)
    #return res


def state_note_view(request):
    reg = ast.literal_eval(request.args.get('reg'))
    note_id = request.args.get('note')
    
    cancel = request.args.get('cancel',False)
    
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.updateState(reg,current_user,cancel)
    
    if note.register.alias == 'mat':
        updateSocks(note.received_by.split(',') + [note.sender.alias])
    elif reg[0] == 'des':
        updateSocks([rc.alias for rc in note.receiver])
    
    if reg[2]:
        return render_template('notes/table_row_subregister.html',note=note, reg=reg, user=current_user)
    else:
        res = make_response(render_template('notes/table_row.html',note=note, reg=reg, user=current_user))
        res.headers['HX-Trigger'] = f'state-updated'
        return res
    
    res = make_response(note.status_html(reg))
    #res.headers['HX-Trigger'] = f'update-row-{note.id}'
    res.headers['HX-Trigger'] = f'update-row-{note.id}, state-updated'

    return res

