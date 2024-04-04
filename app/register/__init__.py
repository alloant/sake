#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, request
from flask_login import login_required, current_user

from .register import register_view
from .edit_note import edit_note_view, delete_note_view
from .download import download_view
from .inbox import inbox_view
from .tools import get_cr_users

bp = Blueprint('register', __name__)

@bp.route('/',methods=['POST','GET'])
@bp.route('/register',methods=['POST','GET'])
@login_required
def register():
    get_cr_users()
    return register_view(request.form.to_dict(),request.args)

@bp.route('/edit_note', methods=['GET','POST'])
@login_required
def edit_note():
    get_cr_users()
    return edit_note_view(request)

@bp.route('/delete_note', methods=['GET','POST'])
@login_required
def delete_note():
    get_cr_users()
    return delete_note_view(request)

@bp.route('/download', methods=['GET','POST'])
@login_required
def download_note():
    get_cr_users()
    return download_view(request)

@bp.route('/inbox_scr',methods=['POST','GET'])
@login_required
def inbox_scr():
    get_cr_users()
    
    return inbox_view(request)
