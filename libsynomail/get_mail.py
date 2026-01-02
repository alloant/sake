#!/bin/python
import re
from datetime import datetime
from pathlib import Path
import logging

from libsynomail import EXT
from libsynomail.classes import File, Note
from libsynomail.scrap_register import Register
from libsynomail.syneml import write_eml

from libsynomail.nas import files_path,send_message
from libsynomail.register import write_register, read_register, join_registers


def init_config(config):
    global CONFIG
    CONFIG = config

def get_notes_in_folders(folders,ctrs):
    files = []
    paths = []
    for key,path in folders.items():
        if key in ['ctr','dr']:
            for ctr in ctrs:
                value = ctr if 'name' not in ctrs[ctr] else ctrs[ctr]['name']
                paths.append([key,ctr,path.replace('@',value)])
        else:
            paths.append([key,'',path])
    
    for path in paths:
        logging.debug(f"Checking path {path}")
        files_in_folder = files_path(path[2])
        
        if not files_in_folder: continue

        for file in files_in_folder:
            logging.info(f"Found in {path[0]} {path[1]}: {file['name']}")
            if path[0] == 'r':
                if 'r_' in file['name']:
                    source = file['name'].split("_")[1]
                else:
                    source = file['name']
            else:
                source = path[1]
            
            register = "cr"
            for reg,item in CONFIG['registers'].items():
                if source in item['source'] and item['pattern'] in file['name']:
                    register = reg
                    break

            files.append({"register":register,"type": path[0],"source": source,"file": File(file)})
    
    
    return files

def notes_from_files(files,flow = 'in'):
    notes = {}
    
    files.sort(reverse=True,key = lambda file: f"{file['main']}_{file['file']}")

    for file in files:
        if file['num'] != "": 
            note = Note(file['register'],file['type'],file['source'],file['num'],flow,file['ref'],year=file['year'])
            if not note.key in notes:
                notes[note.key] = note
            
            notes[note.key].addFile(file['file'])
        else:
            file['file'].move(f"{CONFIG['folders']['despacho']}/Inbox Despacho")
            if file['file'].ext in EXT:
                file['file'].convert()

    return notes


def manage_files_despacho(path_files,files,is_from_dr = False):
    flow = 'out' if is_from_dr else 'in'
    notes = notes_from_files(files,flow)
    
    if not notes_from_files: return None
    
    if is_from_dr: #We only need this for the dr to know where they are sending the note
        register = Register('out',CONFIG['folders']['archive'])
    
    path_notes = f"{path_files}/ToSend" if is_from_dr else f"{path_files}/Notes"
    path_register = f"{path_files}/ToSend" if is_from_dr else f"{path_files}/Inbox Despacho"
    

    try:
        for note in notes.values():
            for i,file in enumerate(note.files):
                # Getting information about the note from Mail out
                if is_from_dr:
                    if note.register == 'cr' and register != None:
                        note.dept,note.content,note.ref = register.scrap_destination(note.no)
                    elif note.register in CONFIG['registers']:
                        note.dept = CONFIG['registers'][note.register]['dest']
            note.organice_files_to_despacho(f"{path_notes}",CONFIG['folders']['originals'])
    except Exception as err:
        logging.error(err)
        logging.error("There was some error managing the notes")

    write_register(f"{path_register}",notes,CONFIG['BROWSER'])
    #join_registers(f"{path_register}",flow,notes,CONFIG['BROWSER'])
    
    return notes


def rec_in_groups(recipients,RECIPIENTS,ctr = True):
    send_to = []
    if recipients == 'all':
        for key in RECIPIENTS:
            send_to.append(key)
        
        return list(set(send_to))


    recs = [rec.strip() for rec in recipients.split(',')]
    send_to = []
    ex_groups = []
    in_groups = []

    for rec in recs:
        if rec in RECIPIENTS:
            send_to.append(rec)
        else: #rec is a groups
            if rec.lower() == rec:
                in_groups.append(rec)
            else:
                ex_groups.append(rec.lower())

    for key,rec in RECIPIENTS.items():
        putin = True
        for gp in ex_groups:
            if not gp in rec['groups']:
                putin = False
                break

        if putin:
            if in_groups:
                for gp in in_groups:
                    if gp in rec['groups']:
                        send_to.append(key)
            else:
                if ex_groups:
                    send_to.append(key)

    return list(set(send_to))

def new_mail_ctr(note):
    send_to = rec_in_groups(note.dept,CONFIG['ctrs'],True)
    rst = True
    cont = 0
    for st in send_to:
        if not st.lower() in note.sent_to.lower().split(","):
            rst = note.copy(CONFIG['mail_out']['ctr'].replace('@',st))
            
            if rst:
                note.sent_to += f",{st}" if note.sent_to else st
                cont += 1
    
    if cont == len(send_to):
        return True
    else:
        return False

def new_mail_eml(note):
    send_to = rec_in_groups(note.dept,CONFIG['r'],False)
    TO = []
    recipients = ""
    for st in send_to:
        if not st.lower() in note.sent_to.lower():
            recipients += f",{st}" if recipients else st
            TO.append(CONFIG['r'][st]['email'])
    if TO:
        if write_eml(",".join(TO),note,CONFIG['folders']['local_folder']):
            note.sent_to += f",{recipients}" if note.sent_to else recipients
            return True
    return False

def new_mail_asr(note):
    rst = True
    if not 'asr' in note.sent_to.lower():
        for file in note.files:
            if not file.copy(CONFIG['mail_out']['asr']):
                rst = False
        if rst:
            note.sent_to += f",asr" if note.sent_to else 'asr'
            return True

    return False

def register_notes(is_from_dr = False):
    register_dest = CONFIG['folders']['to_send'] if is_from_dr else f"{CONFIG['folders']['despacho']}/Outbox Despacho"
    flow = 'out' if is_from_dr else 'in'
    notes = read_register(register_dest,flow)
    
    if not notes: return None
    
    try:
        for note in notes.values():
            # Moving note to archive if needed
            if not note.archived and note.dept != '':
                if is_from_dr:
                    dest = f"{CONFIG['folders']['archive']}/{note.archive_folder}"
                else:
                    dest = f"{CONFIG['folders']['archive']}/{note.archive_folder}"


                if note.register == 'cr':
                    if note.move(dest):
                        note.archived = True
                        logging.info(f"Note {note.key} was archived")

            # Sending copy/message of note to recipient
            if (note.archived or note.register != 'cr') and note.dept != '':
                if is_from_dr: # Is mail out
                    if note.no < 250: #cg
                        rst = new_mail_eml(note)
                    elif note.no < 1000: #asr
                        rst = new_mail_asr(note)
                    elif note.no < 2000: #ctr
                        rst = new_mail_ctr(note)
                    else: #r
                        rst = new_mail_eml(note)

                    if rst: logging.info(f"Note {note.key} was copied/converted eml")
                else: # Is mail in to one/several dr
                    depts = [dep.lower().strip() for dep in note.dept.split(',')]
                    for dep in depts:
                        if not dep.lower() in note.sent_to.lower():
                            rst = send_message(dep,CONFIG['deps'],note.message)
                            if rst:
                                note.sent_to += f",{dep}" if note.sent_to else dep
                                logging.info(f"Message to {dep} about {note.key} was sent")
    except Exception as err:
        logging.error(err)
        logging.error("There was some error registering the notes")
        
    write_register(register_dest,notes,CONFIG['BROWSER'])
