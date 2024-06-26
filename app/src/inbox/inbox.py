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
            import_ctr()
            return inbox_main_view(request)
        case 'generate_notes':
            output = request.form.to_dict()
            generate_notes(output)
        case 'remove_file':
            file = request.args.get('file')
            remove_file(file)

    res = make_response(inbox_body_view(request))
    res.headers['HX-Trigger'] = 'update-flash'

    return res



def inbox_main_view(request):
    session['reg'] = ['box','in','']
    dark = '-dark' if session['theme'] == 'dark-mode' else ''

    title = {}
    title['icon'] = f'static/icons/00-inbox{dark}.svg' 
    title['text'] = gettext(u'Inbox cr')


    sql = select(File).where(File.note_id == None)
    files = db.paginate(sql, per_page=22)
    
    ctr_notes = db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==0))),db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==1)))
    
    return render_template('inbox/main.html',title=title, files=files, ctr_notes=ctr_notes)

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

def import_ctr():
    # Searching for notes sent by the ctr. reg = ctr, flow = in and state = 1
    sender = aliased(User,name="sender_user")
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
    files = db.session.scalars(select(File).where(File.note_id==None))
    involved_notes = []
    for file in files:
        prot = output[f"number_{file.id}"].lower()
        prots = re.findall(r'\w+',prot)
        register_field = output[f"register_{file.id}"].lower()
        sender_field = output[f"sender_{file.id}"].lower()

        ref = False

        if "@" in sender_field:
            sender = db.session.scalar(select(User).where(User.email==sender_field))
        else:
            sender = db.session.scalar(select(User).where(User.alias==sender_field))

        if len(prots) > 2:
            if len(prots) == 3:
                if prots[0] == 'ref':
                    ref = True
                    pt = "cg"
                else:
                    pt = prots[0]
            elif len(prots) == 4:
                ref = True
                pt = prots[1]

            gfk = f"{pt} {prots[-2]}/{prots[-1]}"
        else:
            if not sender:
                continue
            gfk = f"{sender.alias} {prot}"

        nt = get_note_fullkey(gfk)
        
        if not gfk:
            continue

        content = "" 
        if ";" in file.subject:
            parts = file.subject.split(";")
            if "/" in parts[0]:
                content = parts[1]

        sndr = aliased(User,name="sender_user")
        #nt = db.session.scalar(select(Note).join(Note.sender.of_type(sender)).where(Note.fullkey==gfk))
        
        if ref and nt:
            rnt = db.session.scalar(select(Note).join(Note.sender.of_type(sndr)).where(and_(Note.num==0,Note.ref.contains(nt))))
        else:
            rnt = None

        if rnt:
            #rst = file.move_to_note(f"{rnt.folder_path}")
            rst = rnt.addFile(file)
            if rst:
                if not rnt in involved_notes: involved_notes.append(rnt)
                flash(f"{file} was added to {nt}")
        elif nt and not ref:
            #rst = file.move_to_note(f"{nt.folder_path}")
            rst = nt.addFile(file)
            if rst:
                if not nt in involved_notes: involved_notes.append(nt)
                flash(f"{file} was added to {nt}")
        else: # We need to create the note
            if ref:
                nref = nt

            num = re.findall(r'\d+',gfk)[0]                
            year = re.findall(r'\d+',gfk)[1]                
            
            
            if not sender:
                continue
           

            state = 3
            if register_field in ['dg','cc','desr']:
                state = 5
            
            register = db.session.scalar(select(Register).where(Register.alias==register_field))

            if ref:
                nt = Note(num=0,year=f"20{year}",sender_id=sender.id,reg=register_field,register=register,state=state,content=content,ref=[nref])
                #nt.ref.append(nref)
            else:
                nt = Note(num=num,year=f"20{year}",sender_id=sender.id,reg=register_field,register=register,state=state,content=content)
            
            
            nt.addFile(file)
            
            if not nt in involved_notes: involved_notes.append(nt)
            db.session.add(nt)
            flash(f"{nt} was created")
            flash(f"{file} was added to {nt}")
    
            refs = file.guess_ref

            for ref in refs:
                nt.ref.append(ref)
        
            if len(refs) != len(nt.ref): # I didn't get all refs
                flash(f"There was a problem with {file.subject}. Not all references are in place")
    
        db.session.commit()



