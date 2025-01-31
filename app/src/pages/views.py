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

def get_pages():
    sql = select(Page)
    pages = db.paginate(sql, per_page=25)

    return pages

def list_pages_view(request):
    page = 1 if not 'page' in session else session['page']
    
    res = make_response(render_template('pages/main.html',pages=get_pages(),page=page))
    res.headers['HX-Trigger'] = 'update-main'

    return res

def page_view(page_id):
    page = db.session.scalar(select(Page).where(Page.id==page_id))
    
    return render_template('pages/view.html',page=page)

def pages_table_view(request):
    page = 1 if not 'page' in session else session['page']
    
    return render_template('pages/table.html',pages=get_pages(),page=page)


def pages_row_view(request,page_id):
    page = db.session.scalar(select(Page).where(Page.id==page_id))

    return render_template('pages/table_row.html',page=page)

