import re
from datetime import date

from sqlalchemy import select

from app import db

class FileProp(object):
    @property
    def name(self):
        return self.path.split("/")[-1]

    @property
    def type(self):
        if len(self.name.split(".")) == 1:
            return 'folder'
        elif self.name.split(".")[1] in ['odoc','osheet','oslide']:
            return 'synology'
        else:
            return 'file'
    
    @property
    def ext(self):
        if self.type == 'folder':
            return ""
        else:
            return self.name.split(".")[-1]
    
    @property
    def chain_link(self):
        if self.type == 'synology':
            return 'oo/r'
        else:
            return 'd/f'

    @property
    def register(self):
        for rg in ['vcr','vc','dg','cc','desr']:
            if re.search(fr"\b{rg}\b",self.subject):
                return rg

        if self.sender == 'cg@cardumen.lan':
            return 'cg'
        elif self.sender == 'asr':
            return 'asr'
        else:
            return 'r'

    def getLinkSheet(self,text = None):
        link_text = text if text else self.name
        return f'=HYPERLINK("#dlink=/{self.chain_link}/{self.permanent_link}", "{link_text}")'

    def getLinkMessage(self,text = None):
        link_text = text if text else self.name
        return f'<https://nas.prome.sg:5001/{self.chain_link}/{self.permanent_link}|{link_text}>'


    @property
    def guess_number(self):
        if ";" in self.subject:
            temp = self.subject.split(";")[0]
            if "/" in temp:
                temp = re.findall(r'\d+',temp)
                if len(temp) > 1:
                    return f"{int(temp[0])}/{int(temp[1])}"

        temp = re.findall(r'\d+',self.path.split('/')[-1])
        
        if temp:
            return f"{int(temp[0])}/{date.today().year-2000}"

    
