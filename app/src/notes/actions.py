#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import io
import re
from datetime import date
from dateutil.relativedelta import relativedelta

from flask import render_template, session, make_response, current_app, flash
from flask_login import current_user

from sqlalchemy import select, and_, or_, func, not_
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased

from flask_babel import gettext

from app import db
from app.src.models import Note, User, Register, File, NoteUser, Group
from app.src.forms.note import NoteForm
from app.src.notes.edit import fill_form_note, extract_form_note, updateSocks
from app.src.notes.renders import render_main_body, render_body_element

from app.src.tools.mail import send_emails
from app.src.tools.tools import newNote, delete_note
from app.src.tools.syneml import write_eml

from app.src.models.nas.nas import copy_path, copy_office_path, toggle_share_permissions, delete_path, upload_path, convert_office

EXT = {'xls':'osheet','xlsx':'osheet','docx':'odoc','rtf':'odoc'}

def action_note_view(request,template):
    reg = request.args.get('reg')
    if reg:
        reg = ast.literal_eval(reg)
    else:
        reg = session['reg']
    
    note_id = None
    action = request.args.get('action')
    trigger = ['update-flash']
    match action:
        case 'read':
            file_clicked = True if request.args.get('file_clicked','false') == 'true' else False
            note_id = request.args.get('note')
            if file_clicked:
                note = db.session.scalar(select(Note).where(Note.id==note_id))
                if not note.result('is_read'):
                    trigger.append(f'content_{note_id}')
            else:
                toggle_read(note_id,file_clicked)
                trigger.append('read-updated')
        case 'archive':
            note_id = request.args.get('note')
            ctr = True if request.args.get('ctr','false') == 'true' else False
            toggle_archive(note_id,ctr)
            trigger.append('status-updated')
        case 'start_circulation':
            note_id = request.args.get('note')
            circulation_proposal(note_id,'start')
            trigger.append('state-updated')
            trigger.append('socket-updated')
        case 'stop_circulation':
            note_id = request.args.get('note')
            circulation_proposal(note_id,'stop')
            trigger.append('state-updated')
            trigger.append('socket-updated')
        case 'restart_circulation':
            note_id = request.args.get('note')
            circulation_proposal(note_id,'restart')
            trigger.append('state-updated')
            trigger.append('socket-updated')
        case 'sign_proposal':
            note_id = request.args.get('note')
            act = 'back' if request.args.get('back','false') == 'true' else 'forward'
            circulation_proposal(note_id,act)
            trigger.append('state-updated')
            trigger.append('socket-updated')
        case 'reset_proposal':
            note_id = request.args.get('note')
            circulation_proposal(note_id,'reset')
            trigger.append('state-updated')
            trigger.append('socket-updated')
        case 'new':
            if reg[0] == 'box':
                return new_note(reg)
            else:
                target = request.args.get('target')
                newNote(current_user,reg,target=target)
        case 'create_note':
            created(reg,request)
        case 'send_to_box':
            note_id = request.args.get('note')
            back = True if request.args.get('back','false') == 'true' else False
            send_to_box(reg,note_id,back)
            trigger.append('socket-updated')
        case 'outbox_target':
            note_id = request.args.get('note')
            back = True if request.args.get('back','false') == 'true' else False
            outbox_to_target(note_id,back)
            trigger.append('state-updated')
        case 'inbox_despacho':
            note_id = request.args.get('note')
            back = True if request.args.get('back','false') == 'true' else False
            inbox_to_despacho(note_id,back)
            trigger.append('state-updated')
        case 'download_eml':
            note_id = request.args.get('note')
            return download_eml(note_id)
        case 'delete_note':
            note_id = request.args.get('note')
            delete_note(note_id)
            note_id = None
        case 'delete_file':
            note_id = request.args.get('note')
            file_id = request.args.get('file')
            note = db.session.scalar(select(Note).where(Note.id==note_id))
            file = db.session.scalar(select(File).where(File.id==file_id))
            delete_path(f'{note.folder_path}/{file.path}')
            return update_files(reg,note_id)
        case 'edit_note':
            note_id = request.args.get('note')
            output = request.form.to_dict()
            return edit_note(note_id,output,request,reg)
        case 'edited':
            note_id = request.args.get('note')
            return edited(note_id,request,reg,template)
        case 'info':
            note_id = request.args.get('note')
            return get_info(note_id,reg)
        case 'update_files':
            note_id = request.args.get('note')
            create_folder = True if request.args.get('create_folder','false') == 'true' else False
            print('create_folder:',create_folder)
            if create_folder:
                update_files(reg,note_id)
            else:
                return update_files(reg,note_id)
        case 'upload_files':
            print('upload_files')
            note_id = request.args.get('note')
            note = db.session.scalar(select(Note).where(Note.id==note_id))
            if request.method == 'POST':
                print('post')
                files = request.files.getlist('files')
                checkboxes = request.form.getlist('checkboxes')
                print(checkboxes)
                for file in files:
                    print(file.filename,note.folder_path)
                    b_file = io.BytesIO(file.read())
                    b_file.name = file.filename
                    rst = upload_path(b_file,note.folder_path)
                    if rst and 'convert' in checkboxes:
                        if file.filename.split(".")[-1] in EXT.keys():
                            convert_office(rst['data']['display_path'])
                            if 'delete' in checkboxes:
                                print('we are going to delete')
                                delete_path(f'{note.folder_path}/{file.filename}')

                return update_files(reg,note_id)
            else:
                return render_template('modals/modal_upload_files.html',note=note)

        case 'new_from_template':
            template = request.args.get('template')
            note_id = request.args.get('note')
            return new_from_template(reg,note_id,template)
        case 'sign_despacho':
            note_id = request.args.get('note')
            back = True if request.args.get('back','false') == 'true' else False
            sign_despacho(note_id,back)
            trigger.append('state-updated')
        case 'mark_as_sent':
            note_id = request.args.get('note')
            mark_as_sent(note_id)
            trigger.append('state-updated')
        case 'notes_from_cg':
            notes_page = request.args.get('notes_page')
            return notes_from_cg(notes_page)


    if note_id:
        res = make_response(render_body_element(reg,note_id,'row',template))
    else:
        res = make_response(render_main_body(request,template))
    
    res.headers['HX-Trigger'] = ','.join(trigger)

    return res


def send_to_box(reg,note_id,back):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    users = db.session.scalars(select(User).where(User.groups.any(Group.txt=='scr')))
    if back:
        note.status = 'draft'
        updateSocks(users,"")
    else:
        note.status = 'queued'
        update_files(reg,note_id)
        updateSocks(users,f"There is new mail in {note.flow}box")

    db.session.commit()

def circulation_proposal(note_id,action):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    match action:
        case 'start':
            note.status = 'shared'
        case 'stop':
            note.status = 'draft'
        case 'restart':
            note.status = 'draft'
            for user in note.users:
                user.target_acted = False
        case 'forward':
            if note.result('num_sign_proposal') == note.result('num_target') - 1:
                note.status = 'approved'
            note.toggle_status_attr('target_acted')
        case 'back':
            note.status = 'denied'
        case 'reset':
            note.status = 'draft'
            for user in note.users:
                user.target_acted = False
 
    users = note.receiver + [note.sender]
    updateSocks(users,"")

    db.session.commit()

    if action in ['start','forward','back'] and note.status == 'shared':
        if note.status in ['approved','denied']:
            targets = [note.sender]
        elif action == 'start':
            targets = [user.user for user in note.users if note.result('is_current_target',user.user)]
        else:
            rst = note.current_status()
            targets = [user.user for user in note.users if note.current_status(user.user).target_order > rst.target_order and note.result('is_current_target',user.user)]

        send_emails(note,kind='proposal',targets=targets)


def toggle_archive(note_id,is_ctr=False):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    if note:
        if is_ctr:
            ctr = db.session.scalar(select(User).where(User.alias==session['ctr']['alias']))
            if ctr:
                note.toggle_status_attr('target_acted',ctr)
        else:
            note.toggle_status_attr('target_acted')
            if note.archived:
                if note.register.alias == 'mat':
                    toggle_share_permissions(note.folder_path,'editor')
                note.archived = False
            else:
                if note.register.alias == 'mat':
                    toggle_share_permissions(note.folder_path,'viewer')
                note.archived = False
        
        db.session.commit()


def toggle_read(note_id,file_clicked=False):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    if note:
        if note.register.alias != 'mat':
            if not file_clicked or not note.result('is_read'):
                note.toggle_status_attr('read')

def notes_from_cg(notes_page=None):
    month = date.today().replace(day=1)
    if notes_page:
        notes_page = int(notes_page)
        month -= relativedelta(months=notes_page)
        sdate = month
        edate = sdate + relativedelta(months = 1) - relativedelta(days = 1)
        notes = db.session.scalars(select(Note).where(Note.sender.has(User.alias.contains('cg')),Note.n_date>=sdate,Note.n_date<edate))
        return render_template("modals/modal_notes_from_cg_data.html",month=month,notes_page=notes_page,notes=notes)
    else:
        notes_page = 0
        sdate = month
        edate = sdate + relativedelta(months = 1) - relativedelta(days = 1)
        notes = db.session.scalars(select(Note).where(Note.sender.has(User.alias.contains('cg')),Note.n_date>=sdate,Note.n_date<edate))

        return render_template("modals/modal_notes_from_cg.html",month=month,notes_page=notes_page,notes=notes)

def mark_as_sent(note_id):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.status = 'sent'
    db.session.commit()


def sign_despacho(note_id,back):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.toggle_status_attr('sign_despacho')
    note.toggle_status_attr('read')

    db.session.commit()

    if note.result('num_sign_despacho') > 1:
        note.status = 'registered'
        db.session.commit()

    if note.status == 'registered':
        users = db.session.scalars(select(User).where(User.groups.any(Group.text=='cr')))
        send_emails(note,kind='from despacho')
    else:
        users = db.session.scalars(select(User).where(User.groups.any(Group.text=='despacho')))

    updateSocks(users,'')



def outbox_to_target(note_id=None,back=False):
    if note_id:
        notes = db.session.scalars(select(Note).where(Note.id==note_id)).all()
    else:
        notes = db.session.scalars(select(Note).where(Note.flow=='out',Note.status=='queued')).all()

    for note in notes:
        if back:
            note.status = 'draft'
        else:
            if note.status != 'sent' and note.path != f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/{note.reg} out":
                if not note.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/{note.reg} out"):
                    flash(f'Could not move note {note}')
                    continue
        
            note.status = 'sent'
            print('sent') 
            if note.register.alias == 'asr' or note.register.alias in ['vc','vcr'] and '-asr ' in note.fullkey:
                note.copy(f"/team-folders/Mail asr/Mail to asr")
                note.status = 'sent'
            elif note.register.alias == 'ctr':
                print('sending')
                send_emails(note)
                note.status = 'sent'
    
    users = db.session.scalars(select(User).where(User.groups.any(Group.text=='scr')))
    updateSocks(users,'')

    db.session.commit()


def download_eml(note_id):
    note = db.session.scalar(select(Note).where(Note.id==note_id))

    if note.reg in ['cg','dg','cc','desr']:
        rec = "cg@cardumen.lan"
    else:
        rec = ",".join([rec.email for rec in note.receiver])
    
    path = f"{current_user.local_path}/Outbox"


    return write_eml(rec,note,path)


def inbox_to_despacho(note_id=None,back=False):
    if note_id:
        notes = db.session.scalars(select(Note).where(Note.id==note_id)).all()
    else:
        notes = db.session.scalars(select(Note).where(Note.flow=='in',Note.status=='queued')).all()

    for note in notes:
        if back:
            note.status = 'draft'
        elif note.register.alias == 'ctr':
            import_ctr(note.id)
        elif 'despacho' in note.register.groups:
            note.status = 'despacho'
        else: # If it is not for despacho is a personal register and we send it to the final place
            note.status = 'registered'

    users = db.session.scalars(select(User).where(or_(User.groups.any(Group.text=='scr'),User.groups.any(Group.text=='despacho'))))
    updateSocks(users,'')

    db.session.commit()

def new_note(reg):
    form = NoteForm()
    form.set_disabled(current_user,None,reg)
    dnone = {}
    dnone['rec'] = 'd-none'
    choices = []
    for group in ['cr','ct_cg','ct_asr','ct_ctr','ct_r']:
        rg = group if group == 'cr' else group[3:]
        choices += [f"{rg} - {user.alias}" for user in db.session.scalars(select(User).where(User.active==1,User.groups.any(Group.text==group)).order_by(User.alias)).all()]
    form.sender.choices = choices
    form.reg.choices = ['cg','asr','ctr','r']
    return render_template('modals/modal_edit_note.html',note=None,dnone=dnone,form=form, reg=reg)

def created(reg,request):
    form = NoteForm(request.form)
    sender_alias = form.sender.data.split(' - ')[-1]
    sender = db.session.scalar(select(User).where(User.alias==sender_alias))
    #nt = Note(num=num,sender_id=ctr.id,reg=reg[0],register=register)
    print(form.content.data,form.sender.data)

def edit_note(note_id,output,request,reg):
    note = db.session.scalar(select(Note).where(Note.id==note_id))

    filter = output['search'] if 'search' in output else ''

    form = NoteForm(request.form,obj=note)
    form.set_disabled(current_user,note,reg)
    form = fill_form_note(reg,form,note,filter)

    despacho = True if reg[0] == 'des' else False

    return render_template('modals/modal_edit_note.html',note=note,form=form, reg=reg, dnone=visibility_note_form(reg,note), despacho=despacho)

def edited(note_id,request,reg,template):
    reg = ast.literal_eval(request.args.get('reg'))
    note_id = request.args.get('note')
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    
    form = NoteForm(request.form,obj=note)
    extract_form_note(reg,form,note)
    
    return render_body_element(reg,note_id,'row',template)

def get_info(note_id,reg):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    if reg[2] or not reg[2] and note.flow == 'in':
        if reg[2]:
            people = db.session.scalars( select(User).where(User.ctrs.any(User.alias==reg[2])).order_by(User.name) )
        else:
            people_id = db.session.scalars(select(NoteUser.user_id).where(NoteUser.note_id==note_id,or_(NoteUser.target,NoteUser.access.in_(['reader','editor'])))).all()
            print('people_id:',people_id)
            people = db.session.scalars(select(User).where(User.active==1,or_(User.id.in_(people_id),User.category=='dr')).order_by(User.name)).all()

        rst_yes = []
        rst_no = []
        for user in people:
            if note.result('is_read',user):
                rst_yes.append({'alias':user.name,'read':True})
            else:
                rst_no.append({'alias':user.name,'read':False})
        
        props = []
        if not reg[2]:
            props = db.session.scalars(select(Note).where(Note.ref.any(Note.id == note.id)))
            props = list(props)

        return render_template('notes/note_info.html',reg=reg,rst=rst_no + rst_yes,note=note,props=props)
    elif note.flow == 'out' and not reg[2]:
        ctrs = note.receiver
        rst = {}
        for ctr in ctrs:
            rst[ctr.alias] = {}
            rst[ctr.alias]['archived'] = note.result('is_done',ctr)
            people = db.session.scalars(select(User).where(User.ctrs.any(User.alias==ctr.alias)).order_by(User.name))
            rst_yes = []
            rst_no = []
            for user in people:
                if note.result('is_read',user):
                    rst_yes.append({'alias':user.name,'read':True})
                else:
                    rst_no.append({'alias':user.name,'read':False})
            rst[ctr.alias]['rst'] = rst_no + rst_yes

        return render_template('notes/note_info.html',reg=reg,rst=rst,note=note)

def visibility_note_form(reg,note):
    dnone = {'admin':'d-none','permanent':'d-none','date':'d-none','proc':'d-none','content':'d-none','content_jp':'d-none','comments':'d-none','comments_ctr':'d-none','ref':'d-none','rec':'d-none'}

    if reg[2]: # Note in a register of a ctr
        if note.flow == 'out': # Not IN for the ctr, only comments
            dnone['comments_ctr'] = ''
        else:
            dnone['date'] = ''
            dnone['content'] = ''
            dnone['content_jp'] = ''
            dnone['ref'] = ''
    else: # Everything else
        if current_user.admin:
            dnone['admin'] = ''
        
        if note.register.alias == 'mat' and (note.sender_id == current_user.id or current_user.admin):
            dnone['proc'] = ''

        if note.sender_id == current_user.id or 'despacho' in current_user.groups or current_user.admin: # My note, I can change everything
            dnone['permanent'] = ''
            dnone['date'] = ''
            dnone['content'] = ''
            dnone['content_jp'] = ''
            dnone['comments'] = ''
            dnone['ref'] = ''
            dnone['rec'] = ''

    return dnone

def import_ctr(id_note = None):
    # Searching for notes sent by the ctr. reg = ctr, flow = in and status = draft
    sender = aliased(User,name="sender_user")
    if id_note:
        notes = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(Note.id==id_note))
    else:
        notes = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg=='ctr',Note.flow=='in',Note.status=='queued')))

    for note in notes:
        rst = note.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/ctr in/")
        if rst:
            note.status = 'despacho'
            note.n_date = date.today()
        else:
            flash(f"Could not move note {note} to its destination")

    db.session.commit()

def update_files(reg,note_id):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    note.updateFiles()
   
    if reg[2] and session['version'] == 'old':
        res = make_response(render_template("notes/table/2_files_old.html",note=note, reg=reg))
    else:
        res = make_response(render_template("notes/table/2_files.html",note=note, reg=reg))
    res.headers['HX-Trigger'] = 'update-flash,update-action  s'

    return res

def new_from_template(reg,note_id,template):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    ext = template.split('.')[-1]
    cont = 0
    for file in note.files:
        if re.match(fr'{note.folder_name}_*a*[0-9]*\.[a-zA-Z]+',file.path):
            print(file.path)
            cont += 1

    if cont == 0:
        copy_office_path(f"/team-folders/Data/Templates/{template}",f"{note.folder_path}/{note.folder_name}.{ext}")
    else:
        copy_office_path(f"/team-folders/Data/Templates/{template}",f"{note.folder_path}/{note.folder_name}_a{cont}.{ext}")

    return update_files(reg,note_id)

