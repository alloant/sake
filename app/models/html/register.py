from xml.etree import ElementTree as ET

class RegisterHtml(object): 
    def link_icon_html(self,flow,subregister='',size=70):
        if subregister:
            img = ET.Element('img',attrib={'src':f'static/icons/ctr/{subregister}-{flow}.svg','width':f'{size}vmin','height':f'{size}vmin'})
        else:
            img = ET.Element('img',attrib={'src':f'static/icons/ctr/{self.alias}-{flow}.svg','width':f'{size}vmin','height':f'{size}vmin'})
        
        a = ET.Element('a',attrib={'class':'text-decoration-none','href':f'/register?reg={self.alias}_{flow}_{subregister}','data-bs-toggle':'tooltip','data-bs-placement':'right','data-bs-original-title':f'{self.alias} {flow}'})
        
        a.append(img)

        return ET.tostring(a,encoding='unicode',method='html')
