from xml.etree import ElementTree as ET
from flask import current_app

class FileHtml(object): 
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
