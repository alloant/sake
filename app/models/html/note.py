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
            if ref.register.permissions() != 'notallowed':
                if rg[0] == 'des':
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>({ref.dep_html})')
                else:
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>')

        return ','.join(html)
    
    @property
    def fullkey_link_html(self):
        a = ET.Element('a',attrib={'href':f'?reg=all_all_&h_note={self.id}','target':'_blank','data-bs-toggle':'tooltip','title':self.receivers})
        if self.num == 0 and self.ref:
            a.text = f"ref {self.ref[0].fullkey}"
        else:
            a.text = self.fullkey

        if self.permanent:
            i = ET.Element('i',attrib={'class':'bi bi-asterisk','style':'color: red;'})
            a.append(i)
        

        return ET.tostring(a,encoding='unicode',method='html')

    @property
    def tag_html(self):
        span = ET.Element('span',attrib={'class':'small ms-1'})
        if len(self.tags) > 3:
            span.attrib['data-bs-toggle'] = 'tooltip'
            span.attrib['title'] = ",".join(self.tags)

        for i,tag in enumerate(self.tags):
            t = ET.Element('span',attrib={'class':f'badge bg-success'})
            if len(self.tags) > 3 and i == 2:
                t.text = '...'
                span.append(t)
                break
            else:
                t.text = tag
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
                dep.text = "."
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

        if current_user.admin or rg[0] in ['des','box'] or self.state < 2 and self.rel_flow(reg) == 'out' or self.register.permissions() == 'editor':
            despacho = '&despacho=true' if rg[0] == 'des' else ''
            edit_link = ET.Element('a',attrib={'href':f'/edit_note?note={self.id}{despacho}','data-bs-toggle':'tooltip','title':gettext('Edit note')})
            delete_link = ET.Element('button',attrib={'class':'btn btn-link p-0 ms-1','onclick':f"myFunction('{self.fullkey}',{self.id})",'data-bs-toggle':'tooltip','title':gettext('Delete note')})
        
        elif not rg[2] in ['','pending'] and self.rel_flow(reg) == 'in':
            edit_link = ET.Element('a',attrib={'href':f'/edit_note?note={self.id}&ctr={rg[2]}','data-bs-toggle':'tooltip','title':gettext('Edit note')})

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
        elif self.flow == 'out' and self.state < 2 and self.sender == current_user:
            return True
        elif self.flow == 'out' and self.state == 1 and 'scr' in current_user.groups:
            return True

        return False
    
    def status_html(self,reg):
        rg = reg.split("_")
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
    
    def state_min_html(self,reg,user):
        if self.sender == user:
            if self.state == 0: # Sender is working on it
                a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':gettext('Start circulation minuta')})
                i = ET.Element('i',attrib={'class':'bi bi-hourglass-top','style':'color: green;'})
            elif self.state == 4:
                a = ET.Element('span',attrib={'data-bs-toggle':'tooltip','title':f'Circulating ({self.read_by})'})
                i = ET.Element('i',attrib={'class':'bi bi-hourglass-split','style':'color: gray;'})
            elif self.state == 2:
                a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':'Circulation done. Mark as done'})
                i = ET.Element('i',attrib={'class':'bi bi-hourglass-bottom','style':'color: red;'})
            elif self.state == 6:
                a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':'Mark as undone'})
                i = ET.Element('i',attrib={'class':'bi bi-check','style':'color: blue;'})
        else:
            if self.state <= 5:
                if not self.is_read(user): # User has already done this note
                    a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':'Pass to the next one'})
                    i = ET.Element('i',attrib={'class':'bi bi-hourglass-split','style':'color: red;'})
                else: 
                    a = ET.Element('span',attrib={'data-bs-toggle':'tooltip','title':f'Circulating ({self.read_by})'})
                    i = ET.Element('i',attrib={'class':'bi bi-hourglass-split','style':'color: gray;'})
            elif self.state == 6:
                a = ET.Element('span',attrib={'data-bs-toggle':'tooltip','title':'Done'})
                i = ET.Element('i',attrib={'class':'bi bi-check','style':'color: blue;'})




        if self.reg == 'min' and self.sender == user and self.state == 2:
            div = ET.Element('span')
            a2 = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}&again=true','data-bs-toggle':'tooltip','title':'Circulate minuta again from beginning'})
            i2 = ET.Element('i',attrib={'class':'bi bi-hourglass-bottom','style':'color: green;'})
            a.append(i)
            a2.append(i2)
            div.append(a)
            div.append(a2)
            rst = div
        else:
            a.append(i)
            rst = a
        return ET.tostring(rst,encoding='unicode',method='html')


                
