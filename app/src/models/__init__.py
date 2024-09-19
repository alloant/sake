#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import re

from flask import current_app, session
from flask_login import UserMixin, current_user

from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, column_property
from sqlalchemy import select, delete, func, case, union, and_, or_, not_
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.sql import text

from app import db

from .properties.file import FileProp
from .nas.file import FileNas

from .properties.note import NoteProp
from .html.note import NoteHtml
from .html.file import FileHtml
from .nas.note import NoteNas
from .html.register import RegisterHtml

from .properties.user import UserProp

def get_register(prot):
    registers = db.session.scalars(select(Register).where(Register.active==1))
    prot = re.sub(r'\d+\/\d+','',prot)
    prot = prot.strip('- ')

    for reg in registers:
        alias = r"^\D+"
        if re.match( eval(f"f'{reg.in_pattern}'"),prot): # Could note IN
            alias = ""

            senders = db.session.scalars(select(User).where(and_( User.u_groups.regexp_match(f'\\bct_{reg.alias}\\b') ))).all()
            
            if len(senders) == 1:
                sender = senders[0]
            else:
                rst = re.sub( eval(f"f'{reg.in_pattern}'"),'',prot)
                sender = db.session.scalar(select(User).where(and_(User.alias==rst,User.u_groups.regexp_match(f'\\bct_{reg.alias}\\b') )))
            
            if sender:
                return {'reg':reg,'sender':sender,'flow':'in'}

        
        alias = r"\D+$"
        if re.match( eval(f"f'{reg.out_pattern}'"),prot): # Could note OUT
            return {'reg':reg,'flow':'out'}


def get_filter_fullkey(prot):
    reg = get_register(prot)
    nums = re.findall(r'\d+',prot)
    
    if reg and len(nums) == 2:
        fn = []
        fn.append(Note.register==reg['reg'])
        if reg['reg'].alias != 'mat':
            fn.append(Note.flow==reg['flow'])

        if 'sender' in reg:
            fn.append(Note.sender==reg['sender'])

        fn.append(Note.num==int(nums[0]))
        fn.append(Note.year==2000+int(nums[1]))
        
        return and_(*fn)
    
    return None

def get_note_fullkey(prot):
    return db.session.scalar( select(Note).where(get_filter_fullkey(prot)) )


class File(FileProp,FileNas,FileHtml,db.Model):
    __tablename__ = 'file'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    subject: Mapped[str] = mapped_column(db.String(150), default = '')
    path: Mapped[str] = mapped_column(db.String(150), default = '')
    permanent_link: Mapped[str] = mapped_column(db.String(150), default = '')
    sender: Mapped[str] = mapped_column(db.String(20), default = '')
    note_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('note.id'),nullable=True)
    
    note: Mapped["Note"] = relationship(back_populates="files")
   

    def __repr__(self):
        return f'<File "{self.name}">'

    def __str__(self):
        return self.name

    def get_user(self,field,value = None):
        if field == 'email':
            return db.session.scalar(select(User).where(User.email==self.sender))
        elif field == 'alias':
            return db.session.scalar(select(User).where(User.alias==value))
        else:
            return None

    @property
    def guess_ref(self):
        refs = []
        if ";" in self.subject:
            subject = self.subject.split(";")
            if len(subject) == 3:
                for ref in subject[2].split(","):
                    tid = get_note_fullkey(ref)
                    if tid: 
                        refs.append(tid)
        return refs


class Comment(db.Model):
    __tablename__: 'comment'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    note_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('note.id'))
    note: Mapped["Note"] = relationship(back_populates="comments_ctr")
    sender_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('user.id'))
    sender: Mapped["User"] = relationship()
    comment: Mapped[str] = mapped_column(db.Text, default = '')
    


note_ref = db.Table('note_ref',
                db.Column('note_id', db.Integer, db.ForeignKey('note.id')),
                db.Column('ref_id', db.Integer, db.ForeignKey('note.id'))
                )

note_receiver = db.Table('note_receiver',
                db.Column('note_id', db.Integer, db.ForeignKey('note.id')),
                db.Column('receiver_id', db.Integer, db.ForeignKey('user.id')),
                )


class Note(NoteProp,NoteHtml,NoteNas,db.Model):
    __tablename__ = 'note'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    num: Mapped[int] = mapped_column(db.Integer, default = 0)
    year: Mapped[int] = mapped_column(db.Integer, default = datetime.utcnow().year)
    
    sender_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('user.id'))
    sender: Mapped["User"] = relationship(back_populates="outbox")

    receiver: Mapped[list["User"]] = relationship('User', secondary=note_receiver, backref='rec_notes')

    status: Mapped[list["NoteStatus"]] = relationship(back_populates="note", order_by="NoteStatus.target_order")

    n_date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    content: Mapped[str] = mapped_column(db.Text, default = '')
    content_jp: Mapped[str] = mapped_column(db.Text, default = '')
    proc: Mapped[int] = mapped_column(db.String(50), default = '')
    ref: Mapped[list["Note"]] = relationship('Note', secondary=note_ref, primaryjoin=note_ref.c.note_id==id, secondaryjoin=note_ref.c.ref_id==id, backref='notes', order_by="desc(Note.n_date)") 
    path: Mapped[str] = mapped_column(db.String(150), default = '')
    permanent_link: Mapped[str] = mapped_column(db.String(150), default = '')
    comments: Mapped[str] = mapped_column(db.Text, default = '')
    
    is_ref: Mapped[bool] = mapped_column(db.Boolean, default=False)
    permanent: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    reg: Mapped[str] = mapped_column(db.String(15), default = '')
    register_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('register.id'), default=1)
    register: Mapped["Register"] = relationship(back_populates="notes")

    n_tags: Mapped[str] = mapped_column(db.String(500), default = '')
    n_groups: Mapped[str] = mapped_column(db.String(50), default = '')

    done: Mapped[bool] = mapped_column(db.Boolean, default=False)
    state: Mapped[int] = mapped_column(db.Integer, default = 0)
    received_by: Mapped[str] = mapped_column(db.String(500), default = '', nullable=True)
    read_by: Mapped[str] = mapped_column(db.String(500), default = '')
    
    privileges: Mapped[str] = mapped_column(db.String(500), default = '', nullable=True)

    files: Mapped[list["File"]] = relationship(back_populates="note", order_by="File.files_order,File.path")
    comments_ctr: Mapped[list["Comment"]] = relationship(back_populates="note")
    

    files_date = column_property(
        select(func.max(File.date)).
        where(File.note_id==id).
        correlate_except(File).
        scalar_subquery()
    )

    def __init__(self, *args, **kwargs):
        super(Note,self).__init__(*args, **kwargs)
        self.sender = db.session.scalar(select(User).where(User.id==self.sender_id))  
        self.year = datetime.utcnow().year 
        alias = self.sender.alias
        flow = 'out' if 'cr' in self.sender.groups else 'in'
        
        if 'personal' in self.register.groups:
            self.path = f"/team-folders/Mail {self.register.alias}/Register/{self.year}/{self.register.alias} {flow}"
        elif 'matters' in self.register.groups: # Is matters
            self.path = f"/team-folders/Mail {alias}/Matters/{self.year}"
            self.proc = "Ordinario"
        elif 'ctr' in self.sender.groups: # A note to cr created in a ctr. The sender is a ctr.
            self.path = f"/team-folders/Mailbox {alias}/{alias} to cr"
        elif flow == 'out': # a dr from cr writing a note out
            self.path = f"/team-folders/Mail {alias}/Outbox/"
        else: # Note in from cg, asr or r
            self.path = f"{self.register.folder}/{self.year}/{self.register.alias} in"

        rst = self.create_folder()

    def __repr__(self):
        return f'<{self.fullkey_short} "{self.content}">'

    def __str__(self):
         return self.fullkey_short

    def __eq__(self,other):
        if isinstance(other,Note):
            if self.num == other.num and self.year == other.year and self.register == other.register:
                return True

        return False

    def current_status(self,user=current_user):
        return db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==self.id,NoteStatus.user_id==user.id))

    def toggle_status_attr(self,attr):
        rst = self.current_status()
        if not rst:
            status = NoteStatus(note_id=self.id,user_id=current_user.id)
            setattr(status,attr,True)
            db.session.add(status)
        else:
            setattr(rst,attr,not getattr(rst,attr))
        
        db.session.commit()
        
    def deleteFiles(self,files_id):
        db.session.execute(delete(File).where(File.id.in_(files_id)))

    def addFileArgs(self,*args,**kargs):
        self.addFile(File(**kargs))
    
    @hybrid_method
    def result(self,demand,user=current_user):
        match demand:
            case 'is_sign_despacho':
                return self.contains_in('read_by',f'des_{current_user.alias}')
                #NEW
                rst = self.current_status(user)
                if rst:
                    return rst.sign_despacho
                return False
            case 'is_target':
                rst = self.current_status(user)
                if rst:
                    return rst.target
                return False
            case 'is_read':
                if self.n_date < current_user.date:
                    toggle = lambda x: not x
                else:
                    toggle = lambda x: x

                rst = self.current_status(user)
                if rst and rst.read:
                    return toggle(True)

                return toggle(False)
            case 'num_sign_despacho':
                return self.state - 3
                #NEW return db.session.scalars(select(func.count(NoteStatus)).where(NoteStatus.note_id==self.id,NoteStatus.sign_despacho))

    @result.expression
    def result(cls,demand,user=current_user):
        match demand:
            case 'is_sign_despacho':
                return cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==user.id,NoteStatus.sign_despacho)
            case 'is_target':
                return cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==user.id,NoteStatus.target)
            case 'is_read':
                return case(
                    (cls.n_date < user.date,not_(cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==user.id,NoteStatus.read))),
                    else_=cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==user.id,NoteStatus.read)
                )
            case 'num_sign_despacho':
                return func.count(cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==user.id,NoteStatus.sign_despacho))


    @hybrid_method
    def is_read_new(self,user=current_user):
        if self.n_date < current_user.date:
            toggle = lambda x: not x
        else:
            toggle = lambda x: x
        
        rst = self.current_status()
        if rst and rst.read:
            return toggle(True)
        
        return toggle(False)
            
    @is_read_new.expression
    def is_read_new(cls,user=current_user):
        return case(
            (cls.n_date < current_user.date,not_(cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==current_user.id,NoteStatus.read))),
            else_=cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==current_user.id,NoteStatus.read)
        )
        return cls.status.any(NotesStatus.note_id==self.id,NoteStatus.user_id==current_user.id,NoteStatus.read)

    #NEW
    @hybrid_method
    def is_read(self,user=current_user):
        if isinstance(user,str): # This is a ctr or des
            alias = user if user[:4] == 'des_' else user.split('_')[2]
            return alias in self.read_by.split(",")

        if 'of' in user.groups:
            if not user in self.receiver and not user.alias in self.privileges.split(','):
                return True

        if user.date > self.n_date:
            return not user.alias in self.read_by.split(",")
        else:
            return user.alias in self.read_by.split(",")
    #NEW
    @is_read.expression
    def is_read(cls,user=current_user):
        if isinstance(user,User):
            if 'of' in user.groups:
                return case (
                    (not_(or_(cls.receiver.any(User.id==user.id),cls.privileges.regexp_match(fr'(^|[^-])\b{user.alias}\b($|[^-])'))),True),
                    (user.date > cls.n_date,not_(cls.read_by.regexp_match( fr'(^|[^-])\b{user.alias}\b($|[^-])' )) ),
                    else_=cls.read_by.regexp_match( fr'(^|[^-])\b{user.alias}\b($|[^-])' )
                )
            else:
                return case (
                    (user.date > cls.n_date,not_(cls.read_by.regexp_match( fr'(^|[^-])\b{user.alias}\b($|[^-])' )) ),
                    else_=cls.read_by.regexp_match( fr'(^|[^-])\b{user.alias}\b($|[^-])' )
                )
        else:
            alias = user if user[:4] == 'des_' else user.split('_')[2]
            return cls.read_by.regexp_match( fr'(^|[^-])\b{alias}\b($|[^-])' )


    def is_involve(self,reg,user):
        if reg[0] == 'des':
            return True
        elif reg[2]: # It is from a subregister
            check = db.session.scalar(select(User).where(User.alias==reg[2]))
        else:
            check = user
       
        if self.reg == 'mat':
            return check.alias in self.received_by.replace('|',',').split(',')
        else:
            return check in self.receiver
    
    def potential_receivers(self,filter,possibles = [],only_of = False):
        fn = []
        fn.append(User.active==1)
        if filter:
            fts = re.findall(r'\w+',filter)
            ftn = []
            for ft in fts:
                ftn.append(or_(func.lower(User.alias).contains(func.lower(ft)),User.description.regexp_match(fr'\b{ft}\b')))
            fn.append(and_(*ftn))
        if only_of:
            fn.append(User.u_groups.regexp_match(fr'\bof\b'))
        
        recs = []

        if self.register.alias == 'mat':
            fn.append(User.contains_group('cr'))
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.order.desc())).all() if user.alias != self.sender.alias]
            firsts = []
            for pot in possibles:
                for rc in recs:
                    if rc[0] == pot:
                        firsts.append(rc)

            for ft in firsts:
                recs.remove(ft)

            return firsts + recs
        
        if self.flow == 'in' or only_of:
            if self.register.alias in ['vc','vcr']:
                fn.append(User.u_groups.regexp_match(fr'\bcr\b'))
            else:
                fn.append(User.u_groups.regexp_match(fr'\b[evo]_{self.register.alias}\b'))
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
        else:
            fn.append(User.u_groups.regexp_match(fr'\bct_{self.register.alias}\b'))
            recs = [(user.alias,f"{user.alias} - {user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
 
        return recs

    @hybrid_property
    def alias_sender(self):
        return self.sender.alias

    @alias_sender.expression
    def alias_sender(cls):
        alsend = db.session.scalar(select(User.alias).where(User.id==cls.sender_id))
        return alsend
        return select(User.alias).where(User.id==cls.sender_id)
   
    @hybrid_property
    def date(self):
        rst = self.n_date
        for file in self.files:
            if rst < file.date:
                rst = file.date
        return rst

    @date.expression
    def date(cls): 
        return case(
            (and_(cls.n_date < cls.files_date,cls.files_date.isnot(None)), cls.files_date),
            else_=cls.n_date
        )

    @hybrid_property
    def flow(self) -> str:
        return 'out' if any(map(lambda v: v in self.sender.groups, ['sake'])) else 'in'

    @flow.expression
    def flow(cls):
        cr_users = [user.id for user in db.session.scalars( select(User).where(User.u_groups.regexp_match(r'\bsake\b')) ).all()]
        return case(
            (cls.sender_id.in_(cr_users),'out'),
            else_='in'
        )
    
    @property
    def history_notes(self):
        refs = [self.id]
        for ref in self.ref:
            refs.append(ref.id)

        notes = ",".join([str(r) for r in refs])
        
        sql = text(
                f"with recursive R as ( \
                select note_id as n, ref_id as r from note_ref where note_id in ({notes}) or ref_id in ({notes}) \
                UNION \
                select note_ref.note_id,note_ref.ref_id from R,note_ref where note_ref.note_id = R.r or note_ref.ref_id in (R.n,R.r) or note_ref.note_id in (R.n,R.r)\
                ) \
                select n,r from R"
            )

        d_nids = db.session.execute(sql).all()

        nids = [self.id]
        for nid in d_nids:
            nids += nid

        nids = list(set(nids))

        return db.session.scalars( select(Note).where(Note.id.in_(nids)).order_by(Note.date.desc(), Note.id.desc()) ).all()


class User(UserProp,UserMixin, db.Model):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    password: Mapped[str] = mapped_column(db.String(500), default='')
    password_nas: Mapped[str] = mapped_column(db.String(500), default='')

    date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    name: Mapped[str] = mapped_column(db.String(200), default='')
    alias: Mapped[str] = mapped_column(db.String(20), unique=True)
    u_groups: Mapped[str] = mapped_column(db.String(200), default=False)
    order: Mapped[str] = mapped_column(db.Integer, default=0)

    email: Mapped[str] = mapped_column(db.String(200), default='')
    description: Mapped[str] = mapped_column(db.String(200), default='')
    
    local_path: Mapped[str] = mapped_column(db.String(200), default='')
    
    status: Mapped[list["NoteStatus"]] = relationship(back_populates="user")
    
    active: Mapped[str] = mapped_column(db.Boolean, default=True)
    admin_active: Mapped[str] = mapped_column(db.Boolean, default=False)

    outbox: Mapped[list["Note"]] = relationship(back_populates="sender")

    def __repr__(self):
        return self.alias
    
    def __lt__(self,other):
        return self.order < other.order

    def __gt__(self,other):
        return self.order > other.order

    @property
    def all_registers(self):
        rst = []
        registers = db.session.scalars(select(Register).where(Register.active==1)).all()
        for register in registers:
            if register.permissions != 'notallowed':
                rst.append(register)

        return rst
   
    @property
    def all_registers_and_sub(self):
        rst = []
        registers = db.session.scalars(select(Register).where(Register.active==1)).all()
        for register in registers:
            if register.permissions != 'notallowed' or 'subregister' in register.groups:
                rst.append(register)

        return rst
 
    @property
    def has_pendings(self):
        pendings = db.session.scalars(select(Note).where(and_(not_(Note.register.has(Register.alias=='mat')),Note.receiver.any(User.id==current_user.id),Note.state<6,Note.state>4)))
        for note in pendings:
            if not note.is_read(current_user):
                return True

        return False
    
    @property
    def pendings_html(self):
        rst = self.pendings
        if rst > 0:
            return str(rst)
        return ""
   
    @property
    def unread_html(self):
        rst = self.unread
        if rst > 0:
            return str(rst)
        return ""
 
    @property
    def despacho_html(self):
        rst = self.despacho
        if rst > 0:
            return str(rst)
        return ""

    @property
    def pendings_matters_html(self):
        rst = self.pending_matters
        if rst > 0:
            return str(rst)
        return ""

    def data(self,info,html=False):
        rst = 0
        if info == "pending":
            rst = current_user.pending_matters + current_user.pendings
        elif info == "proposals":
            rst = current_user.pending_matters
        elif info == "unread":
            rst = current_user.unread
        elif info == 'despacho':
            rst = current_user.despacho
        elif info == 'inbox':
            rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg!='mat',Note.flow=='in',Note.state==1))
        elif info == 'outbox':
            rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg!='mat',Note.flow=='out',Note.state==1))
        elif info == 'register':
            if 'permanente' in current_user.groups:
                rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg!='mat',Note.flow=='in',Note.register.has(Register.permissions!='notallowed'),not_(Note.is_read(current_user))))
            else:
                rst = db.session.scalar(select(func.count(Note.id)).where(not_(Note.permanent),Note.reg!='mat',Note.flow=='in',Note.register.has(Register.permissions!='notallowed'),not_(Note.is_read(current_user))))
                rst += db.session.scalar(select(func.count(Note.id)).where(not_(Note.permanent),Note.reg=='ctr',Note.flow=='out',Note.register.has(Register.permissions!='notallowed'),not_(Note.is_read(current_user))))
            rst = current_user.unread
        elif '_' in info:
            reg = info.split('_')
            register = db.session.scalar(select(Register).where(Register.alias==reg[0]))
            if reg[2]:
                rst = register.unread(reg[2])
                #rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg==reg[0],Note.flow=='out',Note.register.has(Register.permissions!='notallowed'),not_(Note.is_read(current_user)),Note.receiver.any()))
            else:
                rst = register.unread()
        if html:
            rst = str(rst) if rst > 0 else ""

        return rst

    @property
    def pendings(self):
        return db.session.scalar(select(func.count(Note.id)).where(not_(Note.is_read(current_user)),Note.register.has(Register.alias!='mat'),Note.receiver.any(User.id==current_user.id),Note.state<6,Note.state>4))

    @property
    def despacho(self):
        return db.session.scalar(select(func.count(Note.id)).where(not_(Note.is_read(f'des_{current_user.alias}')),Note.register.has(Register.contains_group('despacho')),Note.state<5,Note.state>2))


    @property
    def unread(self):
        cont = 0
        registers = db.session.scalars(select(Register).where(and_(Register.active==1,Register.permissions=='allowed'))).all()
        for register in registers:
            for sb in register.get_subregisters():
                cont += db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id==register.id,Note.flow=='out',Note.receiver.any(User.alias==sb),not_(Note.is_read(current_user)))))

        if 'permanent' in current_user.groups:
            cont += db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id.in_([reg.id for reg in registers]),Note.flow=='in',not_(Note.is_read(current_user)))))
        else:
            cont += db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.permanent==False,Note.register_id.in_([reg.id for reg in registers]),Note.flow=='in',not_(Note.is_read(current_user)))))
        
        return cont

    @property
    def pending_matters(self):
        return db.session.scalar(select(func.count(Note.id)).where(Note.register.has(Register.alias=='mat'),Note.receiver.any(User.id==current_user.id),Note.state==1,Note.next_in_matters(current_user.alias)))


class NoteStatus(db.Model):
    __tablename__ = 'notestatus'
    note_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("note.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("user.id"), primary_key=True)

    note: Mapped["Note"] = relationship(back_populates="status")
    user: Mapped["User"] = relationship(back_populates="status")

    read: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    target: Mapped[bool] = mapped_column(db.Boolean, default=False)
    target_order: Mapped[int] = mapped_column(db.Integer, default=0)
    target_acted: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    sign_despacho: Mapped[bool] = mapped_column(db.Boolean, default=False)

    comment: Mapped[str] = mapped_column(db.String(500), default='')

class Register(RegisterHtml,db.Model):
    __tablename__ = 'register'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    
    name: Mapped[str] = mapped_column(db.String(200), default='')
    alias: Mapped[str] = mapped_column(db.String(20), unique=True)
    
    r_groups: Mapped[str] = mapped_column(db.String(200), default=False)
    
    in_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    out_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    #protocol_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    folder: Mapped[str] = mapped_column(db.String(200), default='')

    active: Mapped[str] = mapped_column(db.Boolean, default=True)
    
    notes: Mapped[list["Note"]] = relationship(back_populates="register")

    def __repr__(self):
        return f"{self.name} ({self.alias})"

    @hybrid_method
    def contains_group(cls,group):
        return cls.r_groups.regexp_match(fr'(^|[^-])\b{group}\b($|[^-])')

    @property
    def groups(self):
        return [g.strip() for g in self.r_groups.split(",")]
    
    @hybrid_property
    def permissions(self): # it is only for full register not subregister
        #rst = re.search(fr'\b[evo]_{self.alias}_*[a-z,0-9]*\b',user.u_groups)
        rst = re.search(fr'\b[evo]_{self.alias}\b',current_user.u_groups)

        if not rst:
            return 'notallowed'
         
        rst = rst.group().split('_')
        
        if rst[0] == 'e':
            return 'editor'
        elif rst[0] == 'v':
            return 'viewer'
        elif rst[0] == 'o':
            return 'official'
        else:
            return 'notallowed'
    
    @permissions.expression
    def permissions(cls):
        rst = re.findall(fr'\b[evo]_[A-Za-z]*\b',current_user.u_groups)
        registers = [r.split('_')[1] for r in rst]
        
        return case(
            (cls.alias.in_(registers),'allowed'),
            else_='notallowed'
        )

    def get_subregisters(self,ids=False):
        rst = re.findall(fr'\b[evo]_{self.alias}_[A-Za-z0-9-]+\b',current_user.u_groups)

        sbs = []
        for sb in rst:
            if ids:
                usb = db.session.scalar(select(User).where(User.alias==sb.split('_')[2]))
                if usb:
                    sbs.append([usb.id,sb.split('_')[2]])
            else:
                sbs.append(sb.split('_')[2])

        return sbs

    def get_contacts(self):
        return db.session.scalars(select(User).where(User.u_groups.regexp_match(fr'\bcr\b'))).all()
 
    @property
    def get_num_contacts(self):
        return len(db.session.scalars(select(User).where(User.u_groups.regexp_match(fr'\bct_{self.alias}\b'))).all())

    def unread(self,sb=""):
        if sb:
            return db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id==self.id,Note.flow=='out',Note.receiver.any(User.alias==sb),not_(Note.is_read(current_user)))))
        else:
            if 'permanent' in current_user.groups:
                return db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id==self.id,Note.flow=='in',not_(Note.is_read(current_user)))))
        
            return db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.permanent==False,Note.register_id==self.id,Note.flow=='in',not_(Note.is_read(current_user)))))

