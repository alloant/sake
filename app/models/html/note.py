from flask import session
from flask_login import current_user

from xml.etree import ElementTree as ET

from app import db
from sqlalchemy import select

class NoteHtml(object): 
    def refs_html(self,reg):
        rg = reg.split("_")
        html = []
        for ref in self.ref:
            if rg[0] == 'cl' and ref.reg == 'ctr' or rg[0] in ['cr','pen','des','box','min','vc','vcr','dg','cc','desr']:
                if rg[0] == 'des':
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>({ref.dep_html})')
                else:
                    html.append(f'<a href"#" data-bs-toggle="tooltip" data-bs-original-title="{ref.content}">{ref.fullkey}</a>')

        return ','.join(html)

    def fullkey_link_html(self,reg):
        rg = reg.split("_")
        nreg = 'cr' if rg[0] in ['min','pen','des'] else rg[0]
        a = ET.Element('a',attrib={'href':f'?reg={nreg}_all_{rg[2]}&h_note={self.id}','target':'_blank','data-bs-toggle':'tooltip','title':self.receivers})
        if self.num == 0 and self.ref:
            a.text = f"ref {self.ref[0].keyto(True,True)}/{self.year-2000}"
        else:
            a.text = f"{self.keyto(True,True)}/{self.year-2000}"

        if self.permanent:
            i = ET.Element('i',attrib={'class':'bi bi-asterisk','style':'color: red;'})
            a.append(i)
        

        return ET.tostring(a,encoding='unicode',method='html')

    @property
    def dep_html(self):
        dep = ET.Element('span',attrib={'class':f'badge {"bg-primary" if self.flow == "out" else "bg-danger"}'})
        if self.flow == 'in':
            if len(self.receiver) > 1:
                dep.attrib['data-bs-toggle'] = 'tooltip'
                dep.attrib['title'] = self.receivers
                dep.text = "(...)"
            else:
                dep.text = self.receivers
        else:
            dep.text = self.sender.alias
        
        return ET.tostring(dep,encoding='unicode',method='html')

       
    
    def content_html(self,reg):
        text = self.content_jp if 'jp' in current_user.groups else self.content
        rg = reg.split("_")

        if rg[0] == 'cl' and self.flow == 'in' or rg[0] != 'cl' and self.flow == 'out' or self.is_read(current_user):
            ct = ET.Element('span',attrib={'class':f''})
            ct.attrib['data-toggle'] = 'tooltip'
            ct.attrib['title'] = ""
            ct.text = text
        else:
            ct = ET.Element('div')
            ct.attrib['hx-get'] = f"/read_note?note={self.id}"

            cti = ET.Element('span',attrib={'class':f'fw-bold','role':'button'})
            cti.attrib['data-toggle'] = 'tooltip'
            cti.attrib['title'] = "Mark as read"
            cti.text = text

            ct.append(cti)

        return ET.tostring(ct,encoding='unicode',method='html')
        


    def row_decoration(self,reg,user):
        rg = reg.split('_')
        return f'<tr class="">'

        if rg[0] == 'min':
            if self.sender == user: # The one who wrote the minuta
                if self.state in [0,5]:
                    return f'<tr class="fw-bold" id="table-row-{self.id}">'
                elif self.state == 6:
                    return f'<tr class="fst-italic" id="table-row-{self.id}">'
            else:
                if not self.is_read(user):
                    return f'<tr class="fw-bold" id="table-row-{self.id}">'
                elif self.state == 6:
                    return f'<tr class="fst-italic">'
        elif rg[0] in ['cr','cl','pen']:
            if self.rel_flow(reg) == 'in':
                if not self.is_read(user):
                    return f'<tr class="fw-bold">'
                elif self.state == 6:
                    return f'<tr class="fst-italic">'
            else:
                if self.state in [0,5]:
                    return f'<tr class="fw-bold">'
                elif self.state == 6:
                    return f'<tr class="text-muted">'



        return "<tr>"
    
    def status_html(self,reg):
        rg = reg.split("_")
        sp = ET.Element('span',attrib={'hx-post':f'/state_note?note={self.id}&reg={reg}','role':'button'})
        if rg[0] == 'des':
            if self.is_read(f"des_{current_user.alias}"):
                icon = "bi-hourglass-bottom"
                color = "gray"
                text = "Unsign note"
            else:
                color = "orange"
                if self.state == 3: #Nobody has check it before
                    text = "Sign note"
                    icon = "bi-circle-fill"
                else:
                    text = "Sign note (the other d has already signed)"
                    icon = "bi-check-circle"
        elif self.flow == 'out' and rg[0] == 'cl' or self.flow == 'in' and rg[0] != 'cl': # It is IN
            if rg[0] == 'cl':
                done = self.ctr_has_done(session['ctr'])
                mine = True
            else:
                done = True if self.state > 5 else False
                mine = True if current_user in self.receiver else False

            if mine:
                mn = '-fill'
            else:
                mn = ''
                sp = ET.Element('span')
                

            if done:
                icon = f"bi-check-circle{mn}"
                color = "green"
                text = "Mark note as pending"
            else:
                icon = f"bi-x-circle{mn}"
                color = "red"
                text = "Mark note as done"
        else: # Out for the ctr
            match self.state:
                case 0:
                    icon = "bi-send"
                    color = "gray"
                    text = "Send note to cr"
                case 1:
                    icon = "bi-check"
                    color = "gray"
                    text = "Waiting for cr to get the note (click to take note back from cr inbox)"
                case _:
                    sp = ET.Element('span')
                    icon = "bi-check"
                    color = "blue"
                    text = "Note has been received in cr"
        
        #text = ""

        i = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};','data-toggle':'tooltip','title':text})
        sp.append(i)
        return ET.tostring(sp,encoding='unicode',method='html')
    
    def state_html(self,reg,user,ctr):
        rg = reg.split("_")

        if rg[0] == 'cl':
            return self.state_cl_html(reg,user,ctr)
        elif rg[0] in ['cr','pen']:
            return self.state_cr_html(reg,user)
        elif rg[0] == 'min':
            return self.state_min_html(reg,user)
        elif rg[0] == 'des':
            return self.state_des_html(reg,user)
        elif rg[0] == 'box':
            return self.state_box_html(reg,user)
        else:
            return self.state_cr_html(reg,user)

    def state_other_html(self,reg,user):
        rg = reg.split("_")

    def state_cl_html(self,reg,user,ctr):
        rg = reg.split("_")
        if self.flow == 'out': # Notes in for the ctr. 3 options: no read, read and done
            if self.is_read(user):
                if self.is_done(ctr):
                    icon = "bi-check-circle"
                    action = "state"
                    text = "Mark as undone"
                    color = "green"
                else:
                    icon = "bi-x-circle"
                    action = "state"
                    text = "Mark as done"
                    color = "red"
            else:
                if self.is_done(ctr):
                    color = "gray"
                else:
                    color = "red"
                icon = "bi-envelope-fill"
                text = "Mark as read"
                action = "read"
        else: # Note from ctr to cr
            action = "state"
            if self.state == 0: # cl is still working on it
                icon = "bi-send"
                color = "gray"
                text = "Send note to cr"
            elif self.state == 1: # cl send it to cr but it is still in outbox
                icon = "bi-check"
                color = "gray" 
                text = "Take note back from cr"
            elif self.state > 1: # Note is already on despacho or beyond that
                icon = "bi-check"
                color = "blue"
                text = "Note has been received"
                action = ""
            
        if action:
            a = ET.Element('a',attrib={'href':f'?reg={reg}&{action}={self.id}','data-bs-toggle':'tooltip','title':text})
        else:
            a = ET.Element('span',attrib={'data-bs-toggle':'tooltip','title':text})
        
        i = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};'})
        a.append(i)
        
        return ET.tostring(a,encoding='unicode',method='html')

    def state_des_html(self,reg,user):
        if self.is_read(f"des_{user.alias}"):
            icon = "bi-hourglass-bottom"
            color = "gray"
            text = "Unsign note (other dr has already signed)"
        else:
            if self.state == 3: #Nobody has check it before
                text = "Sign note"
                icon = "bi-circle-fill"
            else:
                text = "Sign note (the other d has already signed)"
                icon = "bi-check-circle"
            color = "orange"

        a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':text})
        i = ET.Element('i',attrib={'class':f'bi {icon}','style':f'color: {color};'})
        a.append(i)
        
        return ET.tostring(a,encoding='unicode',method='html') 
    
    def state_box_html(self,reg,user):
        rg = reg.split("_")
        a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':'Archive the note'})
        if rg[1] == 'in':
            i = ET.Element('i',attrib={'class':'bi bi-floppy2','style':'color: orange;'})
        else:
            i = ET.Element('i',attrib={'class':'bi bi-send','style':'color: orange;'})
        
        a.append(i)
       
        return ""
        return ET.tostring(a,encoding='unicode',method='html') 
    
    def state_cr_html(self,reg,user):         
        if self.flow == 'in': # Notes from cg,asr,r and ctr. They could be read/unread and done/undone
            fill = "-fill" if self.is_involve(user,reg) else ""
            action = ""
            text = ""
            if self.is_read(user): # The note has been read   
                icon = f"bi-envelope-open{fill}"
            else:
                icon = f"bi-envelope{fill}"
                text = "Mark as read"
                action = "read"

            if self.state == 5: # Note is not done
                color = "gray"
                if fill and not action:
                    text = "Mark as done"
                    action = "state"
                    icon = f"bi-x-circle"
                    color = "red"
            else:
                color = "gray"
                if fill and not action:
                    text = "Mark as not done"
                    action = "state"
                    icon = "bi-check-circle"
                    color = "green"
        else: # Note send to cg,asr,r,ctr. Could be working, waiting, sent
            action = "state"
            if self.state == 0: # dr is still working on the note
                icon = "bi-send"
                color = "gray"
                text = "Send note to scr"
            elif self.state == 1: # dr send it to scr but it is still in outbox
                icon = "bi-check"
                color = "gray" 
                text = "Take note back from scr"
            elif self.state > 1: # Note is already sent
                icon = "bi-check"
                color = "blue"
                text = "Note has been sent"
                action = ""
            
        if action:
            a = ET.Element('a',attrib={'href':f'?reg={reg}&{action}={self.id}','data-bs-toggle':'tooltip','title':text})
        else:
            a = ET.Element('span',attrib={'data-bs-toggle':'tooltip','title':text})
        
        i = ET.Element('i',attrib={f'class':f'bi {icon}','style':f'color: {color};'})
        a.append(i)
        
        return ET.tostring(a,encoding='unicode',method='html')

    def state_min_html(self,reg,user):
        if self.sender == user:
            if self.state == 0: # Sender is working on it
                a = ET.Element('a',attrib={'href':f'?reg={reg}&state={self.id}','data-bs-toggle':'tooltip','title':'Start circulation minuta'})
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


                
