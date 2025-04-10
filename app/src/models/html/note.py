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
                t.text = tag.text
                span.append(t)
            cont +=1

        if cont == 0 and show_something:
            t = ET.Element('span',attrib=attr)
            t.text = '+'
            span.append(t)

        return ET.tostring(span,encoding='unicode',method='html')

    def number_files(self,ctr=''):
        num = len([file for file in self.files if file.permissions('user_can_see',ctr)])

        num = str(num)
        rst = ''
        for n in num:
            rst += f'<i class="bi bi-{n}-square"></i>'

        return rst


    @property
    def people_matter_html(self):
        if self.register.alias != 'mat':
            return ""
        
        done = []
        working = []
        waiting = []

        for user in self.users:
            if user.target:
                if user.target_acted:
                    done.append(user.user.alias)
                elif user.target_order == self.current_target_order and self.status == 'shared':
                    working.append(user.user.alias)
                else:
                    waiting.append(user.user.alias)

        max_people = 5
        max_waiting = max_people - len(working) if max_people > len(working) else 0
        max_done = max_people - len(working + waiting) if max_people > len(working + waiting) else 0
      
        span = ET.Element('span',attrib={'class':'small ms-1'})
        if session['theme'] == 'light-mode':
            color = 'dark'
            text = 'light'
        else:
            color = 'light'
            text = 'dark'

        # First people who have already signed
        if len(done) > max_done:
            start = len(done) - max_done
            t = ET.Element('span',attrib={'class':f'badge border text-secondary border-secondary fw-normal'})
            t.text = '...'
            t.attrib['data-bs-toggle'] = 'tooltip'
            t.attrib['title'] = ','.join(done[:start])
            span.append(t)
        else:
            start = 0

        for alias in done[start:]:
            t = ET.Element('span',attrib={'class':f'badge border text-secondary border-secondary fw-normal'})
            t.text = alias
            span.append(t)
        
        # Then people who are working in the note
        for alias in working:
            if alias == current_user.alias:
                t = ET.Element('span',attrib={'class':f'badge border bg-{color} text-{text} fw-bold'})
            else:
                t = ET.Element('span',attrib={'class':f'badge border bg-secondary text-light fw-bold'})
            t.attrib['data-bs-toggle'] = 'tooltip'
            t.attrib['title'] = f"{alias} is studying the matter"
            t.text = alias

            span.append(t)

        # People who still cannot see the proposal
        for i,alias in enumerate(waiting):
            t = ET.Element('span',attrib={'class':f'badge border text-{color} border-{color} fw-normal'})
            if i >= max_waiting and i != len(waiting) - 1:
                t.text = '...'
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = ','.join(waiting[i:])
            else:
                t.text = alias
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
