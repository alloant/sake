#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ast
import re
from datetime import datetime

from flask import session
from flask_login import current_user

from sqlalchemy import select, and_, or_, func, not_
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased

from app.src.models import Note, User, Register, File, NoteUser, Group, Tag


def sccr_sql(reg, count=False):
    if count:
        rst_sql = select(func.count(Note.id))
    else:
        rst_sql = select(Note)

    match f'{reg[0]}_{reg[1]}':
        case 'box_in':
            filter = [Note.status == 'queued',Note.flow=='in']
        case 'box_out':
            filter = [Note.status == 'queued',Note.flow=='out']
        case 'import_in':
            if count:
                return select(func.count(File.id)).where(File.note_id==None)
            else:
                return select(File).where(File.note_id==None)

    return rst_sql.where(*filter).order_by(Note.date.desc())

def notes_sql(reg,state="",count=False,bar_filter=''): #stete can be snooze or archived
    if count:
        rst_sql = select(func.count(Note.id))
    else:
        rst_sql = select(Note)

    match f'{reg[0]}_{reg[1]}':
        case 'my_in': # Notes, in (registered), current_user is target
            filter = [
                Note.status == 'registered',
                Note.has_target(current_user.id),
                not_(Note.archived),
                Note.due_date.is_(None)
            ]
        case 'my_snooze': # Notes, in (registered), current_user is target
            filter = [
                Note.status == 'registered',
                Note.has_target(current_user.id),
                not_(Note.due_date.is_(None))
            ]

        case 'my_archived': # Notes, in (registered), current_user is target
            filter = [
                Note.status == 'registered',
                Note.has_target(current_user.id),
                Note.archived
            ]

        case 'my_out': # Notes, out(drafts), current_user is sender
            filter = [Note.reg != 'mat',Note.status.in_(['draft','queued']),Note.sender_id == current_user.id]
        case 'my_sent': # Notes, out(sent), current_user is sender
            filter = [Note.reg != 'mat',Note.status == 'sent',Note.sender_id == current_user.id]
        case 'mat_all': # Proposals (better not to use this that is useless)
            filter = [Note.reg == 'mat',
                      or_(Note.sender_id == current_user.id,
                          and_(
                            Note.result('is_target'),
                            Note.status != 'draft',
                            or_(
                                Note.result('is_done'),
                                Note.current_target_order == Note.result('target_order')
                                )
                            )
                          )
                      ]
        case 'mat_sign':
            filter = [  Note.reg == 'mat',
                        Note.result('is_target'),
                        Note.status != 'draft',
                        Note.current_target_order == Note.result('target_order'),
                        not_(Note.result('target_has_acted'))
                      ]
        case 'mat_signed':
            filter = [  Note.reg == 'mat',
                        Note.result('is_target'),
                        Note.status != 'draft',
                        Note.result('is_done'),
                      ]
        case 'mat_draft':
            filter = [  Note.reg == 'mat',
                        or_(Note.owner_id == current_user.id, Note.sender_id == current_user.id),
                        not_(Note.archived),
                        Note.status == 'draft',
                        Note.due_date.is_(None)
                      ]
        case 'mat_shared':
            filter = [  Note.reg == 'mat',
                        or_(Note.owner_id == current_user.id, Note.sender_id == current_user.id),
                        Note.status == 'shared'
                      ]
        case 'mat_done':
            filter = [  Note.reg == 'mat',
                        or_(Note.owner_id == current_user.id, Note.sender_id == current_user.id),
                        Note.status.in_(['approved','denied']),
                        not_(Note.archived),
                        Note.due_date.is_(None)
                      ]
        case 'mat_snooze':
            filter = [  Note.reg == 'mat',
                        or_(Note.owner_id == current_user.id, Note.sender_id == current_user.id),
                        Note.status.in_(['approved','denied','draft']),
                        not_(Note.due_date.is_(None)) 
                      ]
        case 'mat_archived':
            filter = [  Note.reg == 'mat',
                        or_(Note.owner_id == current_user.id, Note.sender_id == current_user.id),
                        Note.status.in_(['approved','denied','draft']),
                        Note.archived
                      ]
        case 'notes_all':
            filter = [
                Note.reg != 'mat',
                Note.status == 'registered'
            ]
            
            if current_user.admin:
                filter.append(Note.register.has(Register.active==1))
            else:
                filter.append(Note.register.has(and_(Register.active==1,Register.permissions!='')))

            if not 'permanente' in current_user.groups:
                filter.append(not_(Note.permanent))

            if count:
                filter.append(not_(Note.result('is_read')))
        
        case 'all_all':
            if session['filter_option'] == 'only_notes':
                filter = [
                        Note.reg != 'mat',
                        Note.status.in_(['registered','sent'])
                    ]
            elif session['filter_option'] == 'only_proposals':
                filter = [
                    Note.reg == 'mat',
                    or_(Note.sender_id==current_user.id,and_(Note.has_target(current_user.id),Note.status.in_(['approved','denied'])))
                ]
            elif session['filter_option'] == 'notes_proposals':
                filter = [ or_(
                    and_(
                        Note.reg != 'mat',
                        Note.status.in_(['registered','sent'])
                    ),
                    and_(
                        Note.reg == 'mat',
                        or_(Note.sender_id==current_user.id,and_(Note.has_target(current_user.id),Note.status.in_(['approved','denied'])))
                    )
                )]
                   
            if current_user.admin:
                filter.append(Note.register.has(Register.active==1))
            else:
                filter.append(Note.register.has(and_(Register.active==1,Register.permissions!='')))

            if not 'permanente' in current_user.groups:
                filter.append(not_(Note.permanent))


        case 'notes_unread':
            filter = [
                Note.reg != 'mat',
                Note.status == 'registered',
                not_(Note.result('is_read')),
                Note.register.has(and_(Register.active==1,Register.permissions!=''))
            ]
            
            if not 'permanente' in current_user.groups:
                filter.append(not_(Note.permanent))
        case 'des_in':
            filter = [
                    Note.result('num_sign_despacho')<2,
                    Note.register.has(Register.groups.any(Group.text=='despacho')),
                    Note.status == 'despacho'
            ]
            if count:
                filter.append(not_(Note.result('is_sign_despacho')))

        case _:
            if reg[2]: #Is a ctr register
                filter = [
                    Note.reg == reg[0]
                ]
                if reg[1] == 'in':
                    filter.append(Note.has_target(reg[2]))
                else:
                    filter.append(Note.sender.has(User.alias == reg[2]))

            else: # Normal cg, asr, r, ctr, vc, etc... in/out register
                filter = [
                    Note.reg == reg[0]
                ]
                if reg[1] == 'in':
                    filter.append(Note.status=='registered')
                    if not 'permanente' in current_user.groups:
                        filter.append(or_(not_(Note.permanent),Note.has_target(current_user.id)))
                else:
                    filter.append(or_(Note.status=='sent',and_(Note.sender_id==current_user.id,Note.status.in_(['queued','draft']))))
                    if not 'permanente' in current_user.groups:
                        filter.append(or_(not_(Note.permanent),Note.sender_id == current_user.id))
            if count:
                filter.append(not_(Note.result('is_read')))


    if bar_filter:
        filter += text_filter(bar_filter,reg)

    return rst_sql.where(*filter).order_by(Note.date.desc())


def text_filter(text,reg):
    ft = text
    
    tags = re.findall(r'#[^ ]*',ft)
    ft = re.sub(r'#[^ ]*','',ft).strip()
    tfn = []

    for tag in tags:
        #tfn.append(Note.contains_in('tags',tag.replace('#','').strip()))
        tfn.append(Note.tags.any(Tag.text == tag.replace('#','').strip()))

    senders = re.findall(r'@[^ ]*',ft)
    ft = re.sub(r'@[^ ]*','',ft).strip()
    sfn = []
    
    for sender in senders:
        alias = sender.replace('@','').strip()
        if reg[0] == 'mat' and alias == current_user.alias:
            sfn.append( Note.sender.has(User.alias==alias) )
        else:
            sfn.append( or_(Note.sender.has(User.alias==alias),Note.users.any(NoteUser.user.has(User.alias==alias))) )

    files = re.findall(r'file:\w+(?:[.-]\w+)*',ft)
    ft = re.sub(r'file:\w+(?:[.-]\w+)*','',ft).strip()
    ft_files = []
    for file in files:
        ft_files.append(Note.files.any(File.path.contains(file[5:])))

    flows = re.findall(r'flow:[^ ]*',ft)
    ft = re.sub(r'flow:[^ ]*','',ft).strip()
    ft_flows = []
    for flow in flows:
        ft_flows.append(Note.flow==flow[5:])

    dates = re.findall(r'date:[^ ]*',ft)
    ft = re.sub(r'date:[^ ]*','',ft).strip()
    ft_dates = []
    for ddt in dates:
        dt = ddt[5:]
        if '-' in dt:
            dts = dt.split('-')
            try:
                ft_dates.append(Note.n_date>=datetime.strptime(dts[0],'%d/%m/%Y'))
                ft_dates.append(Note.n_date<=datetime.strptime(dts[1],'%d/%m/%Y'))
            except:
                pass
        else:
            try:
                ft_dates.append(Note.n_date==datetime.strptime(dt,'%d/%m/%Y'))
            except:
                pass

    ofn = []
    if ft != "":
        ofn.append( Note.content.contains(ft) )
        ofn.append( Note.sender.has(User.alias==ft) )
        ofn.append( Note.has_target(ft) )
        

        rst = re.findall(r'\b[a-zA-Z-]* \b\d+\/\d+\b',ft)
        if rst:
            for r in rst:
                alias = re.search(r'\b[a-zA-Z-]*\b',r).group().replace('-Aes','')
                nums = re.findall(r'\d+',r)
                if db.session.scalar(select(User).where(User.alias==alias)):
                    ofn.append(and_(Note.sender.has(User.alias==alias),Note.num==nums[0],Note.year==2000+int(nums[1])))
                else:
                    ofn.append(and_(Note.num==nums[0],Note.year==2000+int(nums[1])))
        else:
            rst = re.findall(r'\b\d+\/\d+\b',ft)
            if rst:
                for r in rst:
                    nums = re.findall(r'\d+',r)
                    ofn.append(and_(Note.num==nums[0],Note.year==2000+int(nums[1])))
            else:
                rst = re.findall(r'\b\d+\b',ft)
                if rst:
                    for r in rst:
                        ofn.append(Note.num==r)

                
    return ft_flows + ft_dates + ft_files + sfn + tfn + [or_(*ofn)]






