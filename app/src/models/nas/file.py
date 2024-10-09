from app import db
from pathlib import Path

from .nas import get_info,rename_path, move_path, copy_path, convert_office, download_path, create_folder

class FileNas(object):
    def move_to_note(self,dest):
        #rst = move_path(self.path,dest)
        rst = move_path(f'link:{self.permanent_link}',dest)
        if rst:
            self.path = self.path.split('/')[-1]

    def move(self,dest,dest_original = None):
        return move_path(f'link:{self.permanent_link}',f"{dest}")
        #return move_path(self.path,f"{dest}")

    def copy(self,dest):
        return copy_path(f'link:{self.permanent_link}',f"{dest}/{self.name}")
        #return copy_path(f"{self.path}/{self.name}",f"{dest}/{self.name}")

    def convert(self):
        self.original_name = self.name
        self.original_id = self.file_id
        
        rst = convert_office(self.file_id)
        
        self.name = rst['name']
        self.file_id = rst['id']
        self.permanent_link = rst['permanent_link']

