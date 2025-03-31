#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ast

from flask import Blueprint, request, render_template, current_app, session
from flask_login import login_required, current_user
from flask_mobility.decorators import mobile_template

from app.src.notes.actions import action_note_view
from app.src.notes.renders import render_main_title_body, render_main_body, get_body_data, render_sidebar
from app.src.notes.views import table_body_view, browse_files_modal
from app.src.notes.edit import edit_receivers_view, edit_receivers_files_view, sortable_view, edit_tags_view, files_view, reply_note_view, get_files_view, load_socket_view
from app.src.main import dashboard_view
from app.src.inbox.inbox import inbox_body_view, inbox_main_view, action_inbox_view, marked_files_deletion_view
from app.src.notes.renders import render_body_element

from app.src.tools.syneml import read_eml, write_report_eml

bp = Blueprint('register', __name__)

@bp.route('/flash')
@login_required
def flash():
    return render_template('flash.html')

# Main
@bp.route('/',methods=['POST','GET'])
@mobile_template("{mobile/}main.html")
#@mobile_template("main.html")
@login_required
def register(template):
    return dashboard_view(template)

# Main bar

# Main title


# Main body
@bp.route('/main_title_body')
@mobile_template("{mobile/}notes/main.html")
@login_required
def main_title_body(template):
    return render_main_title_body(request,template)


@bp.route('/main_body',methods=['GET','POST'])
@mobile_template("{mobile}")
@login_required
def main_body(template):
    return render_main_body(request,template)


@bp.route('/action_note',methods=['GET','POST'])
@mobile_template("{mobile}")
@login_required
def action_note(template):
    return action_note_view(request,template)

@bp.route('/load_socket')
@login_required
def load_socket():
    return load_socket_view(request)

# Information

@bp.route('/body_data')
@login_required
def body_data():
    info = request.args.get('info')
    return get_body_data(info)

# Actions

@bp.route('/action_inbox',methods=['GET','POST'])
@login_required
def action_inbox():
    return action_inbox_view(request)

@bp.route('/notes')
@login_required
def notes():
    get = request.args.get('get')
    if get == 'title':
        return render_template('mobile/title.html')

@bp.route('/body_element', methods=['GET','POST'])
@mobile_template("{mobile}")
@login_required
def body_element(template):
    reg = ast.literal_eval(request.args.get('reg'))
    note_id = request.args.get('note')
    element = request.args.get('element')
    return render_body_element(reg,note_id,element,template)
    irint('here',note_id)

@bp.route('/register_icon')
@login_required
def register_icon():
    return register_icon_view(request)


@bp.route('/browse_files', methods=['GET','POST'])
@login_required
def browse_files():
    return browse_files_modal(request)

@bp.route('/sidebar')
@mobile_template("{mobile/}")
@login_required
def sidebar(template):
    element = request.args.get('element')
    return render_sidebar(element,template)

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

@bp.route('/download_report', methods=['GET','POST'])
@login_required
def download_report():
    return write_report_eml(session['eml']['body'],session['eml']['dates'],session['eml']['path'])

@bp.route('/inbox_body',methods=['POST','GET'])
@login_required
def inbox_scr():
    return inbox_main_view(request)

@bp.route('/marked_files_deletion',methods=['POST','GET'])
@login_required
def marked_files_deletion():
    session['reg'] = ['marked','files','']
    return marked_files_deletion_view(request)

from werkzeug.exceptions import HTTPException

#@bp.errorhandler(Exception)
#def handle_exception(e):
    # pass through HTTP errors
#    if isinstance(e, HTTPException):
#        return e

    # now you're handling non-HTTP exceptions only
#    return render_template("error.html", e=e), 500
