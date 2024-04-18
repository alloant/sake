#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, request, render_template
from flask_login import login_required, current_user

from .register import register_view
from .state_note import state_note_view, read_note_view
from .edit_note import edit_note_view, delete_note_view, edit_receivers_view, edit_receivers_files_view,rec_files_view, sortable_view
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

@bp.route('/edit_receivers_files', methods=['GET','POST'])
@login_required
def edit_receivers_files():
    return edit_receivers_files_view(request)

@bp.route('/sortable', methods=['POST'])
@login_required
def sortable():
    return sortable_view(request)

@bp.route('/rec_files', methods=['GET','POST'])
@login_required
def rec_files():
    return rec_files_view(request)

@bp.route('/edit_receivers', methods=['GET','POST'])
@login_required
def edit_receivers():
    return edit_receivers_view(request)

@bp.route('/receivers_form', methods=['GET','POST'])
@login_required
def receivers_form():
    return receivers_form_view(request)

@bp.route('/edit_note', methods=['GET','POST'])
@login_required
def edit_note():
    get_cr_users()
    return edit_note_view(request)

@bp.route('/state_note', methods=['GET','POST'])
@login_required
def state_note():
    return state_note_view(request)

@bp.route('/read_note', methods=['GET','POST'])
@login_required
def read_note():
    return read_note_view(request)

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

from werkzeug.exceptions import HTTPException

@bp.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    return render_template("error.html", e=e), 500
