import re

from flask import session, make_response
from flask_babel import gettext
from flask_login import current_user

from xml.etree import ElementTree as ET

from app import db
from sqlalchemy import select

class NoteHtml(object): 
    def refs_html(self,reg):
        html = []
        for ref in self.ref:
            if not reg[2] == '':
                if ref.sender.alias == reg[2] or reg[2] in [r.alias for r in ref.receiver]:
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>')
            elif ref.register.permissions != 'notallowed':
                if reg[0] == 'des':
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>({ref.dep_html})')
                else:
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>')

        return ','.join([h for h in html if h])

    def files_html(self,reg, copy = True):
        span = ET.Element('span')
        dots = False 
        if self.can_edit(reg):
            if self.permanent_link and copy:
                dots = True
                copy_files = ET.Element('a')
                copy_files.attrib['hx-get'] = f"browse_files?note={self.id}&reg={reg}" 
                copy_files.attrib['hx-target'] = "#modal-htmx" 
                copy_files.attrib['hx-trigger'] = "click" 
                copy_files.attrib['data-bs-toggle'] = "modal" 
                copy_files.attrib['data-bs-target'] = "#modal-htmx"
                copy_files.attrib['class'] = "ms-1"
                copy_files.attrib['role'] = "button"
                
                copy_files_icon = ET.Element('i')
                copy_files_icon.attrib['id'] = f'fileRow-{self.id}'
                copy_files_icon.attrib['class'] = 'bi bi-folder-symlink-fill'
                copy_files_icon.attrib['style'] = 'color: orange;'
                copy_files_icon.attrib['data-toggle'] = 'tooltip'
                copy_files_icon.attrib['title'] = gettext('Copy files from notes or other folders')

                copy_files.append(copy_files_icon)
                span.append(copy_files)

            update_folder = ET.Element('a')
            update_folder.attrib['hx-get'] = f"update_files?note={self.id}&reg={reg}"
            update_folder.attrib['hx-target'] = f"#filesRow-{self.id}" 
            update_folder.attrib['hx-target-error'] = "#flash-errors" 
            update_folder.attrib['hx-trigger'] = "click"
            update_folder.attrib['hx-indicator'] = f"#filesIndRow-{self.id}"
            update_folder.attrib['class'] = "ms-1"
            update_folder.attrib['role'] = "button"
            
            update_folder_icon = ET.Element('i')
            update_folder_icon.attrib['id'] = f'fileRow-{self.id}'
            if self.permanent_link == '':
                update_folder_icon.attrib['class'] = 'bi bi-folder-plus'
                update_folder_icon.attrib['style'] = 'color: orange;'
                update_folder_icon.attrib['title'] = gettext('Create folder for note')
            else:
                update_folder_icon.attrib['class'] = 'bi bi-arrow-repeat'
                update_folder_icon.attrib['style'] = 'color: blue;'
                update_folder_icon.attrib['title'] = gettext('Update files in folder')
            update_folder_icon.attrib['data-toggle'] = 'tooltip'

            update_folder.append(update_folder_icon)
            span.append(update_folder)
 

        if self.permanent_link and (not reg[2] and (self.register.permissions in ['editor','viewer'] or self.sender == current_user or current_user in self.receiver and self.register.alias != 'mat') or reg[2] and self.flow == 'in'):
            dots = True
            folder_link = ET.Element('a',attrib={'href':f'https://nas.prome.sg:5001/d/f/{self.permanent_link}','data-toggle':'tooltip','title':gettext('Folder'),'target':'_blank'})
            folder_icon = ET.Element('i',attrib={'class':'bi bi-folder-fill ms-1','style':'color: orange;'})                         
            folder_link.append(folder_icon)
            span.append(folder_link)

        if dots:
            separator = ET.Element('span',attrib={'class':'ms-1 me-1'})
            separator.text = ":"
            span.append(separator)

        for file in self.files:
            if reg[2]: # We are in a cl register
                if file.subject == '' or reg[2] in file.subject.split(','):
                    span.append(file.icon_html_raw)
            else: # For everything else
                if self.register.alias == 'mat': # Are the files of a mmatter
                    if current_user.alias in self.received_by.split(',') or self.sender == current_user:
                        span.append(file.icon_html_raw)
                elif current_user in self.receiver or self.sender == current_user:
                    span.append(file.icon_html_raw)
                elif self.register.permissions in ['editor','viewer']:
                    span.append(file.icon_html_raw)

    
        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def fullkey_link_html(self):
        if self.register.alias == 'mat':
            a = ET.Element('a',attrib={'class':'link','hx-get':f"/main_body?reg=['all',{self.id},'']",'hx-trigger':'click','hx-target':'#main-body','data-bs-toggle':'tooltip','title':self.received_by,'role':'button'})
        else:
            a = ET.Element('a',attrib={'class':'link','hx-get':f"/main_body?reg=['all',{self.id},'']",'hx-trigger':'click','hx-target':'#main-body','data-bs-toggle':'tooltip','title':self.receivers,'role':'button'})
        if self.num == 0 and self.ref:
            a.text = f"ref {self.ref[0].fullkey}"
        else:
            a.text = self.fullkey

        if self.permanent:
            i = ET.Element('i',attrib={'class':'bi bi-asterisk','style':'color: red;'})
            a.append(i)
        

        return ET.tostring(a,encoding='unicode',method='html')

    def tag_html(self,show_something=False):
        max_tags = 6
        
        span = ET.Element('span',attrib={'class':'small ms-1'})
        if len(self.tags) > max_tags:
            span.attrib['data-bs-toggle'] = 'tooltip'
            span.attrib['title'] = ",".join([t for t in self.tags if t])

        cont = 0
        for i,tag in enumerate(self.tags):
            if not tag:
                continue
            t = ET.Element('span',attrib={'class':f'badge bg-success'})
            if len(self.tags) > max_tags and i == max_tags - 1:
                t.text = '...'
                span.append(t)
                break
            else:
                t.text = tag
                span.append(t)
            cont +=1
        
        if cont == 0 and show_something:
            t = ET.Element('span',attrib={'class':f'badge bg-success'})
            t.text = '+'
            span.append(t)

        
        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def people_matter_html(self):
        if self.register.alias != 'mat':
            return ""
       
        max_people = 4
        people = [p for p in self.received_by.split(',') if p]
        people_read = [p for p in self.read_by.split(',') if p]

        num_people = len(people)
        num_read = len(people_read)
        count_people = 0
        count_read = 0
        rst = []

        over_people = 0
        over_read = 0
        for p in people[num_read:]:
            if len(rst) < max_people:
                rst.append(p)
                count_people += 1
            else:
                over_people += 1

        for p in people[:num_read]:
            if len(rst) < max_people:
                rst = [p] + rst
                count_read += 1
            else:
                over_read += 1

        if count_read < num_read:
            #rst = ['<'] + rst
            if over_read > 0:
                rst[0] = '<'

        if count_people < num_people:
            #rst.append('>')
            if over_people > 0:
                rst[-1] = '>'

        span = ET.Element('span',attrib={'class':'small ms-1'})
        for rec in rst:
            if rec == '<':
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: Maroon; color: gray'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = ",".join([p for p in people_read if not p in rst])
                t.text = '...'
            elif rec == '>':
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: SandyBrown; color: black'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = ",".join([p for p in people if not p in rst and p not in people_read])
                t.text = '...'
            elif rec in self.read_by.split(','): # Was read
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: Maroon; color: gray'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} has already signed"
                t.text = rec
            elif re.search(fr'^{self.read_by},*{rec}',self.received_by) and self.state > 0:
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: SaddleBrown; color: white'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} is studying the matter"
                t.text = rec
            else:
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: SandyBrown; color: black'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} has not seen yet the matter"
                t.text = rec


            span.append(t)

        
        """
        span = ET.Element('span',attrib={'class':'small ms-1'})
        for rec in self.received_by.split(","):
            if rec in self.read_by.split(','): # Was read
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: Maroon; color: gray'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} has already signed"
            elif re.search(fr'^{self.read_by},*{rec}',self.received_by) and self.state > 0:
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: SaddleBrown; color: white'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} is studying the matter"
            else:
                t = ET.Element('span',attrib={'class':f'badge','style':'background-color: SandyBrown; color: black'})
                t.attrib['data-bs-toggle'] = 'tooltip'
                t.attrib['title'] = f"{rec} has not seen yet the matter"

            t.text = rec

            span.append(t)
        """
        
        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def dep_html(self):
        if self.flow == 'in':
            if len(self.receiver) <= 3:
                dep = ET.Element('span',attrib={'class':'small'})
                for rec in self.receiver:
                    dp = ET.Element('span',attrib={'class':'badge bg-danger'})
                    dp.attrib['data-bs-toggle'] = 'tooltip'
                    dp.attrib['title'] = rec.name
                    dp.text = rec.alias
                    dep.append(dp) 
            else:
                dep = ET.Element('span',attrib={'class':'small badge bg-danger'})
                if len(self.receiver) > 3:
                    dep.attrib['data-bs-toggle'] = 'tooltip'
                    dep.attrib['title'] = self.receivers
                    dep.text = "(...)"
                elif self.receivers:
                    dep.text = self.receivers
                else:
                    dep.text = "+"
        else:
            dep = ET.Element('span',attrib={'class':'small badge bg-primary'})
            dep.text = self.sender.alias
        
        return ET.tostring(dep,encoding='unicode',method='html')

       
    
    def content_html(self,reg):
        text = self.content_jp if 'jp' in current_user.groups else self.content

        if reg[2] and self.flow == 'in' or not reg[2] and self.flow == 'out':
            ct = ET.Element('span',attrib={'class':f''})
            ct.attrib['data-toggle'] = 'tooltip'
            ct.attrib['title'] = ""
            ct.text = text
        else:
            ct = ET.Element('span')
            ct = ET.Element('span',attrib={'hx-post':f'/read_note?note={self.id}&reg={reg}','role':'button'})
            #ct.attrib['hx-get'] = f"/read_note?note={self.id}&reg={reg}"
            
            if self.is_read(current_user):
                cti = ET.Element('span',attrib={})
                cti.attrib['title'] = gettext('Mark as unread')
            else:
                cti = ET.Element('span',attrib={'class':f'fw-bold'})
                cti.attrib['title'] = gettext('Mark as read')

            cti.attrib['data-toggle'] = 'tooltip'
            cti.text = text

            ct.append(cti)
        
        return ET.tostring(ct,encoding='unicode',method='html')
   

    def current_user_can_edit(self):
        if current_user.admin:
            return True
        elif 'despacho' in current_user.groups and self.state < 5 and self.flow == 'in': # People during despacho
            return True
        elif (self.flow == 'out' or self.register.alias == 'mat') and self.state < 2 and self.sender == current_user:
            return True
        elif self.flow == 'out' and self.state == 1 and 'scr' in current_user.groups:
            return True
        elif self.register.alias == 'mat' and self.sender == current_user:
            return True

        return False
    
    def status_html(self,reg):
        if self.register.alias == 'mat':
            return self.status_mat_html(reg)

        sp = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','role':'button'})
        if reg[0] == 'des':
            if self.is_read(f"des_{current_user.alias}"):
                if self.state == 5:
                    icon = "bi-check-circle"
                    color = "green"
                else:
                    icon = "bi-hourglass-bottom"
                    color = "gray"
                text = gettext('Unsign note')
            else:
                color = "orange"
                if self.state == 3: #Nobody has check it before
                    text = gettext('Sign note')
                    icon = "bi-circle-fill"
                else:
                    text = gettext('Sign note (the other d has already signed)')
                    icon = "bi-check-circle"
        #elif self.flow == 'out' and not rg[2] in ['','pending'] or self.flow == 'in' and rg[2] in ['','pending']: # It is IN
        elif self.rel_flow(reg) == 'in': # In note for registers and subregisters
            if reg[2]:
                done = self.ctr_has_done(session['ctr'])
                mine = True
            else:
                done = True if self.state > 5 else False
                mine = True if current_user in self.receiver or self.register.permissions == 'editor' else False
            if mine:
                mn = '-fill'
            else:
                mn = ''
                sp = ET.Element('span')
                
            if done:
                icon = f"bi-check-circle{mn}"
                color = "green"
                text = gettext('Mark note as pending')
            else:
                icon = f"bi-x-circle{mn}"
                color = "red"
                text = gettext('Mark note as done')
        else: # Out
            match self.state:
                case 0:
                    icon = "bi-send"
                    color = "gray"
                    if reg[2]:
                        text = gettext('Send note to cr')
                    else:
                        text = gettext('Send note to sccr')
                case 1:
                    icon = "bi-send-check-fill"
                    color = "gray"
                    if reg[2]:
                        text = gettext('Waiting for cr to get the note (click to take note back from cr inbox)')
                    else:
                        sp.attrib['hx-indicator'] = f"#send-{self.id}"
                        text = gettext('Click to send note')
                case _:
                    sp = ET.Element('span')
                    icon = "bi-send-check-fill"
                    color = "green"
                    if reg[2]:
                        text = gettext('Note has been received in cr')
                    else:
                        text = gettext('The note has been sent')
        
        #text = ""

        i = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};','data-toggle':'tooltip','title':text})
        sp.append(i)
        return ET.tostring(sp,encoding='unicode',method='html')
    
    



    def status_mat_html(self,reg):
        #sp1 = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','hx-target':f'#noteRow-{self.id}','role':'button'})
        sp1 = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','hx-target':f'.status-people-{self.id}','hx-disinherit':'*','hx-indicator':'#indicator-table','role':'button'})
        if self.sender == current_user: # Owner of matter. Two buttons. Capacity to re-start
            if self.state == 0 and self.received_by == '':
                icon = "bi-x-circle-fill"
                color = "red"
                text = gettext('Click here to mark it as done')
            elif self.state == 0:
                icon = "bi-send"
                color = "orange"
                text = gettext('Start circulating note')
            elif self.state == 1:
                icon = "bi-hourglass-bottom"
                color = "orange"
                text = f"{gettext('Matter is circulating')} ({self.read_by})"
            elif self.state == 5:
                icon = "bi-x-circle-fill"
                color = "red"
                text = gettext('Matter is back to you after all the directors have checked it. Click here to mark it as done')
            elif self.state == 6:
                icon = "bi-check-circle-fill"
                color = "green"
                text = gettext('Matter was mark as done. Click here to mark it as undone')

            i1 = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};','data-toggle':'tooltip','title':text})
            sp1.append(i1)

            if self.state in [0,5]:
                sp2 = ET.Element('span',attrib={'class':'ms-1','hx-post':f'/state_note?note={self.id}&reg={reg}&cancel=true','hx-target':f'#status_mat-{self.id}','role':'button'})
                i2 = ET.Element('i',attrib={f'class':f'bi bi-skip-start-circle','style':f'color: red;','data-toggle':'tooltip','title':gettext('Click here to restart the matter')})
                sp2.append(i2)
                sp = ET.Element('span')
                sp.append(sp1)
                sp.append(sp2)
                sp.attrib['id'] = f'status_mat-{self.id}'
                sp.attrib['class'] = f"status-people-{self.id}"
                return ET.tostring(sp,encoding='unicode',method='html')
            else:
                sp1.attrib['id'] = f'status_mat-{self.id}'
                sp1.attrib['class'] = f"status-people-{self.id}"
                return ET.tostring(sp1,encoding='unicode',method='html')

        else: # One of the persons circulating the note
            if self.state == 1 and not self.is_read(current_user):
                sp1 = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','hx-target':f'#status_mat-{self.id}','role':'button'})
                icon = "bi-send-fill"
                color = "red"
                text = gettext(f'Click to pass the note to the next one ({self.read_by})')
            elif self.state == 1 and self.is_read(current_user):
                sp1 = ET.Element('span',attrib={})
                icon = "bi-hourglass-bottom"
                color = "gray"
                text = f"{gettext('Matter is circulating')} ({self.read_by})"
            elif self.state == 5:
                sp1 = ET.Element('span',attrib={})
                icon = "bi-x-circle"
                color = "red"
                text = gettext('Matter is back to owner')
            elif self.state == 6:
                sp1 = ET.Element('span',attrib={})
                icon = "bi-check-circle"
                color = "green"
                text = gettext('Matter was mark as done')

            i1 = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};','data-toggle':'tooltip','title':text})
            sp1.append(i1)

            if self.state == 1 and not self.is_read(current_user):
                sp2 = ET.Element('span',attrib={'class':'ms-1','hx-post':f'/state_note?note={self.id}&reg={reg}&cancel=true','hx-target':f'#status_mat-{self.id}','role':'button'})
                i2 = ET.Element('i',attrib={f'class':f'bi bi-skip-start-circle','style':f'color: red;','data-toggle':'tooltip','title':gettext('Click here to send matter back to owner')})
                sp2.append(i2)
                sp = ET.Element('span')
                sp.append(sp1)
                sp.append(sp2)
                sp.attrib['id'] = f'status_mat-{self.id}'
                return ET.tostring(sp,encoding='unicode',method='html')
            else:
                sp1.attrib['id'] = f'status_mat-{self.id}'
                return ET.tostring(sp1,encoding='unicode',method='html')

    def row_html(self):
        tr = ET.Element('tr')
        for i in range(6):
            tr.append(ET.Element('td'))
            tr[-1].text = f"Column {i}"

        return ET.tostring(tr,encoding='unicode',method='html')

        
