#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, date
import re

from flask import current_app, session
from flask_login import UserMixin, current_user

from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, column_property
from sqlalchemy import select, delete, func, case, union, exists, literal_column, and_, or_, not_, any_
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
        #alias = r"^\D+"
        alias = r"[^0-9-]+"
        if re.fullmatch( eval(f"f'{reg.in_pattern}'"),prot): # Could note IN
            alias = ""

            senders = db.session.scalars(select(User).where(and_( User.u_groups.regexp_match(f'\\bct_{reg.alias}\\b') ))).all()
            
            if len(senders) == 1:
                sender = senders[0]
            else:
                rst = re.sub( eval(f"f'{reg.in_pattern}'"),'',prot)
                if 'personal' in reg.groups:
                    sender = db.session.scalar(select(User).where(User.alias==rst))
                else:
                    sender = db.session.scalar(select(User).where(and_(User.alias==rst,User.u_groups.regexp_match(f'\\bct_{reg.alias}\\b') )))
            
            if sender:
                return {'reg':reg,'sender':sender,'flow':'in'}

        
        #alias = r"\D+$"
        alias = r"[^0-9-]+$"
        if re.fullmatch( eval(f"f'{reg.out_pattern}'"),prot): # Could note OUT
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

    @hybrid_property
    def num_note(self):
        return self.note.num

    @num_note.expression
    def num_note(cls):
        return ( select(Note.num).where(Note.id==cls.note_id).scalar_subquery() )



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

#note_receiver = db.Table('note_receiver',
#                db.Column('note_id', db.Integer, db.ForeignKey('note.id')),
#                db.Column('receiver_id', db.Integer, db.ForeignKey('user.id')),
#                )

class Tag(db.Model):
    __tablename__= 'tag'
    
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    text: Mapped[str] = mapped_column(db.String(50), default = '')

note_tag = db.Table('note_tag',
                db.Column('note_id', db.Integer, db.ForeignKey('note.id')),
                db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
                )

class Note(NoteProp,NoteHtml,NoteNas,db.Model):
    __tablename__ = 'note'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    num: Mapped[int] = mapped_column(db.Integer, default = 0)
    year: Mapped[int] = mapped_column(db.Integer, default = datetime.utcnow().year)
    
    sender_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('user.id'))
    sender: Mapped["User"] = relationship(back_populates="outbox")

#    receiver: Mapped[list["User"]] = relationship('User', secondary=note_receiver, backref='rec_notes')

    tag: Mapped[list["Tag"]] = relationship('Tag', secondary=note_tag, primaryjoin=note_tag.c.note_id==id, secondaryjoin=note_tag.c.tag_id==id, order_by="desc(Tag.text)") 
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
        if isinstance(user,dict):
            return db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==self.id,NoteStatus.user.has(User.alias==user['alias'])))
        else:
            return db.session.scalar(select(NoteStatus).where(NoteStatus.note_id==self.id,NoteStatus.user_id==user.id))

    def actived_status(self):
        return db.session.scalars(select(NoteStatus).where(NoteStatus.target_order==self.current_target_order)).all()

    def toggle_status_attr(self,attr,user=current_user):
        rst = self.current_status(user)
        if not rst:
            status = NoteStatus(note_id=self.id,user_id=user.id)
            setattr(status,attr,True)
            db.session.add(status)
        else:
            setattr(rst,attr,not getattr(rst,attr))
        
        db.session.commit()
        
    def deleteFiles(self,files_id):
        db.session.execute(delete(File).where(File.id.in_(files_id)))

    def addFileArgs(self,*args,**kargs):
        self.addFile(File(**kargs))

    @property
    def receiver(self):
        return [state.user for state in self.status if state.target]

    @hybrid_method
    def has_target(self,user):
        return user in self.receiver

    @has_target.expression
    def has_target(cls, user):
        if isinstance(user,int):
            return exists().where(NoteStatus.note_id == cls.id, NoteStatus.user_id == user, NoteStatus.target)
        elif isinstance(user,int):
            if user.isdigit():
                return exists().where(NoteStatus.note_id == cls.id, NoteStatus.user_id == int(user), NoteStatus.target)
            else:
                user_db = db.scalar(select(User).where(User.alias==user))
                return exists().where(NoteStatus.note_id == cls.id, NoteStatus.user_id == user_db.id, NoteStatus.target)


        #return select(User).where(NoteStatus.note_id == cls.id, NoteStatus.user_id == User.id).label('receiver')


    @hybrid_method
    def target_working(self,user=current_user):
        order = 0
        for state in self.status:
            if state.target and state.target_acted == 0:
                order = state.target_order
            if state.user_id == user.id:
                if state.target_order == order:
                    return True
        
        return False

    @target_working.expression
    def target_working(cls,user=current_user):
        NS = aliased(NoteStatus)
        subquery = select(func.min(NS.target_order)).where(
                        NS.note_id==cls.id,
                        NS.target,
                        not_(NS.target_acted)
                    )

        note = aliased(Note,name="note_status")

        rst = select(NoteStatus).join(NoteStatus.note.of_type(note)).where(
                NoteStatus.note_id==cls.id,
                NoteStatus.user_id == user.id,
                literal_column(f"note_status.state > 0"),
                literal_column(f"note_status.reg = 'mat'"),
                NoteStatus.target,
                not_(NoteStatus.target_acted),
                NoteStatus.target_order == subquery.scalar_subquery()
        )

        return exists(rst)

        rst = exists().where(
                NoteStatus.note_id == cls.id,
                NoteStatus.user_id == user.id,
                cls.state>0,
                cls.reg=='mat',
                NoteStatus.target,
                not_(NoteStatus.target_acted),
                NoteStatus.target_order == subquery.scalar_subquery()
            )
        print(rst)
        return rst

    @hybrid_property
    def current_target_order(self):
        for state in self.status:
            if state.target and state.target_acted == 0:
                break
        return state.target_order

    @current_target_order.expression
    def current_target_order(cls):
        NS = aliased(NoteStatus)
        return select(func.min(NS.target_order)).where(
            NS.note_id==cls.id,
            NS.target,
            not_(NS.target_acted)
        ).label('current_target_order')

    @hybrid_method
    def result(self,demand,user=current_user):
        match demand:
            case 'is_sign_despacho':
                rst = self.current_status(user)
                if rst:
                    return rst.sign_despacho
                return False
            case 'is_target':
                rst = self.current_status(user)
                if rst:
                    return rst.target
                return False
            case 'is_current_target':
                if self.reg != 'mat':
                    return False

                rst = self.current_status(user)
                if rst:
                    if rst.target:
                        if rst.target_acted:
                            return False
                        elif self.current_target_order == rst.target_order:
                            return True
                return False
            case 'num_sign_proposal':
                return db.session.scalar(select(func.count(NoteStatus.user_id)).where(NoteStatus.note_id==self.id,NoteStatus.target_acted))
            case 'num_target':
                return db.session.scalar(select(func.count(NoteStatus.user_id)).where(NoteStatus.note_id==self.id,NoteStatus.target))
            case 'is_read':
                if self.n_date < user.date:
                    toggle = lambda x: not x
                else:
                    toggle = lambda x: x

                rst = self.current_status(user)
                if rst and rst.read:
                    return toggle(True)

                return toggle(False)
            case 'is_done':
                dt = date.fromisoformat(user['date']) if isinstance(user,dict) else user.date
                
                if self.n_date < dt:
                    toggle = lambda x: not x
                else:
                    toggle = lambda x: x
                
                alias = user['alias'] if isinstance(user,dict) else user.alias

                rst = self.current_status(user)
                if rst and rst.target_acted:
                    return toggle(True)

                return toggle(False)
            case 'num_sign_despacho':
                return db.session.scalar(select(func.count(NoteStatus.user_id)).where(NoteStatus.note_id==self.id,NoteStatus.sign_despacho))

    @result.expression
    def result(cls,demand,user=current_user):
        match demand:
            case 'is_sign_despacho':
                return cls.status.any(and_(NoteStatus.user_id==user.id,NoteStatus.sign_despacho))
            case 'is_target':
                return cls.status.any(and_(NoteStatus.user_id==user.id,NoteStatus.target))
            case 'target_order':
                return select(NoteStatus.target_order).where(NoteStatus.note_id==cls.id,NoteStatus.user_id==user.id).scalar_subquery()
            case 'is_done':
                return case(
                    (cls.n_date < user.date,not_(cls.status.any(and_(NoteStatus.note_id==cls.id,NoteStatus.user_id==user.id,NoteStatus.target_acted)))),
                    else_=cls.status.any(and_(NoteStatus.user_id==user.id,NoteStatus.target_acted))
                )
            case 'is_read':
                return case(
                    (cls.n_date < user.date,not_(cls.status.any(and_(NoteStatus.note_id==cls.id,NoteStatus.user_id==user.id,NoteStatus.read)))),
                    else_=cls.status.any(and_(NoteStatus.note_id==cls.id,NoteStatus.user_id==user.id,NoteStatus.read))
                )
            case 'num_sign_despacho':
                return select(func.count(NoteStatus.user_id)).where(NoteStatus.note_id==cls.id,NoteStatus.sign_despacho).scalar_subquery()
                return func.count(cls.status.any(NoteStatus.sign_despacho))

    def is_involve(self,reg,user):
        if reg[0] == 'des':
            return True
        elif reg[2]: # It is from a subregister
            check = db.session.scalar(select(User).where(User.alias==reg[2]))
        else:
            check = user
        
        return self.result('is_target',check)
    
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
            fn.append(User.category.in_(['dr','of']))
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.order.desc())).all() if user.alias != self.sender.alias]
            firsts = []
            for pot in possibles:
                if pot == '---':
                    firsts.append(('---','--- All above at the same time ---'))
                else:
                    for rc in recs:
                        if rc[0] == pot:
                            firsts.append(rc)

            for ft in firsts:
                if ft in recs:
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

class Group(db.Model):
    __tablename__= 'group'
    
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    category: Mapped[str] = mapped_column(db.String(50), default = '')
    text: Mapped[str] = mapped_column(db.String(50), default = '')

    def __eq__(self, other):
        if isinstance(other,str):
            return self.text == other
        else:
            return self.text == other.text

    def __ne__(self, other):
        if isinstance(other,str):
            return self.text != other
        else:
            return self.text != other.text

user_group = db.Table('user_group',
                db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                db.Column('group_id', db.Integer, db.ForeignKey('group.id'))
                )

class Setting(db.Model):
    __tablename__= 'setting'
    
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)

    user: Mapped["User"] = relationship(back_populates="setting")
    
    password: Mapped[str] = mapped_column(db.String(500), default='')
    password_nas: Mapped[str] = mapped_column(db.String(500), default='')
    
    notifications: Mapped[str] = mapped_column(db.Boolean, default=False)

user_ctr = db.Table('user_ctr',
                db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                db.Column('ctr_id', db.Integer, db.ForeignKey('user.id'))
                )

class User(UserProp,UserMixin, db.Model):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    password: Mapped[str] = mapped_column(db.String(500), default='')
    password_nas: Mapped[str] = mapped_column(db.String(500), default='')

    setting_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("setting.id"))
    setting: Mapped["Setting"] = relationship(back_populates="user")

    registers: Mapped[list["RegisterUser"]] = relationship(back_populates="user")
    
    category: Mapped[str] = mapped_column(db.String(20), default='')
    
    ctrs: Mapped[list["User"]] = relationship('User', secondary=user_ctr, primaryjoin=user_ctr.c.user_id==id, secondaryjoin=user_ctr.c.ctr_id==id, order_by="desc(User.alias)")

    groups: Mapped[list["Group"]] = relationship('Group', secondary=user_group, primaryjoin=user_group.c.user_id==id, secondaryjoin=user_group.c.group_id==Group.id, order_by="desc(Group.text)") 
    u_groups: Mapped[str] = mapped_column(db.String(500), default='')

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

    def get_setting(self,setting):
        if self.setting:
            return getattr(self.setting,setting)
        return None

    def set_setting(self,setting,value):
        if not self.setting:
            self.setting = Setting()
        setattr(self.setting,setting,value)

        db.session.commit()
    
    def set_register_access(self,register,access,user=current_user):
        rst = self.current_status(user)
        if not rst:
            status = NoteStatus(note_id=self.id,user_id=user.id)
            setattr(status,attr,True)
            db.session.add(status)
        else:
            setattr(rst,attr,not getattr(rst,attr))
        
        db.session.commit()

    def add_group(self,group):
        group = db.session.scalar(select(Group).where(Group.text==group))
        if group and not group in self.groups:
            self.groups.append(group)
            db.session.commit()
            
    def del_group(self,group):
        group = db.session.scalar(select(Group).where(Group.text==group))
        if group in self.groups:
            self.groups.remove(group)

            db.session.commit()


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
        pendings = db.session.scalars(select(Note).where(and_(not_(Note.register.has(Register.alias=='mat')),Note.has_target(current_user.id),Note.state<6,Note.state>4)))
        for note in pendings:
            if not note.result('is_read',current_user):
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
                rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg!='mat',Note.flow=='in',Note.register.has(Register.permissions!='notallowed'),not_(Note.result('is_read'))))
            else:
                rst = db.session.scalar(select(func.count(Note.id)).where(not_(Note.permanent),Note.reg!='mat',Note.flow=='in',Note.register.has(Register.permissions!='notallowed'),not_(Note.result('is_read'))))
                rst += db.session.scalar(select(func.count(Note.id)).where(not_(Note.permanent),Note.reg=='ctr',Note.flow=='out',Note.register.has(Register.permissions!='notallowed'),not_(Note.result('is_read'))))
            rst = current_user.unread
        elif '_' in info:
            reg = info.split('_')
            register = db.session.scalar(select(Register).where(Register.alias==reg[0]))
            if reg[2]:
                rst = register.unread(reg[2])
            else:
                rst = register.unread()
        if html:
            rst = str(rst) if rst > 0 else ""

        return rst

    @property
    def pendings(self):
        return db.session.scalar(select(func.count(Note.id)).where(not_(Note.result('is_read')),Note.register.has(Register.alias!='mat'),Note.has_target(current_user.id),Note.state<6,Note.state>4))

    @property
    def despacho(self):
        return db.session.scalar(select(func.count(Note.id)).where(not_(Note.result('is_sign_despacho')),Note.register.has(Register.contains_group('despacho')),Note.state<5,Note.state>2))


    @property
    def unread(self):
        cont = 0
        registers = db.session.scalars(select(Register).where(and_(Register.active==1,Register.permissions=='allowed'))).all()
        for register in registers:
            for sb in register.get_subregisters():
                cont += db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id==register.id,Note.flow=='out',Note.has_target(sb),not_(Note.result('is_read')))))

        if 'permanent' in current_user.groups:
            cont += db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id.in_([reg.id for reg in registers]),Note.flow=='in',not_(Note.result('is_read')))))
        else:
            cont += db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.permanent==False,Note.register_id.in_([reg.id for reg in registers]),Note.flow=='in',not_(Note.result('is_read')))))
        
        return cont

    @property
    def pending_matters(self):
        return db.session.scalar(select(func.count()).where(Note.state>0,Note.reg=='mat',Note.target_working()))

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

class RegisterUser(db.Model):
    __tablename__ = 'registeruser'
    
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    register_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("register.id"), primary_key=True)
    
    user: Mapped["User"] = relationship(back_populates="registers")
    register: Mapped["Register"] = relationship(back_populates="users")
    
    access: Mapped[str] = mapped_column(db.String(20), default='')

class Register(RegisterHtml,db.Model):
    __tablename__ = 'register'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    
    name: Mapped[str] = mapped_column(db.String(200), default='')
    alias: Mapped[str] = mapped_column(db.String(20), unique=True)
    
    users: Mapped[list["RegisterUser"]] = relationship(back_populates="register")
    
    r_groups: Mapped[str] = mapped_column(db.String(200), default=False)
    
    in_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    out_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    #protocol_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    folder: Mapped[str] = mapped_column(db.String(200), default='')

    active: Mapped[str] = mapped_column(db.Boolean, default=True)
    
    notes: Mapped[list["Note"]] = relationship(back_populates="register")

    def __repr__(self):
        return f"{self.name} ({self.alias})"

    def get_user_access(self,c_user=current_user):
        return next((user.access for user in self.users if user.user_id == c_user.id), None)

    def set_user_access(self,value,c_user=current_user):
        user = next((user for user in self.users if user.user_id == c_user.id), None)
        if user:
            user.access = value
        else:
            self.users.append(RegisterUser(user_id=c_user.id,register_id=self.id,access=value))
        
        db.session.commit()

    @hybrid_method
    def contains_group(cls,group):
        return cls.r_groups.regexp_match(fr'(^|[^-])\b{group}\b($|[^-])')

    @property
    def groups(self):
        return [g.strip() for g in self.r_groups.split(",")]
    
    @hybrid_property
    def permissions(self): # it is only for full register not subregister
        return next((user.access for user in self.users if user.user_id == current_user.id), None)
    
    @permissions.expression
    def permissions(cls):
        return cls.users.any(and_(RegisterUser.user_id==current_user.id,RegisterUser.access!=''))

    def get_subregisters(self,ids=False):
        if self.alias == 'ctr':
            return [ctr.alias for ctr in current_user.ctrs]
        else:
            return []

    def get_contacts(self):
        return [contact.user for contact in self.users if contact.access == 'contact']
 
    @property
    def get_num_contacts(self):
        return len(self.get_contacts())

    def unread(self,sb=""):
        if sb:
            return db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id==self.id,Note.flow=='out',Note.has_target(sb),not_(Note.result('is_read')))))
        else:
            if 'permanent' in current_user.groups:
                return db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.register_id==self.id,Note.flow=='in',not_(Note.result('is_read')))))
        
            return db.session.scalar(select(func.count(Note.id)).where(and_(Note.state>=5,Note.permanent==False,Note.register_id==self.id,Note.flow=='in',not_(Note.result('is_read')))))

