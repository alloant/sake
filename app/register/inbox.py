#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re

from datetime import date

from flask import render_template, flash, url_for, current_app, request, session
from flask_login import current_user

from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, File, User
from app.models.nas.nas import files_path, move_path, delete_path, convert_office
from app.syneml import read_eml

def inbox_view(request):
    output = request.form.to_dict()
    args = request.args
    
    do_check = False
    rm_file = args.get('remove_file')

    #from app.tools import find_files, import_dates, change_file_dates,get_pass_nas
    #get_pass_nas()
    #change_file_dates()
    #import_dates()
    #find_files()
    #print(output)
 
    if rm_file:
        do_check = True
        file = db.session.scalar(select(File).where(File.id==rm_file))
        db.session.delete(file)
        db.session.commit()
        rst = delete_path(file.path)
        #if rst:
        #    db.session.execute(delete(File).where(File.id==rm_file))
    elif "upload" in output:
        uploaded_files = request.files.getlist('files')
        for file in uploaded_files:
            read_eml(file.read())
    elif "getmail_asr" in output:
        do_check = True
        # Searching for notes in from asr
        #asr_files = files_path(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/Mail asr/Inbox")
        asr_files = files_path(f"/team-folders/Mail asr/Mail from asr")
        if asr_files:
            for file in asr_files:
                rst = move_path(file['display_path'],f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN")
                if rst:
                    filename = file['display_path'].split("/")[-1]
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
                    else:
                        flash(f"File {filename} is already in the database. The copy file in Mail/IN")
                    

            db.session.commit()

    elif "getmail" in output:
        do_check = True
        
        # Searching for notes sent by the ctr. reg = ctr, flow = in and state = 1
        sender = aliased(User,name="sender_user")
        notes = db.session.scalars(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.reg=='ctr',Note.flow=='in',Note.state==1)))
        for note in notes:
            rst = note.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{note.year}/ctr in/")
            if rst:
                note.state = 3
                note.n_date = date.today()

        db.session.commit()

    elif "notesfromfiles" in output:
        do_check = True
        files = db.session.scalars(select(File).where(File.note_id==None))
        involved_notes = []
        print('NOTES')
        for file in files:
            prot = output[f"number_{file.id}"].lower()
            prots = re.findall(r'\w+',prot)
            
            
            ref = False
            print(len(prots),prots)
            if len(prots) > 2:
                if len(prots) == 3:
                    if prots[0] == 'ref':
                        ref = True
                        pt = "cg"
                    else:
                        pt = prots[0]
                elif len(prots) == 4:
                    print('here')
                    ref = True
                    pt = prots[1]

                gfk = f"{pt} {prots[-2]}/{prots[-1]}"
            else:
                gfk = file.guess_fullkey(prot)
            

            if gfk == "":
                continue

            content = "" 
            if ";" in file.subject:
                parts = file.subject.split(";")
                if "/" in parts[0]:
                    content = parts[1]

            sender = aliased(User,name="sender_user")
            nt = db.session.scalar(select(Note).join(Note.sender.of_type(sender)).where(Note.fullkey==gfk))
            if ref and nt:
                rnt = db.session.scalar(select(Note).join(Note.sender.of_type(sender)).where(and_(Note.num==0,Note.ref.contains(nt))))
            else:
                rnt = None

            print("rnt",rnt,nt)
                 
            
            if rnt:
                print('!@#!@#',rnt,rnt.path_note)
                rst = file.move_to_note(f"{rnt.path_note}")
                if rst:
                    rnt.addFile(file)
                if not rnt in involved_notes: involved_notes.append(rnt)
            elif nt and not ref:
                rst = file.move_to_note(f"{nt.path_note}")
                if rst:
                    nt.addFile(file)
                if not nt in involved_notes: involved_notes.append(nt)
            else: # We need to create the note
                if ref:
                    nref = nt

                num = re.findall(r'\d+',gfk)[0]                
                year = re.findall(r'\d+',gfk)[1]                
                
                if "@" in file.sender:
                    sender = db.session.scalar(select(User).where(User.email==file.sender))
                else:
                    sender = db.session.scalar(select(User).where(User.alias==file.sender))

                if not sender:
                    continue
            
                preg = re.findall(r'\S+',gfk)
                state = 3
                if preg[0] in ['vc','vcr','dg','cc','desr']:
                    nreg = preg[0]
                    state = 5
                elif file.sender == 'cg@cardumen.lan':
                    nreg = 'cg'
                elif file.sender == 'asr':
                    nreg = 'asr'
                else:
                    nreg = 'r'
                
                if ref:
                    nt = Note(num=0,year=f"20{year}",sender_id=sender.id,reg=nreg,state=state,content=content,ref=[nref])
                    #nt.ref.append(nref)
                else:
                    nt = Note(num=num,year=f"20{year}",sender_id=sender.id,reg=nreg,state=state,content=content)
                
                print('@@',nt.path_note)
                rst = file.move_to_note(nt.path_note)
                if rst:
                    nt.addFile(file)
                
                if not nt in involved_notes: involved_notes.append(nt)
                db.session.add(nt)
        
            refs = file.guess_ref
            if refs:
                rfs = []
                for rf in refs:
                    rfs.append(rf[1])

                nrefs = db.session.scalars(select(Note).where(Note.id.in_(rfs))).all()
                for nr in nrefs:
                    nt.ref.append(nr)
            
                if len(refs) != len(nrefs): # I didn't get all refs
                    flash(f"There was a problem with {file.subject}. Not all references are in place")
        
            db.session.commit()

        for note in involved_notes:
            note.updateFiles()



    sql = select(File).where(File.note_id == None)
    page = args.get('page', 1, type=int)
    files = db.paginate(sql, per_page=30)
    prev_url = url_for('register.inbox_scr', page=files.prev_num) if files.has_prev else None
    next_url = url_for('register.inbox_scr', page=files.next_num) if files.has_next else None

    # Some indicators to help
    if do_check and False:
        #ctr_notes = db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==1)))
        #asr_files = len(files_path("{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/Mail asr/Inbox"))
        IN_db = db.session.scalar(select(func.count(File.id)).where(File.note_id == None))
        check_files = files_path(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN")
        
        if check_files:
            IN_files = len(check_files) - 1
        else:
            IN_files = 0

        if IN_db != IN_files:
            flash(f"The number of files in the database is not the same as in Mail/IN ({IN_db}/{IN_files})")

    #flash(f'There are {IN_files} in Mail/IN, {ctr_notes} waiting from ctrs and {asr_files} in Inbox asr')
    ctr_notes = db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==0))),db.session.scalar(select(func.count(Note.id)).where(and_(Note.flow=='in',Note.reg=='ctr',Note.state==1)))
    return render_template('inbox/main.html',title="Inbox cr", files=files, page=page, ctr_notes=ctr_notes, prev_url=prev_url, next_url=next_url)


