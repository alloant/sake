import re
from datetime import date
from flask import current_app

from sqlalchemy import select
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from app import db

class FileProp(object):
    @property
    def name(self):
        return self.path.split("/")[-1]
    
    @property
    def short_name(self):
        name = self.path.split("/")[-1]
        if len(name) < 15:
            return name
        else:
            return f'{name[:12]}...'

    @property
    def type(self):
        if len(self.name.split(".")) == 1:
            return 'folder'
        elif self.name.split(".")[-1] in ['odoc','osheet','oslide']:
            return 'synology'
        else:
            return 'file'


    @property
    def bi_icon(self):
        if self.ext == "osheet":
            return "bi-file-earmark-excel-fill text-success"
        elif self.ext == "odoc":
            return "bi-file-earmark-word-fill text-primary"
        elif self.ext == "oslides":
            return "bi-file-earmark-slides-fill text-warning"
        elif self.ext == "pdf":
            return "bi-file-earmark-pdf-fill text-danger"
        elif self.ext == "":
            return "bi-folder-fill"
        elif self.ext in ['doc','docx','ppt','pptx','xls','xlsx']:
            return f"bi-filetype-{self.ext} text-secondary"
        elif self.ext in ['mp4','mkv']:
            return "bi-file-earmark-play-fill text-info"
        elif self.ext in ['mp3','wav']:
            return "bi-file-earmark-music-fill text-info"
        elif self.ext in ['jpg','gif','png']:
            return "bi-file-earmark-image-fill text-warning"
        else:
            return "bi-file-earmark-fill"

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
        return f"<https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}/{self.chain_link}/{self.permanent_link}|{link_text}>"
    
    @property
    def link(self):
        return f"https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}/{self.chain_link}/{self.permanent_link}"

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

    
