from datetime import datetime

from flask import flash

from sqlalchemy import and_, select, func, case
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from app import db
from .nas import create_folder, get_info, files_path, move_path, copy_path, delete_path
#from app.models.file import File

class NoteNas(object): 
    @property
    def message(self):
        message = f"Content: `{self.content}` \nLink: {self.messageLink()} \nAssigned to: *{self.dept}*"
        
        if self.ref != '':
            message += f"\nRef: _{self.ref}_"
        
        if self.comments != '':
            message += f"\nComment: _{self.comments}_"
 
        message +=  f"\nRegistry date: {self.date}"

        return message
    
    def addFile(self,file):
        rst = file.move(self.path)
        if rst:
            file.path = file.path.split('/')[-1]

        self.files.append(file)

    def sheetLink(self,text):
        if self.permanent_link:
            return f'=HYPERLINK("#dlink=/d/f/{self.permanent_link}", "{text}")'
        else:
            if self.files:
                return self.files[0].getLinkSheet(text)
            else:
                return ''

    def getPermanentLink(self): # Gets the link and creates the folder if needed
        rst = create_folder(self.path,self.folder_name)

        if rst:
            self.permanent_link = rst['permanent_link']
            db.session.commit()
            return True
        else:
            flash(f'Could not create folder {self.folder_path}')
            return False

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

    def delete_folder(self):
        delete_path(f"{self.path}/{self.folder_name}")

    def create_folder(self,folder = None):
        if folder:
            rst = create_folder(self.path,folder)
        else:
            rst = create_folder(self.path,self.folder_name)

        if rst:
            if 'permanent_link' in rst:
                self.permanent_link = rst['permanent_link']

    def move(self,dest):
        if self.path == dest:
            return True
        rst = move_path(self.folder_path,dest)
        if rst:
            self.path = dest
            db.session.commit()
            return True
        return False

    def copy(self,dest):
        return copy_path(self.folder_path,f"{dest}/{self.folder_name}")

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

    def updateFiles(self):
        if not self.permanent_link: # There is no permanent_link, I should get it first
            rst = self.getPermanentLink()
        else:
            rst = True
        
        if not rst:
            flash("Could not update files. Try again")
            return False

        files = files_path(self.folder_path)
        
        # Just checking the files that are already assigned to the note and fixing the path of the file in the case it has not been yet 
        ntfiles = []
        for file in self.files:
            if "/" in file.path:
                if self.path != "/".join(file.path.split("/")[:-1]):
                    file.move_to_note(self.folder_path)
            ntfiles.append(file.path.split("/")[-1])
        
        extfiles = []
        if files:
            for file in files:
                if not file['name'] in ntfiles:
                    kargs = {'path':file['name'],'permanent_link':file['permanent_link']} 
                    self.addFileArgs(**kargs)
                
                extfiles.append(file['name'])
                
        rmfiles = [f.id for f in self.files if not f.path.split("/")[-1] in extfiles]
        self.deleteFiles(rmfiles)
            
    
        db.session.commit()

