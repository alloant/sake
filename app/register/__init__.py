#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, request, render_template
from flask_login import login_required, current_user
from flask_mobility.decorators import mobile_template

from .register import register_view, notes_view
from .state_note import state_note_view, read_note_view, note_people_view, note_files_view
from .edit_note import edit_note_view, delete_note_view, edit_receivers_view, edit_receivers_files_view,rec_files_view, sortable_view, edit_tags_view, browse_files_view, files_view, update_files_view, reply_note_view
from .download import download_view
from .inbox import inbox_view

bp = Blueprint('register', __name__)

@bp.route('/',methods=['POST','GET'])
@bp.route('/register',methods=['POST','GET'])
#@mobile_template("register/{mobile/}main.html")
@mobile_template("register/main.html")
@login_required
def register(template):
    return register_view(template,request.form.to_dict(),request.args)


@bp.route('/note_people')
@login_required
def note_people():
    return note_people_view(request)

@bp.route('/note_files')
@login_required
def note_files():
    return note_files_view(request)


@bp.route('/notes')
@login_required
def notes():
    return notes_view(request.form.to_dict(),request.args)

@bp.route('/update_files', methods=['GET','POST'])
@login_required
def update_files():
    return update_files_view(request)

@bp.route('/browse_files', methods=['GET','POST'])
@login_required
def browse_files():
    return browse_files_view(request)

@bp.route('/files', methods=['GET'])
@login_required
def files():
    return files_view(request)

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

@bp.route('/edit_tags', methods=['GET','POST'])
@login_required
def edit_tags():
    return edit_tags_view(request)

@bp.route('/edit_receivers', methods=['GET','POST'])
@login_required
def edit_receivers():
    return edit_receivers_view(request)

@bp.route('/receivers_form', methods=['GET','POST'])
@login_required
def receivers_form():
    return receivers_form_view(request)

@bp.route('/reply_note', methods=['GET','POST'])
@login_required
def reply_note():
    return reply_note_view(request)

@bp.route('/edit_note', methods=['GET','POST'])
@login_required
def edit_note():
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
    return delete_note_view(request)

@bp.route('/download', methods=['GET','POST'])
@login_required
def download_note():
    return download_view(request)

@bp.route('/inbox_scr',methods=['POST','GET'])
@login_required
def inbox_scr():
    return inbox_view(request)

from werkzeug.exceptions import HTTPException

@bp.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    return render_template("error.html", e=e), 500
