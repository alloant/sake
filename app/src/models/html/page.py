import re

from flask import session, make_response, current_app
from flask_babel import gettext
from flask_login import current_user

from xml.etree import ElementTree as ET

from app import db
from sqlalchemy import select

def replace_links(text):
    # Define the pattern to match the links
    #pattern = r'https://nas\.prome\.com:8001/page/(\d+)'
    pattern = r'href="/page/(\d+)"'

    # Define the replacement function
    def replacement(match):
        page_number = match.group(1)
        hxget = f"/main_title_body?reg=['pages','{page_number}','']"

        new_link = f'hx-get="{hxget}" hx-indicator="#indicator-table" hx-target="#main-title-body" hx-trigger="click" hx-disinherit="*" href="#"'
        return new_link

    # Use re.sub to replace the links
    new_text = re.sub(pattern, replacement, text)
    return new_text

class PageHtml(object):
    @property
    def access_html(self):
        max_users = 6
        span = ET.Element('small',attrib={'class':'ms-1'})
        if session['theme'] == 'light-mode':
            attr = {'class':f'p-1 fw-normal border rounded-pill text-dark badge border-secondary'}
        else:
            attr = {'class':f'p-1 fw-normal border rounded-pill text-light badge border-secondary'}
        
        groups = self.possible_groups

        for group in groups:
            if group in self.groups:
                t = ET.Element('span',attrib={'class':f'p-1 fw-normal border rounded-pill badge bg-secondary'})
                t.text = group
                span.append(t)


        cont = 0
        for i,user in enumerate(self.users):
            if not user or user.access == '':
                continue
            t = ET.Element('span',attrib=attr)
            if len(self.users) > max_users and i == max_users - 1:
                t.text = '...'
                span.append(t)
                span.attrib['data-bs-toggle'] = 'tooltip'
                span.attrib['title'] = ",".join([t if isinstance(t,str) else t.user.alias for t in self.users if t])
                break
            else:
                t.text = user.user.alias
                span.append(t)
            cont +=1

        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def text_htmx_links(self):
        return replace_links(self.text)


