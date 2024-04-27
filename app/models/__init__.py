#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import re

from flask import current_app
from flask_login import UserMixin

from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, column_property
from sqlalchemy import select, delete, func, case, union, and_, or_
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from app import db

from .properties.file import FileProp
from .nas.file import FileNas

from .properties.note import NoteProp
from .html.note import NoteHtml
from .html.file import FileHtml
from .nas.note import NoteNas

from .properties.user import UserProp

def get_note_fk(fullkey):
    sender = aliased(User,name="sender_user")
    nt = db.session.scalar(select(Note).join(Note.sender.of_type(sender)).where(Note.fullkey==fullkey))
    return nt if nt else None

def get_ref(ref):
    rst = re.compile(r'h104\D+|\D+').findall(ref)
    nums = re.compile(r'\d+').findall(ref)
    if not nums or not rst:
        return None
    
    fk = None
    if rst == ['/'] or rst[0].replace(' ','') in ['','cg']: # Note in from cg
        if len(nums) == 2:
            fk = f"cg {nums[0]}/{nums[1]}"
    elif len(rst) == 2 and len(nums) == 2:
        if rst[1] == '/': # Otherwise there is not rf vc- vcr- -vc -vcr
            if rst[0][:3] == 'vcr':
                fk = f"vcr {nums[0]}/{nums[1]}"
            elif rst[0][:2] in ['vc','dg','cc']: # Is note out from vc or vcr
                fk = f"{rst[0][2]} {nums[0]}/{nums[1]}"
            elif rst[0][:4] == 'desr':
                fk = f"desr {nums[0]}/{nums[1]}"
            elif rst[0][:2] == 'cr' or rst[0][:3] == 'Aes': # Is note out
                if int(nums[0]) < 250: # Note to cg
                    fk = f"Aes {nums[0]}/{nums[1]}"
                elif int(nums[0]) < 1000: # Note to asr
                    fk = f"cr-asr {nums[0]}/{nums[1]}"
                elif int(nums[0]) < 2000: # Note to ctr
                    fk = f"cr {nums[0]}/{nums[1]}"
                else: # Note to cg
                    fk = f"Aes-r {nums[0]}/{nums[1]}"
            else: # is note in
                alias = rst[0].strip() if rst[0].strip().lower() == 'tokyo-sg' else rst[0].split('-')[0].strip()
                user = db.session.scalar(select(User).where(User.alias==alias))
                if user:
                    fk = f"{user.alias} {nums[0]}/{nums[1]}"
    
    if fk:
        return get_note_fk(fk)
    else:
        return None

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
        ids = []
        if ";" in self.subject:
            subject = self.subject.split(";")
            if len(subject) < 3:
                return ""
            
            for ref in subject[2].split(","):
                tid = get_ref(ref)
                if tid: ids.append([tid.fullkey,tid.id])

        return ids



class Comment(db.Model):
    __tablename__: 'comment'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    note_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('note.id'))
    note: Mapped["Note"] = relationship(back_populates="comments_ctr")
    sender_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('user.id'))
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
    
    n_date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    content: Mapped[str] = mapped_column(db.Text, default = '')
    content_jp: Mapped[str] = mapped_column(db.Text, default = '')
    proc: Mapped[int] = mapped_column(db.String(50), default = '')
    ref: Mapped[list["Note"]] = relationship('Note', secondary=note_ref, primaryjoin=note_ref.c.note_id==id, secondaryjoin=note_ref.c.ref_id==id, backref='notes') 
    path: Mapped[str] = mapped_column(db.String(150), default = '')
    permanent_link: Mapped[str] = mapped_column(db.String(150), default = '')
    comments: Mapped[str] = mapped_column(db.Text, default = '')
    
    is_ref: Mapped[bool] = mapped_column(db.Boolean, default=False)
    permanent: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    reg: Mapped[str] = mapped_column(db.String(15), default = '')
    register_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('register.id'), default=1)
    register: Mapped["Register"] = relationship(back_populates="notes")



    n_groups: Mapped[str] = mapped_column(db.String(15), default = '')

    done: Mapped[bool] = mapped_column(db.Boolean, default=False)
    state: Mapped[int] = mapped_column(db.Integer, default = 0)
    received_by: Mapped[str] = mapped_column(db.String(150), default = '', nullable=True)
    read_by: Mapped[str] = mapped_column(db.String(150), default = '')

    files: Mapped[list["File"]] = relationship(back_populates="note")
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
      


        if self.reg in ['vc','vcr','dg','cc','desr']:
            if 'cr' in self.sender.groups:
                self.path = f"/team-folders/Mail {self.reg}/Register/{self.year}/{self.reg} out"
            else:
                self.path = f"/team-folders/Mail {self.reg}/Register/{self.year}/{self.reg} in"
        elif self.sender.alias in ['cg','asr'] or 'r' in self.sender.groups:
            self.path = f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Notes/{self.year}/{self.reg} in"
        elif self.reg == 'min':
            self.path = f"{current_app.config['SYNOLOGY_FOLDER_NOTES']}/Minutas/{datetime.now().year}/{alias}"
        elif 'ctr' in self.sender.groups: # Note created by a ctr
            self.path = f"/team-folders/Mailbox {alias}/{alias} to cr"
        else: # Note create by dr/of cr
            self.path = f"/team-folders/Mail {alias}/Outbox"

        rst = self.create_folder()

    def __repr__(self):
        return f'<{self.fullkey_short} "{self.content}">'

    def __str__(self):
         return self.fullkey_short

    def __eq__(self,other):
        if isinstance(other,Note):
            if self.fullkey == other.fullkey:
                return True

        return False

    def deleteFiles(self,files_id):
        db.session.execute(delete(File).where(File.id.in_(files_id)))

    def addFileArgs(self,*args,**kargs):
        self.addFile(File(**kargs))

    def is_involve(self,user,reg):
        rg = reg.split("_")
        if rg[0] == 'des':
            return True
        elif rg[0] == 'cl' and len(rg) == 3:
            check = db.session.scalar(select(User).where(User.alias==rg[2]))
        else:
            check = user
        
        return check in self.receiver
    
    def potential_receivers(self,filter,possibles = []):
        fn = []
        fn.append(User.active==1)
        if filter:
            fts = re.findall(r'\w+',filter)
            ftn = []
            for ft in fts:
                #ftn.append(or_(func.lower(User.alias).contains(func.lower(ft)),func.lower(User.name).contains(func.lower(ft)),func.lower(User.description).contains(func.lower(ft))))
                #ftn.append(or_(User.alias.regexp_match(fr'\b{ft}\b'),User.description.regexp_match(fr'\b{ft}\b')))
                ftn.append(or_(func.lower(User.alias).contains(func.lower(ft)),User.description.regexp_match(fr'\b{ft}\b')))
            fn.append(and_(*ftn))
        
        recs = []
        if self.reg == 'min':
            fn.append(User.u_groups.regexp_match(r'\bcr\b'))
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.order.desc())).all()]
            firsts = []
            for pot in possibles:
                for rc in recs:
                    if rc[0] == pot:
                        firsts.append(rc)

            for ft in firsts:
                recs.remove(ft)

            recs = firsts + recs
        if self.flow == 'in' and self.reg in ['cg','asr','ctr','r']:
            fn.append(User.u_groups.regexp_match(r'\bcr\b'))
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
        elif self.flow == 'out' and self.reg in ['ctr','r']:
            fn.append(User.u_groups.regexp_match(fr'\b{self.reg}\b'))
            recs = [(user.alias,f"{user.alias} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
        elif self.flow == 'out' and self.reg in ['vc','vcr']:
            fn.append(User.u_groups.regexp_match(r'\bcg\b'))
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
            fn.pop()
            fn.append(User.u_groups.regexp_match(r'\bvc-r\b'))
            recs += [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
    
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
    
    active: Mapped[str] = mapped_column(db.Boolean, default=True)
    admin_active: Mapped[str] = mapped_column(db.Boolean, default=False)

    outbox: Mapped[list["Note"]] = relationship(back_populates="sender")

    def __repr__(self):
        return self.alias
    
    def __lt__(self,other):
        return self.order < other.order

    def __gt__(self,other):
        return self.order > other.order

class Register(db.Model):
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
