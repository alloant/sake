import eml_parser
import io
import base64
from datetime import date

from flask import flash, current_app, send_file

from sqlalchemy import select, and_

import tempfile

from email import generator
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pathlib import Path

from app import db
from .models.nas.nas import upload_path, convert_office, move_path, download_path
from .models import File
#import libsynomail.connection as con

INV_EXT = {'osheet':'xlsx','odoc':'docx'}
EXT = {'xls':'osheet','xlsx':'osheet','docx':'odoc','rtf':'odoc'}

def write_eml(rec,note,path_download):
    msg = MIMEMultipart()
    msg["To"] = rec
    msg["From"] = 'Aes-cr@cardumen.org'
    msg["Subject"] = f"{note.key}/{note.year-2000}; {note.content}; {note.refs}"
    msg.add_header('X-Unsent','1')
    body = ""
    msg.attach(MIMEText(body,"plain"))

    rst = True
    for file in note.files:
        ext = Path(file.name).suffix[1:]
        file_name = f"{Path(file.name).stem}.{INV_EXT[ext]}" if ext in INV_EXT else file.name

        attachment = download_path(f"{note.path_note}/{file.path}")
        
        if attachment:
            part = MIMEApplication(attachment.read(),Name=file.name)

            part['Content-Disposition'] = f'attachment; filename = {file_name}'
            msg.attach(part)
        else:
            rst = False

    if rst:
        #fp = tempfile.TemporaryFile()
        import io
        fp = io.BytesIO()
        emlGenerator = generator.BytesGenerator(fp)
        emlGenerator.flatten(msg)
        return send_file(fp,download_name=f"{note.key}.eml",as_attachment=True)
        return True

        #with open(f"{path_download}/{note.key}.eml",'w') as file:
        #    emlGenerator = generator.Generator(file)
        #    emlGenerator.flatten(msg)
        #    return True
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
    
        for file in attachments:
            fext = file['filename'].split(".")[-1]
            if fext in EXT.keys():
                fn = f"{file['filename'][:-len(fext)]}{EXT[fext]}"
            else:
                fn = file['filename']

            rnt = db.session.scalar(select(File).where(and_(File.path.contains(fn),File.sender==sender)))
            exists = False
            
            if rnt: # Note same name but could be different year
                dt = rnt.note.year if rnt.note else rnt.date.year
                
                if dt == date.today().year:
                    exists = True
              
            if exists:
                flash(f"The file {file['filename']} is already in the database")
                return False
        
        for file in attachments:
            b_file = io.BytesIO(base64.b64decode(file['raw']))
            b_file.name = f"{file['filename']}"
            
            rst = upload_path(b_file,dest)
            if not rst:
                continue

            path = rst['data']['path']
            link = rst['data']['permanent_link']
            
            if file['filename'].split(".")[-1] in EXT.keys():
                path,fid,link = convert_office(rst['data']['display_path'])
                move_path(rst['data']['display_path'],f"{dest}/Originals")

            fl = File(path=path,permanent_link=link,subject=subject,sender=sender.lower(),date=date.date())
            db.session.add(fl)

        db.session.commit()
                
 
    else:
        if 'body' in parsed_eml:
            if parsed_eml['body']:
                if 'content' in parsed_eml['body'][0]:
                    b_file = io.BytesIO(str.encode(parsed_eml['body'][0]['content']))
                    b_file.name = f"{subject}"
                    upload_path(b_file,dest)
