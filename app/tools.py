#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import current_app
from flask_login import current_user

from sqlalchemy import select 
from app import db
from app.models import File, Note, User
from app.models.nas.nas import files_path, copy_path, create_folder

from cryptography.fernet import Fernet

def check_folders_synology():
    create_folder(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Minutas/",current_user.alias)
    create_folder(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Minutas/{current_user.alias}","Notes")


def get_pass_nas():
    cipher = Fernet(current_app.config['SECRET_KEY'])
    PASSWD = cipher.decrypt(db.session.scalar(select(User).where(User.alias=='lc')).password_nas)
    print(PASSWD)

def import_dates():
    import csv
    with open('out2023_final.csv') as csvfile:
        spamreader = csv.reader(csvfile)
        for row in spamreader:
            if not row[0].isdigit(): continue
            nt = db.session.scalar(select(Note).where(Note.id==int(row[0])))
            if nt:
                print(nt.id,nt.n_date,row[4])
                nt.n_date = row[4]
        db.session.commit()


def change_file_dates():
    files = db.session.scalars(select(File)).all()
    for file in files:
        nt= db.session.scalar(select(Note).where(Note.id==file.note_id))
        if nt:
            file.date = nt.n_date
    db.session.commit()

def find_files():
    print("FInd files")
    year = 2024
    regs = ['cg','asr','ctr','r']
    
    regs = ['r']
    flow = 'out'
    
    notes = db.session.scalars(select(Note).where(Note.num>0,Note.files==None,Note.year==year,Note.flow==flow))
    
    only_update = False

    for reg in regs:
        #break
        files_cg = files_path(f"/team-folders/Archive/{reg} {flow} {year}")
        
        for note in notes:
            if note.reg == reg:
                for file in files_cg:
                    if only_update: break
                    #print(note.note_folder,file['path'])
                    if note.note_folder in file['path']:
                        if file['content_type'] == 'dir':
                            files_temp = files_path(f"/team-folders/Archive{file['path']}")
                            if not files_temp:
                                continue
                            for tfile in files_temp:
                                copy_path(f"/team-folders/Archive{tfile['path']}",f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{year}/{reg} {flow}/{note.note_folder}/{tfile['path'].split('/')[-1]}")
                        else:
                            copy_path(f"/team-folders/Archive{file['path']}",f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{year}/{reg} {flow}/{note.note_folder}/{file['path'].split('/')[-1]}")
            
                note.updateFiles()

    change_file_dates()

