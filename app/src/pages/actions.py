#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import re

from flask import render_template, session, make_response
from flask_login import current_user

from sqlalchemy import select, and_, or_, func, not_
from sqlalchemy.sql import text
from sqlalchemy.orm import aliased

from flask_babel import gettext

from app import db
from app.src.models import Page
from app.src.forms.page import PageForm

from app.src.pages.views import pages_table_view, pages_row_view

def pages_action(request):
    page_id = request.args.get('page',None)
    action = request.args.get('action')
    trigger = ['update-main']
    print('action',action,page_id)
    match action:
        case 'new':
            page = Page()
            db.session.add(page)
            db.session.commit()
        case 'edit':
            return edit_page(page_id,request)
        case 'save':
            save_page(page_id,request)

    if page_id:
        res = make_response(pages_row_view(request,page_id))
    else:
        res = make_response(pages_table_view(request))
    
    res.headers['HX-Trigger'] = ','.join(trigger)

    return res

def edit_page(page_id,request):
    page = db.session.scalar(select(Page).where(Page.id==page_id))
    form = PageForm(request.form,obj=page)
    
    form.title.data = page.title
    form.text.data = page.text

    return render_template('modals/modal_edit_page.html',page=page,form=form)

def save_page(page_id,request):
    page = db.session.scalar(select(Page).where(Page.id==page_id))
    form = PageForm(request.form,obj=page)

    page.title = form.title.data
    page.text = form.text.data

    db.session.commit()

