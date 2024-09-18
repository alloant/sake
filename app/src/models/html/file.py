from xml.etree import ElementTree as ET
from flask import current_app

class FileHtml(object): 
    @property
    def icon_html_raw(self):
        match self.ext:
            case "osheet":
                icon = "bi-file-earmark-excel-fill"
                color = "green"
                chain = "oo/r"
            case "odoc":
                icon = "bi-file-earmark-word-fill"
                color = "blue"
                chain = "oo/r"
            case "pdf":
                icon = "bi-file-earmark-pdf-fill"
                color = "red"
                chain = "d/f"
            case "": # It is a folder
                icon = "bi-folder-fill"
                color = "orange"
                chain = "d/f"
            case _:
                icon = "bi-file-earmark-fill"
                color = "gray"
                chain = "d/f"

        a = ET.Element('a',attrib={'class':'ms-1','href':f"https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}/{chain}/{self.permanent_link}",'target':"_blank",'data-bs-toggle':'tooltip','title':self.name})
        i = ET.Element('i',attrib={f'class':f'bi {icon} position-relative','style':f'color: {color};'})
        
        #if self.note.n_date < self.date:
        #    sp = ET.Element('span',attrib={'class':'position-absolute top-0 start-100 translate-middle p-1 bg-danger border border-light rounded-circle'})

        #    i.append(sp)
        
        if "/" in self.path:
            sp = ET.Element('span',attrib={'class':'position-absolute top-0 translate-middle p-1 bg-warning border border-light rounded-circle'})

            i.append(sp)

        a.append(i)

        return a
   
    def icon_html_read_raw(self,reg):
        match self.ext:
            case "osheet":
                icon = "bi-file-earmark-excel-fill"
                color = "green"
                chain = "oo/r"
            case "odoc":
                icon = "bi-file-earmark-word-fill"
                color = "blue"
                chain = "oo/r"
            case "pdf":
                icon = "bi-file-earmark-pdf-fill"
                color = "red"
                chain = "d/f"
            case "": # It is a folder
                icon = "bi-folder-fill"
                color = "orange"
                chain = "d/f"
            case _:
                icon = "bi-file-earmark-fill"
                color = "gray"
                chain = "d/f"
        
        link = f"https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}/{chain}/{self.permanent_link}"
       
    
        a = ET.Element('span',attrib={'class':'ms-1','hx-on:htmx:after-request':f'window.open("{link}")','hx-get':f'/read_note?note={self.note_id}&reg={reg}&file_clicked={self.id}','hx-swap':'none','role':'button','data-bs-toggle':'tooltip','title':self.name})
        i = ET.Element('i',attrib={f'class':f'bi {icon} position-relative','style':f'color: {color};'})
        
        if "/" in self.path:
            sp = ET.Element('span',attrib={'class':'position-absolute top-0 translate-middle p-1 bg-warning border border-light rounded-circle'})

            i.append(sp)

        a.append(i)

        return a
    
    def icon_html_read(self,reg):
        return ET.tostring(self.icon_html_read_raw(reg),encoding='unicode',method='html')
 
    @property
    def icon_html(self):
        return ET.tostring(self.icon_html_raw,encoding='unicode',method='html')

    def subject_html(self, form = False):
        if self.note.reg == 'ctr' and self.note.flow == 'out':
            if self.subject == '':
                sp = ET.Element('span',attrib={'id':f'recFiles-{self.id}'})
                sp.text = '(all)'
            elif len(self.subject.split(",")) > 2: # Several ctrs...
                sp = ET.Element('span',attrib={'id':f'recFiles-{self.id}','data-bs-toggle':'tooltip','title': self.subject})
                sp.text = f"(...)"
            else:
                sp = ET.Element('span',attrib={'id':f'recFiles-{self.id}'})
                sp.text = f"({self.subject})"
            if form:
                return sp
            else:
                return ET.tostring(sp,encoding='unicode',method='html')

        return ""
