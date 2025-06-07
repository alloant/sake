#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import base64
from datetime import date

import smtplib
from email.mime.text import MIMEText
import eml_parser

import threading

from flask import flash, current_app, send_file
import poplib
from email import parser

from sqlalchemy import select, and_

from config import Config
from app import db
from app.src.models import Value, File
from app.src.models.nas.nas import upload_path, convert_office, move_path, download_path

INV_EXT = {'osheet':'xlsx','odoc':'docx'}
EXT = {'xls':'osheet','xlsx':'osheet','docx':'odoc','rtf':'odoc'}

def check_mail():
    print('Connecting to pop3')
    # Replace with your POP3 server details
    pop3_server = Config.EMAIL_CARDUMEN_SERVER
    username = Config.EMAIL_CARDUMEN_USER
    password = Config.EMAIL_CARDUMEN_SECRET
    last_value = db.session.scalar(select(Value).where(Value.name=='last_message'))
    if not last_value or not last_value.value.isdigit():
        return None
    last_message = int(last_value.value)
    # Connect to the POP3 server using SSL
    try:
        pop_conn = poplib.POP3_SSL(pop3_server, port=995)  # Use port 587 or 995
        pop_conn.user(username)
        pop_conn.pass_(password)

        # Get the number of messages
        num_messages = len(pop_conn.list()[1])
        if last_message == num_messages:
            flash("There are not new messages")
        else:
            flash(f"There are {num_messages-last_message} new messages")
        # Fetch and parse emails
        for i in range(last_message + 1,num_messages + 1):
            try:
                raw_email = b"\n".join(pop_conn.retr(i)[1])
                read_mail(raw_email)
                last_value.value = str(int(last_value.value)+1)
            except Exception as e:
                flash(f"No luck with number {i}. {e}",'danger')
                break
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the connection
        db.session.commit()
        if 'pop_conn' in locals():
            pop_conn.quit()
    
    print('End connection')

def list_last_messages():
    print('Connecting to pop3')
    # Replace with your POP3 server details
    pop3_server = Config.EMAIL_CARDUMEN_SERVER
    username = Config.EMAIL_CARDUMEN_USER
    password = Config.EMAIL_CARDUMEN_SECRET
    
    # Connect to the POP3 server using SSL
    try:
        pop_conn = poplib.POP3_SSL(pop3_server, port=995)  # Use port 587 or 995
        pop_conn.user(username)
        pop_conn.pass_(password)

        # Get the number of messages
        messages = pop_conn.list()
        num_messages = len(messages[1])
        print(num_messages)

        for i in range(num_messages - 10,num_messages):
            message_info = messages[1][i].split()
            message_number = message_info[0].decode('utf-8')
            message_size = message_info[1].decode('utf-8')
            print(message_info,message_number,message_size)
        
        
        # Fetch and parse emails
        #for i in range(num_messages - 10,num_messages + 1):
        #    print(f"Message {i}")
        #    try:
        #        raw = b"\n".join(pop_conn.retr(i)[1])
        #        email = eml_parser.parser.decode_email_b(raw,include_attachment_data=True,include_raw_body=True)
        #        print(email.items())
        #    except Exception as e:
        #        flash(f"No luck with number {i}. {e}",'danger')
        #        break
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the connection
        if 'pop_conn' in locals():
            pop_conn.quit()
    
    print('End connection')

def read_mail(raw):
    if isinstance(raw,str):
        email = eml_parser.parser.decode_email(raw,include_attachment_data=True,include_raw_body=True)
    else:
        email = eml_parser.parser.decode_email_b(raw,include_attachment_data=True,include_raw_body=True)
    
    sender = email['header']['from']
    subject = email['header']['subject']
    date = email['header']['date']
    
    dest = f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN"

    if 'attachment' in email:
        attachments = email['attachment']
        efiles = []
        for file in attachments:
            fext = file['filename'].split(".")[-1]
            
            if fext in EXT.keys():
                fn = f"{file['filename'][:-len(fext)]}{EXT[fext]}"
            else:
                fn = file['filename']

            rnt = db.session.scalar(select(File).where(and_(File.path.contains(fn),File.sender==sender)))
            exists = False
            efiles.append(False)
            
            if rnt: # Note same name but could be different year
                dt = rnt.note.year if rnt.note else rnt.date.year
                
                if dt == date.today().year:
                    exists = True
              
            if exists:
                flash(f"The file {file['filename']} is already in the database",'warning')
                efiles.append(True)
        
        for i,file in enumerate(attachments):
            if efiles[i]:
                continue

            b_file = io.BytesIO(base64.b64decode(file['raw']))
            b_file.name = f"{file['filename']}"
            rst = upload_path(b_file,dest)
            if not rst:
                continue

            path = rst['data']['display_path']
            link = rst['data']['permanent_link']
            
            if file['filename'].split(".")[-1] in EXT.keys():
                rst_conv = convert_office(rst['data']['display_path'])
                if rst_conv:
                    path = rst_conv['path']
                    fid = rst_conv['fid']
                    link = rst_conv['link']
                    move_path(rst['data']['display_path'],f"{dest}/Originals")
                else:
                    flash(f"The file {file['filename']} could not be converted to Synology office and the original was added",'danger')

            fl = File(path=path,permanent_link=link,subject=subject,sender=sender.lower(),date=date.date())
            db.session.add(fl)
            flash(f"{fl} has been added to the database",'success')

        db.session.commit()

