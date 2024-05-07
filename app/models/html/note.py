from flask import session
from flask_babel import gettext
from flask_login import current_user

from xml.etree import ElementTree as ET

from app import db
from sqlalchemy import select

class NoteHtml(object): 
    def refs_html(self,reg):
        rg = reg.split("_")
        html = []
        for ref in self.ref:
            if not rg[2] in ['','pending']:
                if ref.sender.alias == rg[2] or rg[2] in [r.alias for r in ref.receiver]:
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>')
            elif ref.register.permissions() != 'notallowed':
                if rg[0] == 'des':
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>({ref.dep_html})')
                else:
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>')

        return ','.join([h for h in html if h])

    def files_html(self,reg):
        rg = reg.split('_')
        span = ET.Element('span')
        if self.permanent_link and rg[2] in ['','pending']:
            folder_link = ET.Element('a',attrib={'href':f'https://nas.prome.sg:5001/d/f/{self.permanent_link}','data-bs-toggle':'tooltip','title':gettext('Folder'),'target':'_blank'})
            folder_icon = ET.Element('i',attrib={'class':'bi bi-folder-fill','style':'color: orange;'})                         
            folder_link.append(folder_icon)
            span.append(folder_link)

        separator = ET.Element('span',attrib={'class':'ms-1 me-1'})
        separator.text = ":"
        span.append(separator)

        for file in self.files:
            if rg[0] == 'mat' and ( current_user.alias in self.received_by.split(',') or self.sender == current_user ):
                span.append(file.icon_html_raw)
            elif rg[0] != 'mat' and ( rg[2] in ['','pending'] or file.subject == '' or rg[2] in file.subject.split(',') ):
                span.append(file.icon_html_raw)
    
        return ET.tostring(span,encoding='unicode',method='html')

    @property
    def fullkey_link_html(self):
        if self.register.alias == 'mat':
            a = ET.Element('a',attrib={'href':f'?reg=all_all_&h_note={self.id}','target':'_blank','data-bs-toggle':'tooltip','title':self.read_by})
        else:
            a = ET.Element('a',attrib={'href':f'?reg=all_all_&h_note={self.id}','target':'_blank','data-bs-toggle':'tooltip','title':self.receivers})
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
    def dep_html(self):
        dep = ET.Element('span',attrib={'class':f'badge {"bg-primary" if self.flow == "out" else "bg-danger"}'})
        if self.flow == 'in':
            if len(self.receiver) > 1:
                dep.attrib['data-bs-toggle'] = 'tooltip'
                dep.attrib['title'] = self.receivers
                dep.text = "(...)"
            elif self.receivers:
                dep.text = self.receivers
            else:
                dep.text = "+"
        else:
            dep.text = self.sender.alias
        
        return ET.tostring(dep,encoding='unicode',method='html')

       
    
    def content_html(self,reg):
        text = self.content_jp if 'jp' in current_user.groups else self.content
        rg = reg.split("_")

        if not rg[2] in ['','pending'] and self.flow == 'in' or rg[2] in ['','pending'] and self.flow == 'out':
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
   
    def edit_delete_html(self,reg):
        rg = reg.split('_')
        div = ET.Element('span')
        edit_icon = ET.Element('i',attrib={'class':'bi bi-pencil'})
        delete_icon = ET.Element('i',attrib={'class':'bi bi-trash3-fill','style':'color: red;'})
        edit_link = None
        delete_link = None
        
        if not rg[2] in ['','pending']:
            if self.flow == 'out': # IT is in for the ctr
                edit_link = ET.Element('a',attrib={'href':f'/edit_note?note={self.id}&ctr={rg[2]}','data-bs-toggle':'tooltip','title':gettext('Edit note')})
            elif self.state < 1:
                edit_link = ET.Element('a',attrib={'href':f'/edit_note?note={self.id}&ctr={rg[2]}','data-bs-toggle':'tooltip','title':gettext('Edit note')})
                delete_link = ET.Element('button',attrib={'class':'btn btn-link p-0 ms-1','onclick':f"myFunction('{self.fullkey}',{self.id})",'data-bs-toggle':'tooltip','title':gettext('Delete note')})
        elif current_user.admin or rg[0] in ['des','box'] or self.state < 2 and self.rel_flow(reg) == 'out' or self.register.permissions() == 'editor' or self.reg == 'mat' and self.sender == current_user and self.state < 6:
            despacho = '&despacho=true' if rg[0] == 'des' else ''
            edit_link = ET.Element('a',attrib={'href':f'/edit_note?note={self.id}{despacho}','data-bs-toggle':'tooltip','title':gettext('Edit note')})
            delete_link = ET.Element('button',attrib={'class':'btn btn-link p-0 ms-1','onclick':f"myFunction('{self.fullkey}',{self.id})",'data-bs-toggle':'tooltip','title':gettext('Delete note')})

        if edit_link != None:
            separation = ET.Element('span',attrib={'class':'ms-1 me-1'})
            separation.text = "|"
            div.append(separation)
            edit_link.append(edit_icon)
            div.append(edit_link)
            if delete_link != None:
                delete_link.append(delete_icon)
                div.append(delete_link)
    
        return ET.tostring(div,encoding='unicode',method='html')

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
        rg = reg.split("_")
        if rg[0] == 'mat':
            return self.status_mat_html(reg)

        sp = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','role':'button'})
        if rg[0] == 'des':
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
            if not rg[2] in ['','pending']:
                done = self.ctr_has_done(session['ctr'])
                mine = True
            else:
                done = True if self.state > 5 else False
                mine = True if current_user in self.receiver or self.register.permissions() == 'editor' else False
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
                    if not rg[2] in ['','pending']:
                        text = gettext('Send note to cr')
                    else:
                        text = gettext('Send note to sccr')
                case 1:
                    icon = "bi-send-check-fill"
                    color = "gray"
                    if not rg[2] in ['','pending']:
                        text = gettext('Waiting for cr to get the note (click to take note back from cr inbox)')
                    else:
                        text = gettext('Waiting for sccr to send note')
                case _:
                    sp = ET.Element('span')
                    icon = "bi-send-check-fill"
                    color = "green"
                    if not rg[2] in ['','pending']:
                        text = gettext('Note has been received in cr')
                    else:
                        text = gettext('The note has been sent')
        
        #text = ""

        i = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};','data-toggle':'tooltip','title':text})
        sp.append(i)
        return ET.tostring(sp,encoding='unicode',method='html')
    
    



    def status_mat_html(self,reg):
        sp1 = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','hx-target':'#status_mat','role':'button'})
        if self.sender == current_user: # Owner of matter. Two buttons. Capacity to re-start
            if self.state == 0:
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
                sp2 = ET.Element('span',attrib={'class':'ms-1','hx-post':f'/state_note?note={self.id}&reg={reg}&cancel=true','hx-target':'#status_mat','role':'button'})
                i2 = ET.Element('i',attrib={f'class':f'bi bi-skip-start-circle','style':f'color: red;','data-toggle':'tooltip','title':gettext('Click here to restart the matter')})
                sp2.append(i2)
                sp = ET.Element('span')
                sp.append(sp1)
                sp.append(sp2)
                sp.attrib['id'] = 'status_mat'
                return ET.tostring(sp,encoding='unicode',method='html')
            else:
                sp1.attrib['id'] = 'status_mat'
                return ET.tostring(sp1,encoding='unicode',method='html')
        else: # One of the persons circulating the note
            if self.state == 1 and not self.is_read(current_user):
                sp1 = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','hx-target':'#status_mat','role':'button'})
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
                sp2 = ET.Element('span',attrib={'class':'ms-1','hx-post':f'/state_note?note={self.id}&reg={reg}&cancel=true','hx-target':'#status_mat','role':'button'})
                i2 = ET.Element('i',attrib={f'class':f'bi bi-skip-start-circle','style':f'color: red;','data-toggle':'tooltip','title':gettext('Click here to send matter back to owner')})
                sp2.append(i2)
                sp = ET.Element('span')
                sp.append(sp1)
                sp.append(sp2)
                sp.attrib['id'] = 'status_mat'
                return ET.tostring(sp,encoding='unicode',method='html')
            else:
                sp1.attrib['id'] = 'status_mat'
                return ET.tostring(sp1,encoding='unicode',method='html')

