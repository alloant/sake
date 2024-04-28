from datetime import date

from flask import flash, session, current_app

from sqlalchemy import case, and_, or_, not_, select, type_coerce, literal_column, func, union
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from app import db

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
    def receivers(self):
        return ",".join([rec.alias for rec in self.receiver])

    @property
    def refs(self):
        return ",".join([ref.fullkey_short for ref in self.ref])

    @hybrid_property
    def fullkey_short(self):
        return self.fullkey_ls(long_key=False) 
    
    @hybrid_property
    def fullkey(self):
        return self.fullkey_ls()

    def fullkey_ls(self,long_key = True):
        if self.flow == 'in':
            alias = self.sender.alias
            pattern = self.register.in_pattern.split('|')[-1].strip(' ^$')
            #if pattern == '': # Only for cg, because the short version is none we use the other
            #    pattern = self.register.in_pattern.split('|')[0].strip(' ^$')
        else:
            if len(self.receiver) == 1 and long_key :
                alias = self.receiver[0].alias
                pattern = self.register.out_pattern.split('|')[0].strip(' ^$')
            else:
                alias = ""
                pattern = self.register.out_pattern.split('|')[-1].strip(' ^$')

        prot = eval(fr"f'{pattern}'")
        
        return f"{prot} {self.num}/{self.year-2000}"


    @property
    def can_edit(self):
        return True if self.sender == current_user and self.state < 2 else False

    @fullkey.expression
    def fullkey(cls):
        """
        return case(
            (and_(cls.flow=='in',cls.reg == 'vcr'), literal_column("sender_user.alias") + "-vcr " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.flow=='in', cls.alias_sender + " " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "cg", "Aes " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "asr", "cr-asr " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "ctr", "cr " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg.contains(","), "Aes-r " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            (cls.reg == "r", "Aes-r" + " " + cls.num.cast(db.String) + "/" + (cls.year % 100).cast(db.String)),
            else_="",
        )
        """
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
   
    @hybrid_property
    def flow(self) -> str:
        return 'out' if any(map(lambda v: v in self.sender.groups, ['cr'])) else 'in'

    @flow.expression
    def flow(cls):
        return case(
            (cls.sender_id.in_(session['cr']),'out'),
            else_='in'
        )
   
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
            (ctr['date'] < cls.n_date,not_(cls.received_by.regexp_match(fr'\b{ctr['alias']}\b')) ),
        else_=cls.received_by.regexp_match(fr'\b{ctr['alias']}\b')
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
            (user.date < cls.n_date,not_(cls.received_by.regexp_match(fr'\b{user.alias}\b')) ),
        else_=cls.received_by.regexp_match(fr'\b{user.alias}\b')
        )
        return not_(cls.received_by.regexp_match(fr'\b{alias}\b'))

    @property
    def folder_name(self):
        if self.num == 0: # Es una ref
            if self.ref:
                if self.ref[0]:
                    folder = self.ref[0].fullkey_short.split("/")[0]
            return None
        else: 
            folder = self.fullkey_short.split("/")[0]
        
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
        rg = reg.split('_')

        if rg[0] == 'cl':
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
        
        self.read_by = ",".join(rb)
        db.session.commit()
        return inc

    def updateState(self,reg,user):
        rg = reg.split("_")
        if rg[0] == 'box': # Is the scr getting mail from cg, asr, ctr or r
            pass
            # Here we move to Archive and if the move is succesful we put state 2
            #self.state = 2
        elif rg[0] == 'des': # Here states are only 2 or 3
            if self.reg in ['vcr','vc']:
                self.state = 5
            else:
                self.state += self.updateRead(f"des_{user.alias}")
        elif rg[0] == 'cl':
            if self.flow == 'out': # Note from cr to the ctr
                rst = self.received_by.split(",")
                if rg[2] in rst:
                    rst.remove(rg[2])
                else:
                    rst.append(rg[2])
                if not rst: rst = ""
                self.received_by = ",".join(rst)
            else:
                if self.state == 0: # sending to cr
                    self.state = 1
                elif self.state == 1: # taking it back before the scr archive it
                    self.state =0
        elif rg[0] in ['cr','pen','vc','vcr','dg','cc','desr']: # Here the states could be 4-6
            if self.flow == 'in': # Notes from cg,asr,r,ctr. They could be 5 or 6
                self.state = 6 if self.state == 5 else 5
            else: # Is out. Only to pass from 0 to 1
                if self.state == 0:
                    self.state = 1
                elif self.state == 1:
                    self.state = 0
        elif self.reg == 'min': #Minuta is different for sender and the rest
            if self.sender == user:
                if self.state == 0:
                    self.receiver.sort(reverse=True)
                    if len(self.receiver) > 0:
                        self.received_by = f"{self.receiver[0].alias}"
                    self.state = 4
                elif self.state == 4:
                    self.state = 0
                elif self.state == 2:
                    self.state = 6
            else:
                rb = self.read_by.split('_') if self.read_by != '' else []
                rb.append(user.alias)
                self.read_by = ",".join(rb)
                self.receiver.sort(reverse=True)
                has_next = False
                for rec in self.receiver:
                    if not rec.alias in rb:
                        self.received_by += f",{rec.alias}"
                        has_next = True
                        break
                
                if not has_next:
                    self.state = 2
        
        db.session.commit()
