from datetime import datetime

from flask import flash

from sqlalchemy import and_, select, func, case
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from app import db
from .nas import create_folder, get_info, files_path, move_path, copy_path, delete_path, preview
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

    @property
    def preview(self):
        return preview(self.permanent_link)

    def addFile(self,file):
        rst = True
        if '/' in file.path:
            rst = file.move(self.folder_path)
            if rst:
                file.path = file.path.split('/')[-1]

        self.files.append(file)

        return rst

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
            return f"<https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}/d/f/{self.permanent_link}|{text}>"
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

    def updateFiles(self):
        if not self.permanent_link: # There is no permanent_link, I should get it first
            rst = self.getPermanentLink()
        else:
            rst = True
        
        if not rst:
            flash("Could not update files. Try again")
            return False

        files = files_path(self.folder_path)
        self.deleteFiles([f.id for f in self.files])

        for file in files:
            kargs = {'path':file['name'],'permanent_link':file['permanent_link']} 
            self.addFileArgs(**kargs)
        
        """
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
        """ 
    
        db.session.commit()

