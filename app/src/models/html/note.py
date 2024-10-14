import re

from flask import session, make_response, current_app
from flask_babel import gettext
from flask_login import current_user

from xml.etree import ElementTree as ET

from app import db
from sqlalchemy import select

def replace_urls_with_links(text):
    # Regular expression pattern to find URLs
    url_pattern = r'(https?://[^\s]+)'
    
    # Function to replace the found URL with an HTML link
    def replace_with_link(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank">(link)</a>'
    
    # Use re.sub to replace all occurrences of the URL pattern
    result = re.sub(url_pattern, replace_with_link, text)
    return result

class NoteHtml(object): 
    @property
    def fullkey_link_html(self):
        color = 'text-light' if session['theme'] == 'dark-mode' else 'text-dark'
        if self.permanent:
            color = 'text-danger'

        title = 'See everything related to this entry'

        a = ET.Element('a',attrib={'class':f'text-decoration-none fw-bold {color}','style':'white-space: nowrap;','hx-get':f"/main_title_body?reg=['all',{self.id},'']",'hx-trigger':'click','hx-target':'#main-title-body','data-bs-toggle':'tooltip','data-bs-container':'body','title':title,'role':'button'})

        if self.num == 0 and self.ref:
            a.text = f"ref {self.ref[0].fullkey}"
        else:
            a.text = self.fullkey


        return ET.tostring(a,encoding='unicode',method='html')

    @property
    def content_url(self):
        return replace_urls_with_links(self.content)

    def tag_html(self,show_something=False):
        max_tags = 6
        span = ET.Element('small',attrib={'class':'ms-1'})
        if session['theme'] == 'light-mode':
            attr = {'class':f'p-1 fw-normal border rounded-pill text-dark badge border-secondary'}
        else:
            attr = {'class':f'p-1 fw-normal border rounded-pill text-light badge border-secondary'}
        
        cont = 0
        for i,tag in enumerate(self.tags):
            if not tag:
                continue
            t = ET.Element('span',attrib=attr)
            if len(self.tags) > max_tags and i == max_tags - 1:
                t.text = '...'
                span.append(t)
                span.attrib['data-bs-toggle'] = 'tooltip'
                span.attrib['title'] = ",".join([t for t in self.tags if t])
                break
            else:
                t.text = tag
                span.append(t)
            cont +=1

        if cont == 0 and show_something:
            t = ET.Element('span',attrib=attr)
            t.text = '+'
            span.append(t)

        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def number_files(self):
        num = str(len(self.files))
        rst = ''
        for n in num:
            rst += f'<i class="bi bi-{n}-square"></i>'

        return rst


    @property
    def people_matter_html(self):
        if self.register.alias != 'mat':
            return ""

        max_people = 3
        people = [p for p in self.received_by.replace('|',',').split(',') if p]
        people_read = [p for p in self.read_by.replace('|',',').split(',') if p]

        if not people:
            return ""

        rst = []
        states = []

        for alias in people:
            if self.working_matter(alias) and self.state == 1:
                rst.append(alias)
                states.append(1)

        cont = 0
        while len(rst) < max_people and cont < len(people):
            if not people[cont] in rst + people_read:
                rst.append(people[cont])
                states.append(2)
            cont += 1

        cont = len(people_read) - 1
        while len(rst) < max_people and cont >= 0:
            if not people_read[cont] in rst:
                rst = [people[cont]] + rst
                states = [0] + states
            cont -= 1

        for p in people_read:
            if not p in rst:
                rst = ['...'] + rst
                states = [0] + states
                break
        for p in people:
            if not p in rst + people_read:
                rst.append('...')
                states.append(2)
                break
        
        span = ET.Element('span',attrib={'class':'small ms-1'})
        color = 'dark' if session['theme'] == 'light-mode' else 'light'
        for i,rec in enumerate(rst):
            if states[i] == 0:
                t = ET.Element('span',attrib={'class':f'badge border text-secondary border-secondary fw-normal'})
                t.text = rec
                if rec == '...':
                    t.attrib['data-bs-toggle'] = 'tooltip'
                    t.attrib['title'] = ",".join([p for p in people_read if not p in rst])
            elif states[i] == 2:
                t = ET.Element('span',attrib={'class':f'badge border text-{color} border-{color} fw-normal'})
                t.text = rec
                if rec == '...':
                    t.attrib['data-bs-toggle'] = 'tooltip'
                    t.attrib['title'] = ",".join([p for p in people if not p in rst + people_read])
            elif states[i] == 1:
                t = ET.Element('span',attrib={'class':f'badge border text-{color} border-{color} fw-bold'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} is studying the matter"
                t.text = rec
            
            span.append(t)

        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def dep_html(self):
        color = '#777' if session['theme'] == 'light-mode' else '#aaaaaa'
        dep = ET.Element('span',attrib={'class':'small ms-1'})
        if self.flow == 'in':
            if not self.receiver:
                dp = ET.Element('span',attrib={'class':f'badge','style':f'border: 1px solid {color}; color: {color}'})
                dp.text = "+"
                dep.append(dp)
            elif len(self.receiver) <= 3:
                for rec in self.receiver:
                    dp = ET.Element('span',attrib={'class':f'badge','style':f'border: 1px solid {color}; color: {color}'})
                    dp.attrib['data-bs-toggle'] = 'tooltip'
                    dp.attrib['title'] = rec.name
                    dp.text = rec.alias
                    dep.append(dp) 
            else:
                dp = ET.Element('span',attrib={'class':f'badge','style':f'border: 1px solid {color}; color: {color}'})
                if len(self.receiver) > 3:
                    dp.attrib['data-bs-toggle'] = 'tooltip'
                    dp.attrib['title'] = self.receivers
                    dp.text = "(...)"
                elif self.receivers:
                    dp.text = self.receivers
                dep.append(dp)
        else:
            color = '#777' if session['theme'] == 'light-mode' else '#aaaaaa'
            dp = ET.Element('span',attrib={'class':'badge fst-italic','style':f'border: 1px solid {color}; color: {color}'})
            dp.text = self.sender.alias
            dep.append(dp)
        
        return ET.tostring(dep,encoding='unicode',method='html')
