#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re
from datetime import date
from dateutil.relativedelta import relativedelta

from flask import render_template, session, make_response, current_app
from flask_login import current_user

from sqlalchemy import select, and_, or_, func, not_
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased

from flask_babel import gettext

from app import db
from app.src.models import Note, User, Register, File
from app.src.forms.note import NoteForm
from app.src.notes.edit import fill_form_note, extract_form_note, updateSocks
from app.src.notes.renders import render_main_body, render_body_element

from app.src.tools.tools import newNote, sendmail, delete_note
from app.src.tools.syneml import write_eml

from app.src.models.nas.nas import toggle_share_permissions

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
                newNote(current_user,reg)
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
            return update_files(reg,note_id)
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
    users = db.session.scalars(select(User).where(User.contains_group('scr')))
    if back:
        note.state = 0
        updateSocks(users,"")
    else:
        note.state = 1
        update_files(reg,note_id)
        updateSocks(users,f"There is new mail in {note.flow}box")

    db.session.commit()

def circulation_proposal(note_id,action):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    match action:
        case 'start':
            note.state = 1
        case 'stop':
            note.state = 0
        case 'restart':
            note.state = 0
            note.read_by = ''
            for status in note.status:
                status.target_acted = False
        case 'forward':
            note.toggle_status_attr('target_acted')
            if '|' in note.received_by and not '|' in note.read_by: # When there is not | or all the people together had read the note
                together,sequence = note.received_by.split('|')
                together = together.split(',')
                read = note.read_by.split(',')
                rst = []
                for alias in together:
                    if alias in read:
                        rst.append(alias)
                note.read_by = ','.join([alias for alias in rst if alias])
                if rst == together:
                    note.read_by += '|'
            else:
                note.read_by += f',{current_user.alias}' if note.read_by and note.read_by[-1] != '|' else current_user.alias

            if note.read_by == note.received_by:
                note.state = 5
        case 'back':
            note.state = 0
        case 'reset':
            note.state = 0
            note.read_by = ''
            for status in note.status:
                status.target_acted = False
 
    users = note.receiver + [note.sender]
    updateSocks(users,"")

    db.session.commit()


def toggle_archive(note_id,is_ctr=False):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    if note:
        if is_ctr:
            ctr = db.session.scalar(select(User).where(User.alias==session['ctr']['alias']))
            if ctr:
                note.toggle_status_attr('target_acted',ctr)
                ctr_acted = note.received_by.split(',')
                if ctr.alias in ctr_acted:
                    ctr_acted.remove(ctr.alias)
                else:
                    ctr_acted.append(ctr.alias)
                note.received_by = ','.join([alias for alias in ctr_acted if alias])
        else:
            note.toggle_status_attr('target_acted')
            if note.state == 6:
                if note.register.alias == 'mat':
                    toggle_share_permissions(note.folder_path,'editor')
                note.state = 5
            else:
                if note.register.alias == 'mat':
                    toggle_share_permissions(note.folder_path,'viewer')
                note.state = 6
        
        db.session.commit()


def toggle_read(note_id,file_clicked=False):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    #print('preview:',note.preview)
    if note:
        if note.register.alias != 'mat':
            if not file_clicked or not note.result('is_read'):
                note.toggle_status_attr('read')
                read_by = note.read_by.split(',')
                if current_user.alias in read_by:
                    read_by.remove(current_user.alias)
                else:
                    read_by.append(current_user.alias)

                note.read_by = ','.join([alias for alias in read_by if alias])
                db.session.commit()

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
    note.state = 6
    db.session.commit()


def sign_despacho(note_id,back):
    note = db.session.scalar(select(Note).where(Note.id==note_id))
    read_by = note.read_by.split(',')
    if f'des_{current_user.alias}' in read_by:
        note.state -= 1
        read_by.remove(f'des_{current_user.alias}')
    else:
        note.state += 1
        read_by.append(f'des_{current_user.alias}')
    
    note.read_by = ','.join([alias for alias in read_by if alias])
    note.toggle_status_attr('sign_despacho')
    note.toggle_status_attr('read')

    db.session.commit()

    if note.state == 5:
        users = db.session.scalars(select(User).where(User.contains_group('cr')))
    else:
        users = db.session.scalars(select(User).where(User.contains_group('despacho')))

    updateSocks(users,'')



def outbox_to_target(note_id=None,back=False):
    if note_id:
        notes = db.session.scalars(select(Note).where(Note.id==note_id)).all()
    else:
        notes = db.session.scalars(select(Note).where(Note.flow=='out',Note.state==1)).all()

    for note in notes:
        if back:
            note.state = 0
        else:
            if note.register.alias in ['cg','r'] and note_id or note.register.alias in ['asr','ctr']: #Here only when you choose one note
                if not note.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/{note.reg} out"):
                    continue

            if note.register.alias in ['cg','r'] and note_id:
                note.state = 6
            elif note.register.alias == 'asr':
                note.copy(f"/team-folders/Mail asr/Mail to asr")
                note.state = 6
            elif note.register.alias == 'ctr':
                note.state = 6
    
    users = db.session.scalars(select(User).where(User.contains_group('scr')))
    updateSocks(users,'')

    db.session.commit()


def download_eml(note_id):
    note = db.session.scalar(select(Note).where(Note.id==note_id))

    #if note.state < 6:
    #    if note.reg in ['vc','vcr','dg','cc','desr']:
    #        rst = note.move(f"/team-folders/Mail {note.reg}/Notes/{note.year}/{note.reg} out")
    #    else:
    #        rst = note.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/{note.reg} out")

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
        notes = db.session.scalars(select(Note).where(Note.flow=='in',Note.state==1)).all()

    for note in notes:
        if back:
            note.state = 0
        elif note.register.alias == 'ctr':
            import_ctr(note.id)
        elif 'despacho' in note.register.r_groups.split(','):
            note.state = 3
        else: # If it is not for despacho is a personal register and we send it to the final place
            note.state = 5

    users = db.session.scalars(select(User).where(or_(User.contains_group('scr'),User.contains_group('despacho'))))
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
        choices += [f"{rg} - {user.alias}" for user in db.session.scalars(select(User).where(User.active==1,User.contains_group(group)).order_by(User.alias)).all()]
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
            people = db.session.scalars(select(User).where(User.contains_group(f'v_ctr_{reg[2]}')).order_by(User.name))
        else:
            fn = [and_(User.contains_group('cr'),not_(User.contains_group('of')))]
            has_access = note.privileges.split(',') + [user.alias for user in note.receiver]
            fn.append(and_(User.contains_group('of'),User.alias.in_(has_access)))
            people = db.session.scalars(select(User).where(and_(User.active==True,or_(*fn))).order_by(User.name))

        rst_yes = []
        rst_no = []
        for user in people:
            if note.is_read(user):
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
            rst[ctr.alias]['archived'] = note.is_done(ctr)
            people = db.session.scalars(select(User).where(User.contains_group(f'v_ctr_{ctr.alias}')).order_by(User.name))
            rst_yes = []
            rst_no = []
            for user in people:
                if note.is_read(user):
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
    # Searching for notes sent by the ctr. reg = ctr, flow = in and state = 1
    sender = aliased(User,name="sender_user")
    if id_note:
        notes = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(Note.id==id_note))
    else:
        notes = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg=='ctr',Note.flow=='in',Note.state==1)))

    for note in notes:
        rst = note.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/ctr in/")
        if rst:
            note.state = 3
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
    res.headers['HX-Trigger'] = 'update-flash,update-actions'

    return res

