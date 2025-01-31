import eml_parser
import io
import base64
from datetime import date

from flask import flash, current_app, send_file
from slugify import slugify

from sqlalchemy import select, and_

import tempfile

from email import generator
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pathlib import Path

from app import db
from app.src.models.nas.nas import upload_path, convert_office, move_path, download_path
from app.src.models import File
#import libsynomail.connection as con

INV_EXT = {'osheet':'xlsx','odoc':'docx'}
EXT = {'xls':'osheet','xlsx':'osheet','docx':'odoc','rtf':'odoc'}

def write_report_eml(body,dates,path_download):
    msg = MIMEMultipart()
    msg["To"] = 'cg@cardumen.lan'
    msg["From"] = 'Aes-cr@cardumen.lan'
    
    msg["Subject"] = f"Notas enviadas {dates}"

    msg.add_header('X-Unsent','1')
    msg.attach(MIMEText(body,"plain"))


    fp = io.BytesIO()
    emlGenerator = generator.BytesGenerator(fp)
    emlGenerator.flatten(msg)
    fp.seek(0)
    today = date.today().strftime("%y%m%d")
    return send_file(fp,download_name=f"{today}-report.eml",as_attachment=False)

def write_eml(rec,note,path_download):
    msg = MIMEMultipart()
    msg["To"] = rec
    msg["From"] = 'Aes-cr@cardumen.lan'
    
    sub1 = note.fullkey if note.num > 0 else f"{note.refs[0]}"
    sub2_1 = note.content
    sub2_2 = []

    if note.num == 0:
        sub2_2.append('ref')

    if note.reg in ['vc','vcr','dg','cc','desr']:
        sub2_2.append(f"{note.reg}-Aes")
        if note.proc == 'sf':
            sub2_2[-1] += "f"

    sub2 = f"{sub2_1} ({'.'.join(sub2_2)})" if sub2_2 else sub2_1

    sub3 = note.refs(only=['cg','r'])

    
    msg["Subject"] = f"{sub1};{sub2};{sub3}"
    #msg["Subject"] = f"{note.key}/{note.year-2000}; {note.content}; {note.refs}"
    

    msg.add_header('X-Unsent','1')
    body = ""
    msg.attach(MIMEText(body,"plain"))

    rst = True
    for file in note.files:
        ext = Path(file.name).suffix[1:]
        file_name = f"{slugify(Path(file.name).stem,lowercase=False)}.{INV_EXT[ext]}" if ext in INV_EXT else f"{slugify(file.name[:-len(ext)])}.{ext}"

        attachment = download_path(f"{note.folder_path}/{file.path}")
        
        if attachment:
            part = MIMEApplication(attachment.read(),Name=file.name)

            part['Content-Disposition'] = f'attachment; filename = {file_name}'
            msg.attach(part)
        else:
            rst = False

    if rst:
        fp = io.BytesIO()
        emlGenerator = generator.BytesGenerator(fp)
        emlGenerator.flatten(msg)
        fp.seek(0) 
        return send_file(fp,download_name=f"{note.fullkey.replace("/","-")}.eml",as_attachment=False)
    
    return False


def read_eml(file_eml,emails = None):
    if isinstance(file_eml,str):
        parsed_eml = eml_parser.parser.decode_email(file_eml,include_attachment_data=True,include_raw_body=True)
    else:
        parsed_eml = eml_parser.parser.decode_email_b(file_eml,include_attachment_data=True,include_raw_body=True)
    
    sender = parsed_eml['header']['from']
    subject = parsed_eml['header']['subject']
    date = parsed_eml['header']['date']
    
    dest = f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Mail/IN"

    if 'attachment' in parsed_eml:
        attachments = parsed_eml['attachment']
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
                
 
#    else:
#        if 'body' in parsed_eml:
#            if parsed_eml['body']:
#                if 'content' in parsed_eml['body'][0]:
#                    b_file = io.BytesIO(str.encode(parsed_eml['body'][0]['content']))
#                    b_file.name = f"{subject}"
#                    upload_path(b_file,dest)
