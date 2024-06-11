from datetime import date

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

    @property
    def groups(self):
        return self.n_groups.split(',')
   
    @property
    def tags(self):
        return self.n_tags.split(',')

    @hybrid_method
    def next_in_matters(cls,user):
        return cls.received_by.regexp_match(func.concat('^',cls.read_by,fr',*{user.alias}.*') )

    @hybrid_method
    def contains_read(cls,alias):
        return cls.read_by.regexp_match(fr'(^|[^-])\b{alias}\b($|[^-])')
    
    @hybrid_method
    def contains_received_by(cls,alias):
        return cls.read_by.regexp_match(fr'(^|[^-])\b{alias}\b($|[^-])')

    @hybrid_method
    def contains_tag(cls,tag):
        return cls.n_tags.regexp_match(fr'(^|[^-])\b{tag}\b($|[^-])')
    
    @hybrid_method
    def contains_group(cls,group):
        return cls.n_groups.regexp_match(fr'(^|[^-])\b{group}\b($|[^-])')

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
            if len(self.receiver) == 0 and self.register.alias != 'mat' and not folder:
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

    
    def can_see(self): # This is use only for cr and of as the ctr is easier.
        if self.sender_id == current_user.id:
            return True
        elif 'matters' in self.register.groups:
            if self.state == 6 and (not self.permanent or 'permanent' in current_user.groups):
                return True
            elif self.state > 0 and self.next_in_matters():
                pass


    def can_edit(self,reg):
        if current_user.admin:
            return True
        elif reg[0] in ['box','des']:
            return True
        elif self.rel_flow(reg) == 'out' and self.state < 1: # because state is 0 only owner can see it
            return True
        elif self.register.permissions == 'editor':
            return True
        elif reg[0] == 'mat' and self.state < 1:
            return True

        return False

    """
    @fullkey.expression
    def fullkey(cls):


        rstin = f"-{cls.reg}" if cls.reg in ['vc','vcr','dg','cc','desr'] else ""
        return case(
            (cls.flow=='in', literal_column("sender_user.alias") + f"{rstin} " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "cg", "Aes " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "asr", "cr-asr " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "ctr", "cr " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg.contains(","), "Aes-r " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "r", "Aes-r" + " " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            else_=cls.reg + " " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String),
        )
    """
   
    @hybrid_method
    def ctr_has_done(self,ctr): #Use in state_cl and updateState for cl. We assume note is in for the ctr
        if ctr['alias'] in self.received_by.split(','):
            rst = True
        else:
            rst = False
        
        if ctr['date'] > self.n_date.strftime("%Y-%m-%d"):
        #if ctr['date'] > self.n_date:
            rst = not rst
        
        return rst 

    @ctr_has_done.expression
    def ctr_has_done(cls,ctr):
        return case (
            (ctr['date'] < cls.n_date,not_(cls.received_by.regexp_match( fr'(^|[^-])\b{alias}\b($|[^-])' )) ),
        else_=cls.received_by.regexp_match(fr'(^|[^-])\b{alias}\b($|[^-])')
        )

    @hybrid_property
    def matters_order(self):
        if self.state == 1 and self.sender != current_user:
            return 1
        elif self.state == 5 and self.sender == current_user:
            return 2
        elif self.state == 0:
            return 3
        elif self.state == 1 and self.sender == current_user:
            return 4
        elif self.state == 1:
            return 5
        else:
            return 6

    @matters_order.expression
    def matters_order(cls):
        return case (
            (and_(cls.state==5,cls.sender==current_user),1),
            (and_(cls.state==1,cls.sender!=current_user),1),
            (cls.state==0,3),
            (and_(cls.state==1,cls.sender==current_user),4),
            (cls.state==1,5),
            else_=6,
        )

    @hybrid_method
    def is_done(self,user): #Use in state_cl and updateState for cl. We assume note is in for the ctr
        if user.alias in self.received_by.split(','):
            rst = True
        else:
            rst = False
        
        if user.date > self.n_date:
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

    def is_read(self,user):
        if isinstance(user,str): # This is a ctr or des
            alias = user if user[:4] == 'des_' else user.split('_')[2]
            return alias in self.read_by.split(",")

        if user.date > self.n_date:
            return not user.alias in self.read_by.split(",")
        else:
            return user.alias in self.read_by.split(",")


    def rel_flow(self,reg):
        if reg[2]: # Is a subregister of a ctr
            return 'in' if self.flow == 'out' else 'out'
        else:
            return self.flow

    def updateRead(self,user):
        rb = self.read_by.split(',') if self.read_by else []
        alias = user if isinstance(user,str) else user.alias

        if alias in rb:
            rb.remove(alias)
            inc = -1
        else:
            rb.append(alias)
            inc = 1
        
        self.read_by = ",".join([r for r in rb if r])
        db.session.commit()
        return inc

    def updateState(self,reg,user,cancel=False):
        if reg[0] == 'box': # Is the scr getting mail from cg, asr, ctr or r
            if not 'personal' in self.register.groups: # Only for not personal calendars
                if self.move(f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{self.year}/{self.reg} out"):
                    if 'folder' in self.register.groups: # Note for asr. We just copy it to the right folder
                        self.copy(f"/team-folders/Mail {self.register.alias}/Mail to {self.register.alias}") # I have to add this to the register database!!!!! Pending
                        self.state = 6
                    
                    if 'sake' in self.register.groups: # note for a ctr (internal sake system). We just change the state.
                        self.state = 6
                        for rec in self.receiver:
                            if rec.email:
                                print('--',rec,rec.email)
                                try:
                                    send_email(f"New mail for {rec.alias}. {self.fullkey}","",rec.email)
                                except:
                                    flash(f"Could not send to {rec}")

            # Here we move to Archive and if the move is succesful we put state 2
            #self.state = 2
        elif reg[0] == 'des': # Here states are only 2 or 3
            if self.reg in ['vcr','vc']:
                self.state = 5
            else:
                self.state += self.updateRead(f"des_{user.alias}")
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
