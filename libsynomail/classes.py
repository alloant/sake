from pathlib import Path
from attrdict import AttrDict
from datetime import datetime

import logging

from libsynomail.nas import get_info,rename_path, move_path, copy_path, convert_office, download_path, create_folder
from libsynomail import INV_EXT, EXT


class File(AttrDict):
    def __init__(self,data,original_name = '',original_id = ''):
        self.name = data['name']
        self.type = data['type']
        self.path = str(Path(data['display_path']).absolute().parent)
        self.file_id = data['file_id']
        self.permanent_link = data['permanent_link']
        self.original_name = original_name
        self.original_id = original_id
    
    def __str__(self): 
         return self.name
    
    @property
    def display_path(self):
        return f"{self.path}/{self.name}"

    @property
    def ext(self):
        return Path(self.name).suffix[1:]

    @property
    def chain_link(self):
        if self.type == 'dir' or not self.ext in INV_EXT:
            return 'd/f'
        else:
            return 'oo/r'

    def getLinkSheet(self,text = None):
        link_text = text if text else self.name
        return f'=HYPERLINK("#dlink=/{self.chain_link}/{self.permanent_link}", "{link_text}")'

    def getLinkMessage(self,text = None):
        link_text = text if text else self.name
        return f'<https://nas.prome.sg:5001/{self.chain_link}/{self.permanent_link}|{link_text}>'

    def exportExcel(self):
        return [self.name,self.type,self.display_path,self.file_id,self.permanent_link,self.original_name,self.original_id]

    def move(self,dest,dest_original = None):
        rst = move_path(self.file_id,dest)
        if rst:
            if self.original_name and dest_original:
                move_path(self.original_id,dest_original)
            self.path = dest
            self.file_id = rst['id']
        
        return rst

    def copy(self,dest):
        return copy_path(f"{self.path}/{self.name}",f"{dest}/{self.name}")
        return copy_path(self.file_id,f"{dest}/{self.name}")

    def convert(self):
        self.original_name = self.name
        self.original_id = self.file_id
        
        rst = convert_office(self.file_id)
        
        self.name = rst['name']
        self.file_id = rst['id']
        self.permanent_link = rst['permanent_link']

    def rename(self,new_name):
        rst = rename_path(self.file_id,new_name)

        if rst: self.name = new_name

    def download(self,dest = None):
        return download_path(f"{self.path}/{self.name}",dest)
        return download_path(self.file_id,dest)


class Note(AttrDict):
    def __init__(self,reg,tp,source,no,flow='in',isref=0,ref='',date=None,content='',dept='',comments='',year=None):
        self.register = reg
        self.type = tp
        self.source = source
        self._no = no
        self.ref = ref
        self.date = date if date else datetime.today()
        self.content = content
        self.dept = dept
        self.comments = comments
        self.year = str(year) if year else str(datetime.today().strftime('%Y'))
        self.files = []
        self.permanent_link = ''
        self.folder_id = ''
        self.folder_path = ''
        self.archived = ''
        self.sent_to = ''
        self.flow = flow
        self.isref = isref
   
        #if self.flow == 'out' and self.dept == '' and self.content == '':
        #    note.dept,note.content = register.scrap_destination(note.no)

    def __str__(self):
         return self.key

    def __eq__(self,other):
        if isinstance(other,Note):
            if self.key == other.key:
                return True

        return False

    @property
    def no(self):
        return int(self._no)

    @no.setter
    def no(self,value):
        self._no = value
    
    def get_key_subject(self,full = False,r = False):
        if self.flow == 'in':
            if self.type in ['r','ctr']:
                key = f"{self.source} "
            else:
                key = f"{self.type} "
        else:
            tp = self.type_from_no

            if tp == 'cg':
                key = f'Aes '
            elif tp == 'asr':
                key = f"cr-asr "
            elif tp == 'ctr':
                key = f"cr "
            elif tp == 'r':
                if r:
                    if "," in self.dept:
                        key = f"Aes-r "
                    else:
                        key = f"Aes-{self.dept}"
                else:
                    key = f"Aes-r "

        if full:
            key += f"0000{self.no}"[-4:]
        else:
            key += f"{self.no}"
        
        return key

    def get_key(self,full = False,r = False):
        if self.flow == 'in':
            if self.type in ['r','ctr']:
                key = f"{self.source}_"
            else:
                key = f"{self.type}_"
        else:
            tp = self.type_from_no

            if tp == 'cg':
                key = f'Aes_'
            elif tp == 'asr':
                key = f"cr-asr_"
            elif tp == 'ctr':
                key = f"cr_"
            elif tp == 'r':
                if r:
                    if "," in self.dept:
                        key = f"Aes-r_"
                    else:
                        key = f"Aes-{self.dept}"
                else:
                    key = f"Aes-r_"

        if full:
            key += f"0000{self.no}"[-4:]
        else:
            key += f"{self.no}"
        
        return key
    
    key = property(get_key)

    @property
    def type_from_no(self):
        if self.flow == 'out':
            if self.no < 250:
                tp = 'cg'
            elif self.no < 1000:
                tp = 'asr'
            elif self.no < 2000:
                tp = 'ctr'
            else:
                tp = 'r'

        return tp

    @property
    def archive_folder(self):
        if self.flow == 'in':
            return f"{self.type} {self.flow} {self.year}"
        else:
            return f"{self.type_from_no} {self.flow} {self.year}"
   
    @property
    def message(self):
        message = f"Content: `{self.content}` \nLink: {self.messageLink()} \nAssigned to: *{self.dept}*"
        
        if self.ref != '':
            message += f"\nRef: _{self.ref}_"
        
        if self.comments != '':
            message += f"\nComment: _{self.comments}_"
 
        message +=  f"\nRegistry date: {self.date}"

        return message

    @property
    def of_annex(self):
        annex = len(self.files) - 1

        return annex if annex > 0 else ''
 
    def addFile(self,file):
        self.files.append(file)

    def sheetLink(self,text):
        if self.permanent_link:
            return f'=HYPERLINK("#dlink=/d/f/{self.permanent_link}", "{text}")'
        else:
            if self.files:
                return self.files[0].getLinkSheet(text)
            else:
                return ''

    def messageLink(self):
        if self.type == 'cg':
            text = f"{self.no}/{str(self.year)[2:]}"
        elif self.type == 'asr':
            text = f"asr {self.no}/{str(self.year)[2:]}"
        else:
            text = f"{self.source} {self.no}/{str(self.year)[2:]}"
        
        if self.permanent_link:
            return f'<https://nas.prome.sg:5001/d/f/{self.permanent_link}|{text}>'
        else:
            return self.files[0].getLinkMessage(text)


    def exportExcel(self):
        return [self.register,self.type,self.source,self.sheetLink(self.no),self.year,self.ref,self.date,self.content,self.dept,self.of_annex,self.comments,self.archived,self.sent_to]

    def move(self,dest):
        logging.info(f"Moving {self.key} to {dest}")
        if self.folder_id:
            rst = move_path(self.folder_id,dest)
            if rst: 
                self.folder_path = f"{dest}/{Path(self.folder_path).stem}"
                self.folder_id = rst['id']
                for file in self.files:
                    file.path = self.folder_path
                return True
        else:
            cont = 0
            for file in self.files:
                cont += 1 if file.move(dest) else 0
            
            if cont == len(self.files):
                return True
            else:
                return False

    def copy(self,dest):
        logging.info(f"Copying {self.key} to {dest}")
        if self.folder_path:
            rst = copy_path(self.folder_path,f"{dest}/{Path(self.folder_path).stem}")
            if rst:
                return True
        else:
            cont = 0
            for file in self.files:
                cont += 1 if file.copy(dest) else 0
            
            if cont == len(self.files):
                return True
            else:
                return False


    def organice_files_to_despacho(self,path_dest,path_originals):
        key = self.get_key(full=True)
        #Change names of files
        if self.register == 'cr':
            for i,file in enumerate(self.files):
                if i == 0:
                    old_name = Path(file.name).stem
                    if self.source == 'r': key = f"r_{key}"
                    new_name = f"{key}.{file.ext}" if self.isref == 0 else f"{key}_ref.{file.ext}" 
                else:
                    new_name = f"{file.name.replace(old_name,key)}".strip().replace('&','and')

                file.rename(new_name)
        else:
            key = f"{self.register}{key}"

        
        # Moving files to inbox folder
        dest =f"{path_dest}"

        #Create a folder if needed
        if self.of_annex != '':
            rst = create_folder(dest,key)
            if not rst: return None
            dest = f"{dest}/{key}"
            self.folder_id = rst['id']
            self.folder_path = dest
            self.permanent_link = rst['permanent_link']
        
        # Convert the files to Synology office
        if self.flow == 'in' or self.type_from_no == 'ctr':
            for file in self.files:
                if file.ext in EXT:
                    file.convert()

        # Move the files to dest
        for file in self.files:
            file.move(dest,path_originals)

        





