#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import re

import gspread
from tinydb import TinyDB, Query
from tinydb.storages import MemoryStorage
from oauth2client.service_account import ServiceAccountCredentials

from cryptography.fernet import Fernet

from sqlalchemy import select, func, literal_column, and_, not_, or_
from sqlalchemy.orm import aliased

from flask import session, current_app
from flask_babel import gettext
from flask_login import current_user
from xml.etree import ElementTree as ET

from app import db
from app.src.models import User, Note, Register, NoteUser, Group, Tag

def toNewNotesStatus():

    get_password()
    return ""
    user = db.session.scalar(select(User).where(User.alias=='tak'))
    register = db.session.scalar(select(Register).where(Register.alias=='ctr'))
    notes = db.session.scalars(select(Note).where(Note.result('is_read',user)==False,Note.reg=='ctr',Note.status=='registered',Note.permanent==False)).all()

    for i,note in enumerate(notes):
        print(i,note.fullkey,note.content,note.date)

    rst = db.session.scalar(select(func.count(Note.id)).where(Note.status=='registered',Note.permanent==False,Note.result('access').in_(['reader','editor']),Note.register_id==register.id,not_(Note.result('is_read',user))))

    print('result:',rst)


def get_password():
    USER = 'akanashiro'
    user = db.session.scalar(select(User).where(User.alias==USER))
    cipher = Fernet(current_app.config['SECRET_KEY'])
    PASSWD = cipher.decrypt(user.get_setting('password_nas'))
    print(PASSWD)


def get_data_gspread():
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Add your service account key file
    creds = ServiceAccountCredentials.from_json_keyfile_name('/cert/sake-465008-82e934891ee2.json', scope)

    # Authorize the client
    client = gspread.authorize(creds)

    # Open the Google Sheet
    sheet = client.open("test").sheet1  # or use .get_worksheet(index)

    # Get all data from the sheet
    data = sheet.get_all_records()
    db = TinyDB(storage=MemoryStorage)

    db.insert_multiple(data)
    
    return db
    


def get_info_gspread(info):
    db = get_data_gspread()
    people = db.search(Query().ctr == info)  # Example query to find users older than 28
    actividades = ['ca','crt n','cve cl','cve sacd']
    
    result = ET.Element('ul',attrib={'class':'','style':'font-size:0.8em'})

    for person in people:
        item = ET.SubElement(result,'li',attrib={'class':'ms-2 mt-2'})
        name = ET.SubElement(item,'span',attrib={'class':'fw-bold'})
        name.text = person['Name']
        item.append(ET.Element('br'))

        for act in actividades:
            if person[act]:
                item.append(ET.Element('span',attrib={'class':'ms-4'}))
                item[-1].text = person[act]
                item.append(ET.Element('br'))
   
    return ET.tostring(result,encoding='unicode',method='html')


#### To use with this html in ctr Page
"""
<li hx-trigger="load" hx-get="/gspread?info=bay" hx-swap="innerHTML" hx-indicator="#indicator-list" hx-target="#activitiesElement" class="htmx-request">
Activities:

<span id="activitiesElement">
 <span id="indicator-list" class="spinner-wrapper htmx-indicator htmx-request">
    <span class="spinner-border text-info" style="width: 1em; height: 1em;" role="status"></span>
    (Refresh window if it is no working after a while)
 </span>
</span>

</li>
</ol>
"""


def get_info_gspread_accordion(info):
    db = get_data_gspread()
    results = db.search(Query().ctr == 'bay')  # Example query to find users older than 28
    actividades = ['ca','crt n','cve cl','cve sacd']
    html = []
    
    for i,rst in enumerate(results):
        acc_item = ET.Element('div',attrib={'class':'accordion-item'})
        acc_header = ET.Element('h2',attrib={'class':'accordion-header'})
        acc_header_button = ET.Element('button',attrib={'class':'accordion-button','type':'button','data-bs-toggle':'collapse','data-bs-target':f'#collapseAct{i}','aria-expanded':'true','aria-control':f'collapseAct{i}'})
        acc_header_button.text = rst['Name']

        acc_header.append(acc_header_button)
        acc_item.append(acc_header)


        acc_collapse = ET.Element('div',attrib={'id':f'collapseAct{i}','class':'accordion-collapse collapse show','data-bs-parent':'#accordionActivities'})
        acc_body = ET.Element('div',attrib={'class':'accordion-body','style':'font-size:1rem'})
        acc_list = ET.Element('ul',attrib={'class':'list-group list-group-flush','style':'padding: 0rem'})
        text_body = []
        for act in actividades:
            if rst[act]:
                acc_list_item = ET.Element('li',attrib={'class':'list-group-item','style':'padding: 0.1rem'})
                acc_list_item.text = rst[act]
                acc_list.append(acc_list_item)
                text_body.append(rst[act])
        
        acc_body.append(acc_list)
        #acc_body.text = " \n ".join(text_body)
        acc_item.append(acc_body)
        html.append(ET.tostring(acc_item,encoding='unicode',method='html'))

    return " ".join(html)
