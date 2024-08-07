#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, request, render_template, current_app
from flask_login import login_required, current_user
from flask_mobility.decorators import mobile_template

from app.src.notes.views import main_body_view, body_table_view, note_row_view, register_icon_view, action_note_view, table_body_view
from app.src.notes.edit import state_note_view, read_note_view, edit_receivers_view, edit_receivers_files_view, sortable_view, edit_tags_view, browse_files_view, files_view, update_files_view, reply_note_view, get_files_view, open_file_view, load_socket_view
from app.src.tools.download import download_view
from app.src.main import  dashboard_view
from app.src.inbox.inbox import inbox_body_view, inbox_main_view, action_inbox_view

bp = Blueprint('register', __name__)

@bp.route('/flash')
@login_required
def flash():
    return render_template('flash.html')

@bp.route('/',methods=['POST','GET'])
#@mobile_template("register/{mobile/}main.html")
@mobile_template("main.html")
@login_required
def register(template):
    return dashboard_view(request)

@bp.route('/table_body')
@login_required
def table_body():
    return table_body_view(request)

@bp.route('/action_note',methods=['GET','POST'])
@login_required
def action_note():
    return action_note_view(request)

@bp.route('/load_socket')
@login_required
def load_socket():
    return load_socket_view(request)

@bp.route('/action_inbox',methods=['GET','POST'])
@login_required
def action_inbox():
    return action_inbox_view(request)

@bp.route('/main_body')
@login_required
def main_body():
    return main_body_view(request)

@bp.route('/body_table',methods=['GET','POST'])
@login_required
def body_table():
    return body_table_view(request)

@bp.route('/note_row')
@login_required
def note_row():
    return note_row_view(request)

@bp.route('/register_icon')
@login_required
def register_icon():
    return register_icon_view(request)

@bp.route('/update_files', methods=['GET','POST'])
@login_required
def update_files():
    return update_files_view(request)

@bp.route('/browse_files', methods=['GET','POST'])
@login_required
def browse_files():
    return browse_files_view(request)

@bp.route('/get_files', methods=['GET','POST'])
@login_required
def get_files():
    return get_files_view(request)

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

@bp.route('/edit_tags', methods=['GET','POST'])
@login_required
def edit_tags():
    return edit_tags_view(request)

@bp.route('/edit_receivers', methods=['GET','POST'])
@login_required
def edit_receivers():
    return edit_receivers_view(request)

@bp.route('/reply_note', methods=['GET','POST'])
@login_required
def reply_note():
    return reply_note_view(request)

@bp.route('/state_note', methods=['GET','POST'])
@login_required
def state_note():
    return state_note_view(request)

@bp.route('/read_note', methods=['GET','POST'])
@login_required
def read_note():
    return read_note_view(request)

@bp.route('/open_file', methods=['GET','POST'])
@login_required
def open_file():
    return open_file_view(request)

@bp.route('/download', methods=['GET','POST'])
@login_required
def download_note():
    return download_view(request)

@bp.route('/inbox_body',methods=['POST','GET'])
@login_required
def inbox_scr():
    return inbox_main_view(request)

from werkzeug.exceptions import HTTPException

@bp.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e

    # now you're handling non-HTTP exceptions only
    return render_template("error.html", e=e), 500
