from xml.etree import ElementTree as ET

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

        a = ET.Element('a',attrib={'class':'ms-1','href':f'https://nas.prome.sg:5001/{chain}/{self.permanent_link}','target':"_blank",'data-bs-toggle':'tooltip','title':self.name})
        i = ET.Element('i',attrib={f'class':f'bi {icon} position-relative','style':f'color: {color};'})
        
        if self.note.n_date < self.date:
            sp = ET.Element('span',attrib={'class':'position-absolute top-0 start-100 translate-middle p-1 bg-danger border border-light rounded-circle'})

            i.append(sp)
        
        if "/" in self.path:
            sp = ET.Element('span',attrib={'class':'position-absolute top-0 translate-middle p-1 bg-warning border border-light rounded-circle'})

            i.append(sp)

        a.append(i)

        return a
    
    @property
    def icon_html(self):
        return ET.tostring(self.icon_html_raw,encoding='unicode',method='html')

    @property
    def subject_html(self):
        if self.note.reg == 'ctr' and self.note.flow == 'out':
            if self.subject == '':
                sp = ET.Element('span',attrib={})
                sp.text = '(all)'
            elif ",,,," in self.subject: # Several ctrs...
                sp = ET.Element('span',attrib={'data-bs-toggle':self.subject,'title':'(...)'})
            else:
                sp = ET.Element('span',attrib={})
                sp.text = self.subject

            return ET.tostring(sp,encoding='unicode',method='html')

        return ""
