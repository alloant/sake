#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re

from datetime import date

from flask import render_template, flash, current_app, session
from flask_login import current_user

from sqlalchemy import select, and_, func, delete, or_
from sqlalchemy.orm import aliased

from app import db
from app.models import Note, File, User, Register, get_note_fullkey

from app.models.nas.nas import files_path, move_path, delete_path, convert_office
from app.syneml import read_eml


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
                    flash(f"File {filename} has been added to database")
                else:
                    flash(f"File {filename} is already in the database. The copy file in Mail/IN")
                

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
        
        ref = False

        if "@" in file.sender:
            sender = db.session.scalar(select(User).where(User.email==file.sender))
        else:
            sender = db.session.scalar(select(User).where(User.alias==file.sender))

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



