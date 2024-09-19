#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import os
import re

from datetime import date, datetime

from flask import render_template, flash, current_app, session, make_response
from flask_login import current_user
from flask_babel import gettext

from sqlalchemy import select, and_, func, delete, or_
from sqlalchemy.orm import aliased

from app import db
from app.src.models import Note, File, User, Register, get_note_fullkey

from app.src.models.nas.nas import files_path, move_path, delete_path, convert_office, upload_path
from app.src.tools.syneml import read_eml

EXT = {'xls':'osheet','xlsx':'osheet','docx':'odoc','rtf':'odoc'}


def action_inbox_view(request):
    action = request.args.get('action')
    
    match action:
        case 'update_file':
            return render_template('inbox/modal_update_file.html')
        case 'updated_file':
            files = request.files.getlist('files')
            dest = f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN"
            for file in files:
                b_file = io.BytesIO(file.read())
                b_file.name = file.filename
                rst = upload_path(b_file,dest)
                if rst:
                    if file.filename.split(".")[-1] in EXT.keys():
                        print(rst)
                        path,fid,link = convert_office(rst['data']['display_path'])
                        move_path(rst['data']['display_path'],f"{dest}/Originals")
                    
                    fl = File(path=path,permanent_link=link,date=datetime.now().date())
                    db.session.add(fl)
                    flash(f"{fl} has been added to the database",'success')
            db.session.commit()

        case 'import_eml':
            return render_template('inbox/modal_import_eml.html')
        case 'eml_imported':
            files = request.files.getlist('files')
            for file in files:
                read_eml(file.read())
        case 'import_asr':
            import_asr()
        case 'import_ctr':
            id_note = request.args.get('note',None)
            import_ctr(id_note)
            return inbox_main_view(request)
        case 'generate_notes':
            output = request.form.to_dict()
            generate_notes(output)
        case 'remove_file':
            file = request.args.get('file')
            remove_file(file)
        case 'report_cg':
            output = request.form.to_dict()
            
            dates = output['daterange'].split(' - ')
            sdate = datetime.strptime(dates[0],"%m/%d/%Y")
            edate = datetime.strptime(dates[1],"%m/%d/%Y")
            
            notes = db.session.scalars(select(Note).where(or_(Note.receiver.any(User.alias == 'cg'),and_(Note.reg.in_(['cg','cc','desr','dg']),Note.flow=='out')),Note.n_date>=sdate,Note.n_date<=edate,Note.state==6))
            path = f"{current_user.local_path}/Outbox"
            dates = f"{sdate.strftime('%d/%m/%Y')} - {edate.strftime('%d/%m/%Y')}"
           
            body = ""
            for note in notes:
                body += f"{note.date} - {note.fullkey}\n"
            body += f"\n\nSingapur, {date.today()}"
            session['eml'] = {'body':body,'dates':dates,'path':path}
            return ""
        case 'transfer':
            from app.src.tools.tools import toNewNotesStatus
            toNewNotesStatus()

    res = make_response(inbox_body_view(request))
    res.headers['HX-Trigger'] = 'update-flash'

    return res



def inbox_main_view(request):
    session['reg'] = ['import','in','']
    dark = '-dark' if session['theme'] == 'dark-mode' else ''

    title = {}
    title['icon'] = f'static/icons/00-import{dark}.svg'
    title['text'] = gettext(u'Import files into Sake')


    sql = select(File).where(File.note_id == None)
    files = db.paginate(sql, per_page=22)
    
    ctr_notes = db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==0))),db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==1)))
    
    notes = db.session.scalars(select(Note).where(Note.flow=='in',Note.reg=='ctr',Note.state==1))
    
    res = make_response(render_template('inbox/main.html',title=title, files=files, ctr_notes=ctr_notes,notes=notes))
    res.headers['HX-Trigger'] = 'update-main'

    return res



def inbox_body_view(request):
    sql = select(File).where(File.note_id == None)
    files = db.paginate(sql, per_page=22)
    
    return render_template('inbox/table.html', files=files)



def remove_file(file_id):
    file = db.session.scalar(select(File).where(File.id==file_id))
    db.session.delete(file)
    db.session.commit()
    return delete_path(file.path)

def import_asr(): 
    # Searching for notes in from asr
    #asr_files = files_path(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/Mail asr/Inbox")
    asr_files = files_path(f"/team-folders/Mail asr/Mail from asr")
    if asr_files:
        for file in asr_files:
            filename = file['display_path'].split("/")[-1]
            flash(f"Found file {filename}",'info')
            rst = move_path(file['display_path'],f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN")
            if rst:
                flash(f"Moved file {filename}",'info')
                path = f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN/{filename}"
                link = file['permanent_link']
                if filename.split(".")[-1] in ['xls','xlsx','docx','rtf']:
                    path,fid,link = convert_office(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN/{filename}")
                    move_path(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN/{filename}",f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN/Originals")
                
                rnt = db.session.scalar(select(File).where(and_(File.path.contains(filename),File.sender=='asr')))
                exists = False
                if rnt: # Note same name but could be different year
                    dt = rnt.note.year if rnt.note else rnt.date.year 
                    if dt == date.today().year:
                        exists = True
                
                if not exists:
                    fl = File(path=path,permanent_link=link,sender="asr",date=date.today())
                    db.session.add(fl)
                    flash(f"File {filename} has been added to database",'success')
                else:
                    flash(f"File {filename} is already in the database. The copy file in Mail/IN",'warning')

            else:
                flash(f"Could not move file {filename}",'danger')
                

        db.session.commit()

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

def generate_notes(output):
    # All the files in import view. The ones without a note
    files = db.session.scalars(select(File).where(File.note_id==None))
    involved_notes = []
    for file in files:
        # Get the prot and the rest from the form in inbox
        prot = output[f"number_{file.id}"].lower()
        prots = re.findall(r'\w+',prot)
        register_field = output[f"register_{file.id}"].lower()
        sender_field = output[f"sender_{file.id}"].lower()

        # Find here the sender in the database. Could be the alias or the email
        if "@" in sender_field:
            sender = db.session.scalar(select(User).where(User.email==sender_field))
        else:
            sender = db.session.scalar(select(User).where(User.alias==sender_field))

        if not sender: # We cannot continue if there is no sender
            continue

        register = db.session.scalar(select(Register).where(Register.alias==register_field))

        if not register:
            continue

        fullkey = f"{sender.alias} {prot}" #before gfk

        # Check if the note already exist in the database
        note = get_note_fullkey(fullkey)

        if note: # There is note already. Then this is a ref or a new version
            rst = note.addFile(file)
            if rst:
                if not note in involved_notes:
                    involved_notes.append(note)
                note.state = 1   
                flash(f"{file} was added to {nt}")
        else: # We need to create a new note
            # First get the content if possible, if not empty
            content = "" 
            if ";" in file.subject:
                parts = file.subject.split(";")
                if "/" in parts[0]:
                    content = parts[1]

            # Get number and year from fullkey
            num = re.findall(r'\d+',fullkey)[0]
            year = re.findall(r'\d+',fullkey)[1]

            # The state is 1 because they all go to inbox
            note = Note(num=num,year=f"20{year}",sender_id=sender.id,reg=register_field,register=register,state=1,content=content)

            note.addFile(file)
            # I put the date of the note
            file.date = note.n_date

            if not note in involved_notes:
                involved_notes.append(note)

            db.session.add(note)

            flash(f"{note} was created")
            flash(f"{file} was added to {note}")

            refs = file.guess_ref

            for ref in refs:
                note.ref.append(ref)

            if len(refs) != len(note.ref): # I didn't get all refs
                flash(f"There was a problem with {file.subject}. Not all references are in place")

        db.session.commit()



