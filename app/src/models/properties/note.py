from datetime import date
import re

from flask import flash, session, current_app
from flask_login import current_user

from sqlalchemy import case, and_, or_, not_, select, type_coerce, literal_column, func, union
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from app import db
from app.src.tools.mail import send_email

from app.src.models.nas.nas import toggle_share_permissions

class NoteProp(object):
    def light_row(self,reg):
        if self.reg == 'mat':
            if self.sender_id == current_user.id:
                if self.status == 'shared' or self.archived:
                    return "fw-light"
            else:
                if not self.result('is_current_target'):
                    return "fw-light"
        return ""

    @hybrid_method
    def contains_in(self,attr,value):
        return value in getattr(self,attr).split(',')

    @contains_in.expression
    def contains_in(cls,attr,value):
        return getattr(cls,attr).regexp_match(fr'(^|[^-])\b{value}\b($|[^-])')

    @property
    def folder_notes(self):
        return current_app.config['SYNOLOGY_FOLDER_NOTES']

    @property
    def in_folder_notes(self):
        return current_app.config['SYNOLOGY_FOLDER_NOTES'] in self.path

    def first_file(self,ctr=None):
        if not self.files:
            return None

        if ctr:
            for file in self.files:
                if file.subject == '' or ctr in file.subject.split(','):
                    break
            return file

        return self.files[0]

    def number_refs(self,reg):
        cont = 0
        if reg[2]:
            for ref in self.ref:
                if ref.reg != 'mat' or not reg[2]:
                    cont += 1
        else:
            cont = len(self.ref)
        
        return cont

    def is_target(self,user=current_user):
        return user in self.receiver

    def permissions(self,demand):
        match demand:
            case 'can_edit':
                if current_user.admin:
                    return True
                elif self.register.permissions == 'editor':
                    return True
                elif self.sender_id == current_user.id:
                    if self.register.alias == 'mat' and self.status in ['draft','approved','denied']:
                        return True
                    elif not self.archived:
                        return True
            case 'can_delete':
                if current_user.admin:
                    return True
                elif self.register.permissions == 'editor' and not self.status in ['registered','sent']:
                    return True
                elif self.sender_id == current_user.id:
                    if self.register.alias == 'mat' and self.status in ['draft','approved','denied']:
                        return True
                    elif not self.status in ['registered','sent']:
                        return True
            case 'can_mark_for_deletion':
                if current_user.admin or 'despacho' in current_user.groups:
                    return True
                elif current_user.id == self.sender_id:
                    return True

                return False


            case 'can_assign_permissions':
                if current_user.admin or 'despacho' in current_user.groups:
                    return True
            case 'can_edit_files':
                if self.sender_id == current_user.id and self.status in ['draft'] or current_user.admin:
                    return True
            case 'can_read':
                if self.register.alias == 'mat':
                    return False

                if current_user.category == 'of':
                    return self.is_target() or self.result('access') in ['reader','editor']
                else:
                    return True
            case 'can_archive':
                if self.register.alias == 'mat':
                    if self.sender_id == current_user.id and (self.status in ['approved','denied'] or not self.receiver):
                        return True
                else:
                    if self.status == 'registered' and (self.is_target() or self.register.permissions == 'editor'):
                        return True
            case 'can_send':
                return self.sender_id == current_user.id and self.status in ['draft','queued']
            case 'can_check_info':
                if self.register.alias == 'mat':
                    return False
                else:
                    if self.flow == 'in':
                        return True
            case 'can_sign_matter':
                return self.result('is_current_target')
            case 'can_return_matter':
                rst = self.actived_status()
                
                if len(rst) > 1:
                    return False
                else:
                    return True
        
        return False


    @property
    def receivers(self):
        return ",".join([rec.alias for rec in self.receiver])

    def refs(self,only = []):
        rst = []
        for ref in self.ref:
            if only == [] or ref.register.alias in only:
                rst.append(ref)
        return ",".join([ref.fullkey_short for ref in rst])

    @hybrid_property
    def fullkey_short(self):
        return self.fullkey_ls(long_key=False) 
   
    @hybrid_property
    def fullkey_folder(self):
        return self.fullkey_ls(long_key=False,folder=True)
 
    #@hybrid_property
    @property
    def fullkey(self):
        return self.fullkey_ls()

    def fullkey_ls(self,long_key = True, folder = False):
        if self.flow == 'in':
            alias = self.sender.alias
            pattern = self.register.in_pattern.split('|')[-1].strip(' ^$')
            if pattern == '' and folder: # Only for cg, because the short version is none we use the other
                pattern = self.register.in_pattern.split('|')[0].strip(' ^$')
        else:
            if 'only_cg' in self.register.groups:
                alias = 'cg'
                #pattern = self.register.out_pattern.split('|')[0].strip(' ^$')
                pattern = self.register.alias
            elif len(self.receiver) == 0 and self.register.alias != 'mat' and not folder:
                alias = "EMPTY"
                pattern = self.register.out_pattern.split('|')[0].strip(' ^$')
            elif len(self.receiver) == 1 and long_key:
                alias = self.receiver[0].alias if self.register.alias != 'mat' else self.sender.alias
                pattern = self.register.out_pattern.split('|')[0].strip(' ^$')
            else:
                alias = "" if self.register.alias != 'mat' else self.sender.alias
                pattern = self.register.out_pattern.split('|')[-1].strip(' ^$')

        prot = eval(fr"f'{pattern}'")
        return f"{prot} {self.num}/{self.year-2000}"

    @property
    def link(self):
        return f"https://{current_app.config['SYNOLOGY_SERVER']}:{current_app.config['SYNOLOGY_PORT']}/d/f/{self.permanent_link}"

    @hybrid_property
    def matters_order(self):
        if self.reg != 'mat':
            if self.result('is_read'):
                return 3
            else:
                return 1
        elif self.sender_id == current_user.id and self.status in ['draft','approved','denied']: #My proposal and I have to do something because is new or reviewed
            return 2
        elif self.sender_id != current_user.id and self.result('is_current_target'): #My turn to review
            return 1
        else:
            return 3

    @matters_order.expression
    def matters_order(cls):
        return case (
            #(and_(cls.reg!='mat',cls.result('is_read')),2),
            (cls.archived,3),
            (cls.status=='sent',3),
            (cls.reg!='mat',1),
            (and_(cls.status.in_(['draft','approved','denied']),cls.sender==current_user),1),
            (and_(cls.result('is_target'),cls.current_target_order==cls.result('target_order'),not_(cls.result('is_done'))),1),
            (cls.reg=='mat',2),
            else_=3,
        )

    @property
    def folder_name(self):
        folder = ''
        if self.num == 0: # Es una ref
            if self.ref:
                if self.ref[0]:
                    folder = self.ref[0].fullkey_folder.split("/")[0]
            else:
                folder = "not defined"
        else: 
            folder = self.fullkey_folder.split("/")[0]
        
        name,num = folder.split(" ")
        num = f"0000{num}"[-4:]
        
        if self.num == 0:
            return f"ref {name}_{num}"
        else:
            return f"{name}_{num}"

    @property
    def folder_parent(self):
        return f"{self.path}"

    @property
    def folder_path(self):
        return f"{self.folder_parent}/{self.folder_name}"



  
