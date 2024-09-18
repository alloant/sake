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
    #@hybrid_property
    #def date(self):
    #    return self.n_date

    #@date.expression
    #def date(cls):
    #    return cls.n_date

    def light_row(self,reg):
        if self.reg == 'mat':
            if self.sender_id == current_user.id:
                if self.state in [1,6]:
                    return "fw-light"
            else:
                if not self.working_matter(current_user):
                    return "fw-light"
        return ""

    @property
    def groups(self):
        return self.n_groups.split(',')
   
    @property
    def tags(self):
        return self.n_tags.split(',')

    @hybrid_method
    def next_in_matters(cls,user):
        return case(
            (and_(cls.received_by.contains('|'),not_(cls.read_by.contains('|'))),and_(not_(cls.contains_read(user)),cls.contains_received_by_part(user))),
            else_ = cls.received_by.regexp_match(func.concat('^',cls.read_by,fr',*{user}.*'))
        )
    
    def working_matter(self,alias):
        if '|' in self.received_by and not '|' in self.read_by: # There are some people who read at the same time
            return bool(re.search(fr'\b{alias}\b',self.received_by.split('|')[0]) and not re.search(fr'\b{alias}\b',self.read_by))
        else: #Normal circulation
            return bool(re.search(fr'^{self.read_by.replace("|","\|")},*{alias}',self.received_by))
    
    @property
    def can_return_matter(self):
        return not bool(re.search(fr'\b{current_user.alias}\b.*\|',self.received_by))

    @hybrid_method
    def contains_read(cls,alias):
        return cls.read_by.regexp_match(fr'(^|[^-])\b{alias}\b($|[^-])')
    
    @hybrid_method
    def contains_received_by(cls,alias):
        return cls.received_by.regexp_match(fr'(^|[^-])\b{alias}\b($|[^-])')
    
    @hybrid_method
    def contains_received_by_part(cls,alias):
        return cls.received_by.regexp_match(fr'\b{alias}\b(?=.*\|)')

    @hybrid_method
    def contains_tag(cls,tag):
        return cls.n_tags.regexp_match(fr'(^|[^-])\b{tag}\b($|[^-])')
    
    @hybrid_method
    def contains_group(cls,group):
        return cls.n_groups.regexp_match(fr'(^|[^-])\b{group}\b($|[^-])')

    @hybrid_method
    def contains_privileges(cls,group):
        return cls.privileges.regexp_match(fr'(^|[^-])\b{group}\b($|[^-])')

    @hybrid_method
    def contains_in(self,attr,value):
        return value in getattr(self,attr).split(',')

    @contains_in.expression
    def contains_in(cls,attr,value):
        return getattr(cls,attr).regexp_match(fr'(^|[^-])\b{value}\b($|[^-])')

    def is_target(self,user=current_user):
        return user in self.receiver

    

    def permissions(self,demand):
        match demand:
            case 'can_edit':
                if current_user.admin:
                    return True
                elif self.sender_id == current_user.id or self.register.permissions == 'editor':
                    if self.register.alias == 'mat' and self.state in [0,5]:
                        return True
                    elif self.state < 6:
                        return True
            case 'can_assign_permissions':
                if current_user.admin or 'despacho' in current_user.groups:
                    return True
            case 'can_edit_files':
                if self.sender_id == current_user.id and self.state < 6 or current_user.admin:
                    return True
            case 'can_read':
                if self.register.alias == 'mat':
                    return False

                if 'of' in current_user.groups:
                    return self.is_target() or current_user.alias in self.privileges.split(',')
                else:
                    return True
            case 'can_archive':
                if self.register.alias == 'mat':
                    if self.sender_id == current_user.id:
                        if self.state >= 5 or not self.receiver:
                            return True
                else:
                    if self.state < 5:
                        return False
                    elif self.is_target() or self.register.permissions == 'editor':
                        return True
            case 'can_send':
                return self.sender_id == current_user.id and self.state < 2
            case 'can_check_info':
                if self.register.alias == 'mat':
                    return False
                else:
                    if self.flow == 'in':
                        return True
            case 'can_sign_matter':
                if '|' in self.received_by and not '|' in self.read_by: # There are some people who read at the same time
                    return bool(re.search(fr'\b{current_user.alias}\b',self.received_by.split('|')[0]) and not re.search(fr'\b{current_user.alias}\b',self.read_by))
                else: #Normal circulation
                    return bool(re.search(fr'^{self.read_by.replace("|","\|")},*{current_user.alias}',self.received_by))
            case 'can_return_matter':
                return not bool(re.search(fr'\b{current_user.alias}\b.*\|',self.received_by))
        
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
            return 1
        elif self.sender_id == current_user.id and self.state in [0,5]: #My proposal and I have to do something because is new or reviewed
            return 2
        elif self.sender_id != current_user.id and self.working_matter(current_user): #My turn to review
            return 1
        else:
            return 3

    @matters_order.expression
    def matters_order(cls):
        return case (
            (cls.reg!='mat',1),
            (and_(or_(cls.state==0,cls.state==5),cls.sender==current_user),2),
            (and_(cls.next_in_matters(current_user.alias),cls.sender!=current_user),1),
            else_=3,
        )

    @hybrid_method
    def is_done(self,user): #Use in state_cl and updateState for cl. We assume note is in for the ctr
        alias = user['alias'] if isinstance(user,dict) else user.alias
        dt = date.fromisoformat(user['date']) if isinstance(user,dict) else user.date

        if alias in self.received_by.split(','):
            rst = True
        else:
            rst = False
        
        if dt > self.n_date:
            rst = not rst
        
        return rst 

    @is_done.expression
    def is_done(cls,user):
        return case (
            (user.date < cls.n_date,not_(cls.received_by.regexp_match( fr'(^|[^-])\b{user.alias}\b($|[^-])' )) ),
        else_=cls.received_by.regexp_match( fr'(^|[^-])\b{user.alias}\b($|[^-])' )
        )

    @property
    def folder_name(self):
        if self.num == 0: # Es una ref
            if self.ref:
                if self.ref[0]:
                    folder = self.ref[0].fullkey_folder.split("/")[0]
            return None
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



    def updateRead(self,user):
        rb = self.read_by.split(',') if self.read_by else []
        alias = user if isinstance(user,str) else user.alias

        if alias in rb:
            rb.remove(alias)
            inc = -1
            self.read_by = ",".join([r for r in rb if r])
        else:
            if self.reg == 'mat' and '|' in self.received_by:
                if not '|' in self.read_by:
                    rec_by = self.received_by.split('|')[0].split(',')
                    rst = []
                    rb.append(alias)
                    for rec in rec_by:
                        print(rec)
                        if rec in rb:
                            rst.append(rec)
                    self.read_by = ",".join([r for r in rst if r])
                    if len(rec_by) == len(rst):
                        self.read_by += '|'
                else:
                    if not self.read_by[-1] == '|':
                        self.read_by += ','
                    self.read_by += alias
            else:
                rb.append(alias)
                self.read_by = ",".join([r for r in rb if r])
            inc = 1
        
        db.session.commit()
        return inc

    def updateState(self,reg,user,cancel=False):
        if reg[0] == 'box' and reg[1] == 'in': # Is the scr getting mail from cg, asr, ctr or r
            pass
        elif reg[0] == 'box' and reg[1] == 'out': # Is the scr getting mail from cg, asr, ctr or r
            if self.state == 1 and cancel:
                self.state = 0
            elif not 'personal' in self.register.groups: # Only for not personal calendars
                if self.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{self.year}/{self.reg} out"):
                    if 'folder' in self.register.groups: # Note for asr. We just copy it to the right folder
                        self.copy(f"/team-folders/Mail {self.register.alias}/Mail to {self.register.alias}") # I have to add this to the register database!!!!! Pending
                        self.state = 6
                    
                    if 'sake' in self.register.groups: # note for a ctr (internal sake system). We just change the state.
                        self.state = 6
                        for rec in self.receiver:
                            if rec.email:
                                try:
                                    send_email(f"New mail for {rec.alias} ({self.fullkey})","",rec.email)
                                except:
                                    flash(f"Could not send to {rec}")
        elif reg[0] == 'des': # Here states are only 2 or 3
            if self.reg in ['vcr','vc']:
                self.state = 5
            else:
                self.state += self.updateRead(f"des_{user.alias}")
                self.toggle_status_attr('sign_despacho')
                self.toggle_status_attr('read')
                self.updateRead(user)
        elif reg[2]:
            if self.flow == 'out': # Note from cr to the ctr
                rst = self.received_by.split(",")
                if reg[2] in rst:
                    rst.remove(reg[2])
                else:
                    rst.append(reg[2])
                if not rst: rst = ""
                self.received_by = ",".join([r for r in rst if r])
            else:
                if self.state == 0: # sending to cr
                    self.state = 1
                elif self.state == 1: # taking it back before the scr archive it
                    self.state =0
        elif self.reg == 'mat': #Minuta is different for sender and the rest
            if self.sender == user: # Here is the sender starting to send the note
                if cancel:
                    self.state = 0
                    self.read_by = ''
                elif self.received_by == '' and self.state == 0:
                    self.state = 6
                    toggle_share_permissions(self.folder_path,'viewer')
                elif self.state == 0:
                    self.state = 1
                elif self.state == 1:
                    self.state = 0
                elif self.state == 5:
                    self.state = 6
                    toggle_share_permissions(self.folder_path,'viewer')
                elif self.state == 6:
                    toggle_share_permissions(self.folder_path,'editor')
                    if self.received_by == '':
                        self.state = 0
                    else:
                        self.state = 5
            else: # Here is other user
                if cancel:
                    self.state = 0
                else:
                    self.updateRead(user)
                    if self.received_by == self.read_by:
                        self.state = 5
                    else:
                        self.state = 1
        else: # Here the states could be 4-6
            if self.flow == 'in': # Notes from cg,asr,r,ctr. They could be 5 or 6
                self.state = 6 if self.state == 5 else 5
            else: # Is out. Only to pass from 0 to 1
                if self.state == 0:
                    self.state = 1
                elif self.state == 1:
                    self.state = 0
 
        db.session.commit()

    