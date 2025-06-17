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
from .html.page import PageHtml
from .nas.note import NoteNas
from .html.register import RegisterHtml

from .properties.user import UserProp

def get_register(prot):
    registers = db.session.scalars(select(Register).where(Register.active==1))
    prot = re.sub(r'\d+\/\d+','',prot)
    prot = prot.strip('- ')
    for reg in registers:
        alias = r"[^0-9-]+"
        if re.fullmatch( eval(f"f'{reg.in_pattern}'"),prot,re.IGNORECASE): # Could note IN
            alias = ""
            
            senders = db.session.scalars(select(User).where(User.registers.any(and_(RegisterUser.register_id==reg.id,RegisterUser.access=='contact')) )).all()
            if len(senders) == 1:
                sender = senders[0]
            else:
                rst = re.sub( eval(f"f'{reg.in_pattern}'"),'',prot)
                if 'personal' in reg.groups or reg.alias == 'mat':
                    sender = db.session.scalar(select(User).where(User.alias==rst))
                else:
                    sender = db.session.scalar(select(User).where(User.alias==rst,User.registers.any(and_(RegisterUser.register_id==reg.id,RegisterUser.access=='contact')) ))
           
            if sender != None:
                return {'reg':reg,'sender':sender,'flow':'in'}

        
        #alias = r"\D+$"
        alias = r"[^0-9-]+$"
        if re.fullmatch( eval(f"f'{reg.out_pattern}'"),prot,re.IGNORECASE) and reg.alias != 'mat': # Could note OUT
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
    mark_for_deletion: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
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
    sender: Mapped["User"] = relationship("User",foreign_keys=[sender_id])
    new_owner_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('user.id'),nullable=True)
    new_owner: Mapped["User"] = relationship("User",foreign_keys=[new_owner_id])
    

    tags: Mapped[list["Tag"]] = relationship('Tag', secondary=note_tag, primaryjoin=note_tag.c.note_id==id, secondaryjoin=note_tag.c.tag_id==Tag.id, order_by="desc(Tag.id)") 
    
    users: Mapped[list["NoteUser"]] = relationship(back_populates="note", order_by="NoteUser.target_order")
    status: Mapped[str] = mapped_column(db.String(20), default = 'draft')

    n_date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    due_date: Mapped[datetime.date] = mapped_column(db.Date, nullable=True)
    sent_date: Mapped[datetime.date] = mapped_column(db.Date, nullable=True)
    
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

    archived: Mapped[bool] = mapped_column(db.Boolean, default=False)

    files: Mapped[list["File"]] = relationship(back_populates="note", order_by="File.files_order,File.path")
    comments_ctr: Mapped[list["Comment"]] = relationship(back_populates="note")

    files_date = column_property(
        select(func.max(File.date)).
        where(File.note_id==id).
        correlate_except(File).
        scalar_subquery()
    )
    """
    def __init__(self, *args, **kwargs):
        super(Note,self).__init__(*args, **kwargs)
        self.sender = db.session.scalar(select(User).where(User.id==self.sender_id))  
        self.year = datetime.utcnow().year
        alias = self.sender.alias
        flow = 'out' if self.sender.category in ['dr','of'] else 'in'
        
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
    """
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
        if isinstance(user,str):
            return db.session.scalar(select(NoteUser).where(NoteUser.note_id==self.id,NoteUser.user.has(User.alias==user)))
        elif isinstance(user,dict):
            return db.session.scalar(select(NoteUser).where(NoteUser.note_id==self.id,NoteUser.user.has(User.alias==user['alias'])))
        else:
            return db.session.scalar(select(NoteUser).where(NoteUser.note_id==self.id,NoteUser.user_id==user.id))

    def actived_status(self):
        return db.session.scalars(select(NoteUser).where(NoteUser.target_order==self.current_target_order)).all()

    def toggle_status_attr(self,attr,user=current_user):
        rst = self.current_status(user)
        if not rst:
            status = NoteUser(note_id=self.id,user_id=user.id)
            setattr(status,attr,True)
            db.session.add(status)
        else:
            setattr(rst,attr,not getattr(rst,attr))
        
        db.session.commit()

    def add_tag(self,tag):
        db_tag = db.session.scalar(select(Tag).where(Tag.text==tag))
        if db_tag and not tag in self.tags:
            self.tags.append(db_tag)
            db.session.commit()
            
    def del_tag(self,tag):
        db_tag = db.session.scalar(select(Tag).where(Tag.text==tag))
        if db_tag and tag in self.tags:
            self.tags.remove(db_tag)

            db.session.commit()

    def set_access_user(self,access,user=current_user):
        rst = self.current_status(user)
        
        if not rst:
            if isinstance(user,int):
                noteuser = NoteUser(note_id=self.id,user_id=user)
            elif isinstance(user,str):
                db_user = db.session.scalar(select(User).where(User.alias==user))
                noteuser = NoteUser(note_id=self.id,user_id=db_user.id)
            elif isinstance(user,User):
                noteuser = NoteUser(note_id=self.id,user_id=user.id)
            noteuser.access = access
            db.session.add(noteuser)
        else:
            rst.access = access
        
        db.session.commit()
 
    def deleteFiles(self,files_id):
        db.session.execute(delete(File).where(File.id.in_(files_id)))

    def addFileArgs(self,*args,**kargs):
        self.addFile(File(**kargs))

    @property
    def receiver(self):
        return [user.user for user in self.users if user.target]

    @hybrid_method
    def has_target(self,user):
        if isinstance(user,int):
            return any([rec for rec in self.receiver if rec.id == user])
        elif isinstance(user,str):
            if user.isdigit():
                return any([rec for rec in self.receiver if rec.id == int(user)])
            else:
                return any([rec for rec in self.receiver if rec.alias == user])
        elif isinstance(user,User):
            return user in self.receiver

        return False

    @has_target.expression
    def has_target(cls, user):
        if isinstance(user,int):
            return exists().where(NoteUser.note_id == cls.id, NoteUser.user_id == user, NoteUser.target)
        elif isinstance(user,str):
            if user.isdigit():
                return exists().where(NoteUser.note_id == cls.id, NoteUser.user_id == int(user), NoteUser.target)
            else:
                return exists().where(NoteUser.note_id == cls.id, NoteUser.user.has(User.alias==user), NoteUser.target)
        elif isinstance(user,User):
            return exists().where(NoteUser.note_id == cls.id, NoteUser.user_id == user.id, NoteUser.target)

        return False


    @hybrid_method
    def target_working(self,cuser=current_user):
        order = 0
        for user in self.users:
            if user.target and user.target_acted == 0:
                order = user.target_order
            if user.user_id == cuser.id:
                if user.target_order == order:
                    return True
        
        return False

    @target_working.expression
    def target_working(cls,user=current_user):
        NS = aliased(NoteUser)
        subquery = select(func.min(NS.target_order)).where(
                        NS.note_id==cls.id,
                        NS.target,
                        not_(NS.target_acted)
                    )

        note = aliased(Note,name="note_user")

        rst = select(NoteUser).join(NoteUser.note.of_type(note)).where(
                NoteUser.note_id==cls.id,
                NoteUser.user_id == user.id,
                literal_column(f"note_user.status = 'shared'"),
                literal_column(f"note_user.reg = 'mat'"),
                NoteUser.target,
                not_(NoteUser.target_acted),
                NoteUser.target_order == subquery.scalar_subquery()
        )

        return exists(rst)

        rst = exists().where(
                NoteUser.note_id == cls.id,
                NoteUser.user_id == user.id,
                cls.status=='shared',
                cls.reg=='mat',
                NoteUser.target,
                not_(NoteUser.target_acted),
                NoteUser.target_order == subquery.scalar_subquery()
            )
        
        return rst

    @hybrid_property
    def owner_id(self):
        if self.new_owner_id is not None:
            return self.new_owner_id
        return self.sender_id
    

    @owner_id.expression
    def owner_id(cls):
        return case (
            (cls.new_owner_id.isnot(None),cls.new_owner_id),
            else_=cls.sender_id
        )

    @hybrid_property
    def owner(self):
        if self.new_owner_id:
            return self.new_owner
        return self.sender
    
    @owner.expression
    def owner(cls):
       return case (
            (cls.new_owner_id.isnot(None),cls.new_owner),
            else_=cls.sender
        )
 

    @hybrid_property
    def current_target_order(self):
        for user in self.users:
            if user.target and user.target_acted == 0:
                break
        return user.target_order

    @current_target_order.expression
    def current_target_order(cls):
        NS = aliased(NoteUser)
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
                return db.session.scalar(select(func.count(NoteUser.user_id)).where(NoteUser.note_id==self.id,NoteUser.target,NoteUser.target_acted))
            case 'num_target':
                return db.session.scalar(select(func.count(NoteUser.user_id)).where(NoteUser.note_id==self.id,NoteUser.target))
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
                return db.session.scalar(select(func.count(NoteUser.user_id)).where(NoteUser.note_id==self.id,NoteUser.sign_despacho))
            case 'access':
                rst = self.current_status()
                return rst.access if rst and rst.access else self.register.permissions

    @result.expression
    def result(cls,demand,user=current_user):
        match demand:
            case 'is_sign_despacho':
                return cls.users.any(and_(NoteUser.user_id==user.id,NoteUser.sign_despacho))
            case 'is_target':
                return cls.users.any(and_(NoteUser.user_id==user.id,NoteUser.target))
            case 'target_has_acted':
                return cls.users.any(and_(NoteUser.user_id==user.id,NoteUser.target,NoteUser.target_acted))

            case 'target_order':
                return select(NoteUser.target_order).where(NoteUser.note_id==cls.id,NoteUser.user_id==user.id).scalar_subquery()
            case 'is_done':
                return case(
                    (cls.n_date < user.date,not_(cls.users.any(and_(NoteUser.note_id==cls.id,NoteUser.user_id==user.id,NoteUser.target_acted)))),
                    else_=cls.users.any(and_(NoteUser.user_id==user.id,NoteUser.target_acted))
                )
            case 'is_read':
                return case(
                    (cls.n_date < user.date,not_(cls.users.any(and_(NoteUser.note_id==cls.id,NoteUser.user_id==user.id,NoteUser.read)))),
                    else_=cls.users.any(and_(NoteUser.note_id==cls.id,NoteUser.user_id==user.id,NoteUser.read))
                )
            case 'num_sign_despacho':
                return select(func.count(NoteUser.user_id)).where(NoteUser.note_id==cls.id,NoteUser.sign_despacho).scalar_subquery()
                return func.count(cls.users.any(NoteUser.sign_despacho))
            case 'access':
                if 'permanente' in user.groups:
                    return case(
                        (exists().where(NoteUser.access!='',NoteUser.note_id==cls.id,NoteUser.user_id==user.id),
                            select(NoteUser.access).where(NoteUser.note_id==cls.id,NoteUser.user_id==user.id).scalar_subquery()),
                        else_= select(RegisterUser.access).where(RegisterUser.register_id==cls.register_id,RegisterUser.user_id==user.id).scalar_subquery()
                    )
                else:
                    return case(
                        (exists().where(NoteUser.access!='',NoteUser.note_id==cls.id,NoteUser.user_id==user.id),
                            select(NoteUser.access).where(NoteUser.note_id==cls.id,NoteUser.user_id==user.id).scalar_subquery()),
                        (cls.permanent,False),
                        else_= select(RegisterUser.access).where(RegisterUser.register_id==cls.register_id,RegisterUser.user_id==user.id).scalar_subquery()
                    )
    def is_involve(self,reg,user):
        if reg[0] == 'des':
            return True
        elif reg[2]: # It is from a subregister
            check = db.session.scalar(select(User).where(User.alias==reg[2]))
        else:
            check = user
        
        return self.result('is_target',check)
    
    def potential_receivers(self,filter,possibles = [],only_of = False,for_pages=False):
        fn = []
        fn.append(User.active==1)
        
        if filter:
            fts = re.findall(r'\w+',filter)
            ftn = []
            for ft in fts:
                ftn.append(or_(func.lower(User.alias).contains(func.lower(ft)),User.description.regexp_match(fr'\b{ft}\b')))
            fn.append(and_(*ftn))
        
        if only_of:
            fn.append(User.category == 'of')
        
        recs = []

        if self.register.alias == 'mat':
            if not only_of:
                fn.append(User.category.in_(['dr','of']))
            
            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.order.desc(),User.name.desc())).all() if user.alias != self.sender.alias]
            
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
            if not only_of:
                fn.append(User.category.in_(['dr','of']))

            recs = [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(and_(*fn)).order_by(User.alias)).all() if user.alias in possibles or not possibles]
        else:
            fn.append(User.registers.any(and_(RegisterUser.access == 'contact',RegisterUser.register_id == self.register.id)))
            
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
        if self.sent_date:
            return self.sent_date
        else:
            rst = self.n_date
            for file in self.files:
                if rst < file.date:
                    rst = file.date
            return  self.sent_date if self.sent_date else self.n_date

    @date.expression
    def date(cls): 
        return case(
                (cls.sent_date.is_(None),
                    case(
                        (and_(cls.n_date < cls.files_date,cls.files_date.isnot(None)), cls.files_date),
                        else_=cls.n_date
                    )),
                else_=cls.sent_date
            )

    @hybrid_property
    def flow(self) -> str:
        return 'out' if self.sender.category in ['dr','of'] else 'in'
        return 'out' if any(map(lambda v: v in self.sender.groups, ['dr','of'])) else 'in'

    @flow.expression
    def flow(cls):
        return case (
            (cls.sender.has(User.category.in_(['dr','of'])),'out'),
            else_='in'
        )
        return case (
            (exists().where(User.id==cls.sender_id,User.category.in_(['dr','of'])),'out'),
            else_='in'
        )
        cr_users = [user.id for user in db.session.scalars( select(User).where(User.category.in_(['dr','of'])) ).all()]
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

page_group = db.Table('page_group',
                db.Column('page_id', db.Integer, db.ForeignKey('page.id')),
                db.Column('group_id', db.Integer, db.ForeignKey('group.id'))
                )

class Page(db.Model,PageHtml):
    __tablename__ = 'page'
    
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    title: Mapped[str] = mapped_column(db.String(500), default = '')
    category: Mapped[str] = mapped_column(db.String(50), default = '')
    
    text: Mapped[str] = mapped_column(db.Text, default = '')
    order: Mapped[str] = mapped_column(db.Integer, default=0)
    
    date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    
    main: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    groups: Mapped[list["Group"]] = relationship('Group', secondary=page_group, primaryjoin=page_group.c.page_id==id, secondaryjoin=page_group.c.group_id==Group.id, order_by="desc(Group.text)") 
    
    users: Mapped[list["PageUser"]] = relationship(back_populates="page")

    @property
    def id_str(self):
        return str(self.id)

    @property
    def str_id(self):
        return str(self.id)

    @property
    def possible_groups(self):
        return db.session.scalars(select(Group.text).where(Group.category.in_(['page','ctr']))).all()

    @hybrid_method
    def has_access(self,user=current_user,for_list=False):
        if user.category in self.groups or 'scr' in user.groups or 'admin' in user.groups:
            return True
        elif self.title in [f'{ctr.alias} cl' for ctr in user.ctrs]:
            return True
        else:
            for ctr in user.ctrs:
                for gp in ctr.groups:
                    if gp in self.groups:
                        return True

            rst = self.get_user(user)
            
            if rst and rst.access != '':
                return True
        return False
    
    @has_access.expression
    def has_access(cls,user=current_user,for_list=False):
        if not for_list and ('scr' in user.groups or 'admin' in user.groups):
            return True
        ctrs = user.ctrs
        gps = []
        for ctr in ctrs:
            for gp in ctr.groups:
                if not gp.id in gps:
                    gps.append(gp.id)

        return or_(
            cls.title.in_([f'{ctr.alias} cl' for ctr in user.ctrs]),
            cls.groups.any(Group.text==user.category),
            cls.groups.any(Group.id.in_(gps)),
            #cls.groups.any(Group.id.in_([gp.id for gp in gps for gps in user.ctrs.groups])),
            cls.users.any(and_(PageUser.user_id == user.id,PageUser.access != ''))
        )

    
    def get_user(self,user=current_user):
        if isinstance(user,str):
            return db.session.scalar(select(PageUser).where(PageUser.page_id==self.id,PageUser.user.has(User.alias==user)))
        elif isinstance(user,int):
            return db.session.scalar(select(PageUser).where(PageUser.page_id==self.id,PageUser.user.has(User.id==user)))
        else:
            return db.session.scalar(select(PageUser).where(PageUser.page_id==self.id,PageUser.user_id==user.id))

    def set_access(self,user,value):
        rst = self.get_user(user)

        if not rst:
            if isinstance(user,str):
                user = db.session.scalar(select(User).where(User.alias==user))
            elif isinstance(user,int):
                user = db.session.scalar(select(User).where(User.id==user))

            access = PageUser(page_id=self.id,user_id=user.id,access=value)
            db.session.add(access)
        else:
            rst.access = value
        
        db.session.commit()

    def potential_receivers(self,filter):
        fn = []
        fn.append(User.active==1)
        
        if filter:
            fts = re.findall(r'\w+',filter)
            ftn = []
            for ft in fts:
                ftn.append(or_(func.lower(User.alias).contains(func.lower(ft)),User.description.regexp_match(fr'\b{ft}\b')))
            fn.append(and_(*ftn))

        fn.append(User.category.in_([group for group in self.possible_groups if not group in self.groups]))

        return [(user.alias,f"{user.name} ({user.description})") for user in db.session.scalars(select(User).where(*fn).order_by(User.category,User.alias)).all()]


class PageUser(db.Model):
    __tablename__ = 'pageuser'
    page_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("page.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("user.id"), primary_key=True)

    page: Mapped["Page"] = relationship(back_populates="users")
    user: Mapped["User"] = relationship(back_populates="pages")

    access: Mapped[str] = mapped_column(db.String(20), default='')


class Setting(db.Model):
    __tablename__= 'setting'
    
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)

    user: Mapped["User"] = relationship(back_populates="setting")
    
    password: Mapped[str] = mapped_column(db.String(500), default='')
    password_nas: Mapped[str] = mapped_column(db.String(500), default='')
    
    notifications: Mapped[bool] = mapped_column(db.Boolean, default=False)

user_ctr = db.Table('user_ctr',
                db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                db.Column('ctr_id', db.Integer, db.ForeignKey('user.id'))
                )

class User(UserProp,UserMixin, db.Model):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy

    setting_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("setting.id"))
    setting: Mapped["Setting"] = relationship(back_populates="user")

    registers: Mapped[list["RegisterUser"]] = relationship(back_populates="user")
    
    category: Mapped[str] = mapped_column(db.String(20), default='')
    
    ctrs: Mapped[list["User"]] = relationship('User', secondary=user_ctr, primaryjoin=user_ctr.c.user_id==id, secondaryjoin=user_ctr.c.ctr_id==id, order_by="desc(User.alias)")

    groups: Mapped[list["Group"]] = relationship('Group', secondary=user_group, primaryjoin=user_group.c.user_id==id, secondaryjoin=user_group.c.group_id==Group.id, order_by="desc(Group.text)") 

    date: Mapped[datetime.date] = mapped_column(db.Date, default=datetime.utcnow())
    name: Mapped[str] = mapped_column(db.String(200), default='')
    alias: Mapped[str] = mapped_column(db.String(20), unique=True)
    order: Mapped[str] = mapped_column(db.Integer, default=0)

    email: Mapped[str] = mapped_column(db.String(200), default='')
    description: Mapped[str] = mapped_column(db.String(200), default='')
    
    local_path: Mapped[str] = mapped_column(db.String(200), default='')
    
    notes: Mapped[list["NoteUser"]] = relationship(back_populates="user")
    pages: Mapped[list["PageUser"]] = relationship(back_populates="user")
    
    active: Mapped[str] = mapped_column(db.Boolean, default=True)
    admin_active: Mapped[str] = mapped_column(db.Boolean, default=False)

    #outbox: Mapped[list["Note"]] = relationship(back_populates="sender")

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
            status = NoteUser(note_id=self.id,user_id=user.id)
            setattr(status,attr,True)
            db.session.add(status)
        else:
            setattr(rst,attr,not getattr(rst,attr))
        
        db.session.commit()

    def add_group(self,group):
        db_group = db.session.scalar(select(Group).where(Group.text==group))
        if db_group and not group in self.groups:
            self.groups.append(db_group)
            db.session.commit()
            
    def del_group(self,group):
        db_group = db.session.scalar(select(Group).where(Group.text==group))
        if db_group and group in self.groups:
            self.groups.remove(db_group)

            db.session.commit()

    @property
    def my_pages(self):
        #pages = db.session.scalars(select(Page).where(Page.main,Page.groups.any(Group.text==current_user.category))).all()
        pages = db.session.scalars(select(Page).where(Page.main,Page.has_access(for_list=True)).order_by(Page.order,Page.title)).all()

        return pages

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
        pendings = db.session.scalars(select(Note).where(
            Note.register.has(Register.alias!='mat'),
            Note.has_target(current_user.id),
            Note.status=='registered',
            not_(Note.status))
        )
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
        if info == "myinbox":
            rst = current_user.pendings
        elif info == "snooze":
            rst = current_user.snooze
        elif info == "myoutbox":
            rst = current_user.pendings_out
        elif info == "done":
            rst = 0
        elif info == "proposals_to_sign":
            rst = current_user.pending_matters_to_sign
        elif info == "proposals_to_finish":
            rst = current_user.pending_matters_done
        elif info == "proposals_all":
            rst = current_user.pending_matters
        elif info == "proposals_to_sign":
            rst = current_user.pending_matters_to_sign
        elif info == "proposals_draft":
            rst = current_user.pending_matters_draft
        elif info == "proposals_snooze":
            rst = current_user.pending_matters_snooze
        elif info == "proposals_shared":
            rst = current_user.pending_matters_shared
        elif info == "proposals_done":
            rst = current_user.pending_matters_done
        elif info == "unread":
            rst = current_user.unread
        elif info == 'despacho':
            rst = current_user.despacho
        elif info == 'files_imported':
            rst = db.session.scalar(select(func.count(File.id)).where(File.note_id==None))
        elif info == 'inbox':
            rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg!='mat',Note.flow=='in',Note.status=='queued'))
        elif info == 'outbox':
            rst = db.session.scalar(select(func.count(Note.id)).where(Note.reg!='mat',Note.flow=='out',Note.status=='queued'))
        elif info == 'register': # All registers together
            rst = current_user.unread
        elif '_' in info: #Each register
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
        return db.session.scalar(select(func.count(Note.id)).where(
            #not_(Note.result('is_read')),
            Note.register.has(Register.alias!='mat'),
            Note.has_target(current_user.id),
            Note.status=='registered',
            Note.due_date.is_(None),
            not_(Note.archived)
        ))

    @property
    def snooze(self):
        return db.session.scalar(select(func.count(Note.id)).where(
            #not_(Note.result('is_read')),
            Note.register.has(Register.alias!='mat'),
            Note.has_target(current_user.id),
            Note.status=='registered',
            not_(Note.due_date.is_(None)),
            not_(Note.archived)
        ))

    @property
    def pendings_out(self):
        return db.session.scalar(select(func.count(Note.id)).where(
            Note.reg!='mat',
            Note.register.has(Register.alias!='mat'),
            Note.sender_id == current_user.id,
            Note.status!='sent'
        ))

    @property
    def despacho(self):
        return db.session.scalar(select(func.count(Note.id)).where(
            Note.result('num_sign_despacho')<2,
            not_(Note.result('is_sign_despacho')),
            Note.register.has(Register.groups.any(Group.text=='despacho')),
            Note.status=='despacho',
        ))


    @property
    def unread(self):
        cont = 0
        
        ## This is for ctr registers
        for ctr in self.ctrs:
            cont += db.session.scalar(select(func.count(Note.id)).where(
                Note.status=='sent',Note.register.has(Register.alias=='ctr'),Note.has_target(ctr),not_(Note.result('is_read'))
            ))

        ## All the others
        if 'permanente' in current_user.groups:
            cont += db.session.scalar(select(func.count(Note.id)).where(
                Note.status=='registered',
                Note.result('access').in_(['reader','editor']),
                not_(Note.result('is_read'))
            ))
        else:
            cont += db.session.scalar(select(func.count(Note.id)).where(
                Note.status=='registered',
                Note.permanent==False,
                Note.result('access').in_(['reader','editor']),
                not_(Note.result('is_read'))
            ))


        return cont

    @property
    def pending_matters(self):
        return db.session.scalar(select(func.count()).where(Note.status=='shared',Note.reg=='mat',not_(Note.result('is_done')),Note.current_target_order==Note.result('target_order')))
    
    @property
    def pending_matters_to_sign(self):
        return db.session.scalar(select(func.count()).where(
            Note.status=='shared',
            Note.reg=='mat',
            Note.result('is_target'),
            not_(Note.result('target_has_acted')),
            Note.current_target_order==Note.result('target_order')))

    @property
    def pending_matters_draft(self):
        return db.session.scalar(select(func.count()).where(
            Note.sender_id==current_user.id,
            Note.status=='draft',
            Note.reg=='mat',
            not_(Note.archived),
            Note.due_date.is_(None)
            ))
    @property
    def pending_matters_snooze(self):
        return db.session.scalar(select(func.count()).where(
            Note.sender_id==current_user.id,
            Note.reg=='mat',
            not_(Note.due_date.is_(None))
            ))

    @property
    def pending_matters_shared(self):
        return db.session.scalar(select(func.count()).where(
                Note.sender_id==current_user.id,
                Note.status=='shared',
                Note.reg=='mat',
                not_(Note.result('is_done'))))

    @property
    def pending_matters_done(self):
        return db.session.scalar(select(func.count()).where(
                Note.sender_id==current_user.id,
                or_(Note.status=='approved',Note.status=='denied'),
                Note.reg=='mat',
                Note.due_date.is_(None),
                not_(Note.archived)))


class NoteUser(db.Model):
    __tablename__ = 'noteuser'
    note_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("note.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("user.id"), primary_key=True)

    note: Mapped["Note"] = relationship(back_populates="users")
    user: Mapped["User"] = relationship(back_populates="notes")

    read: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    target: Mapped[bool] = mapped_column(db.Boolean, default=False)
    target_order: Mapped[int] = mapped_column(db.Integer, default=0)
    target_acted: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    access: Mapped[str] = mapped_column(db.String(20), default='')
    
    sign_despacho: Mapped[bool] = mapped_column(db.Boolean, default=False)

    comment: Mapped[str] = mapped_column(db.String(500), default='')



class RegisterUser(db.Model):
    __tablename__ = 'registeruser'
    
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    register_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("register.id"), primary_key=True)
    
    user: Mapped["User"] = relationship(back_populates="registers")
    register: Mapped["Register"] = relationship(back_populates="users")
    
    access: Mapped[str] = mapped_column(db.String(20), default='')



register_group = db.Table('register_group',
                db.Column('register_id', db.Integer, db.ForeignKey('register.id')),
                db.Column('group_id', db.Integer, db.ForeignKey('group.id'))
                )


class Register(RegisterHtml,db.Model):
    __tablename__ = 'register'

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    
    name: Mapped[str] = mapped_column(db.String(200), default='')
    alias: Mapped[str] = mapped_column(db.String(20), unique=True)
    
    users: Mapped[list["RegisterUser"]] = relationship(back_populates="register")
    
    groups: Mapped[list["Group"]] = relationship('Group', secondary=register_group, primaryjoin=register_group.c.register_id==id, secondaryjoin=register_group.c.group_id==Group.id, order_by="desc(Group.text)") 
    
    in_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    out_pattern: Mapped[str] = mapped_column(db.String(200), default='')
    
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

    @hybrid_property
    def permissions(self): # it is only for full register not subregister
        return db.session.scalar(select(RegisterUser.access).where(RegisterUser.register_id==self.id,RegisterUser.user_id==current_user.id))
        return next((user.access for user in self.users if user.user_id == current_user.id), None)
    
    @permissions.expression
    def permissions(cls):
        return select(RegisterUser.access).where(RegisterUser.register_id==cls.id,RegisterUser.user_id==current_user.id).scalar_subquery()

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

    def unread(self,ctr=""):
        if ctr:
            return db.session.scalar(select(func.count(Note.id)).where(
                Note.status=='sent',Note.register_id==self.id,Note.has_target(ctr),not_(Note.result('is_read'))
            ))
        else:
            if 'permanente' in current_user.groups:
                return db.session.scalar(select(func.count(Note.id)).where(Note.status=='registered',Note.result('access').in_(['reader','editor']),Note.register_id==self.id,not_(Note.result('is_read'))))
             
            return db.session.scalar(select(func.count(Note.id)).where(Note.status=='registered',Note.permanent==False,Note.result('access').in_(['reader','editor']),Note.register_id==self.id,not_(Note.result('is_read'))))


class Value(db.Model):
    __tablename__ = 'value'
    name: Mapped[str] = mapped_column(db.String(20), primary_key=True)
    value: Mapped[str] = mapped_column(db.String(200), default='')

