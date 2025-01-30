#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ast

from flask import Blueprint, request, render_template, current_app, session
from flask_login import login_required, current_user
from flask_mobility.decorators import mobile_template

from app.src.pages.views import list_pages_view, page_view
from app.src.pages.actions import pages_action

bp = Blueprint('pages', __name__)


# Main body
@bp.route('/list_pages')
@login_required
def list_pages():
    return list_pages_view(request)

@bp.route('/page/<int:page_id>')
@login_required
def view_page(page_id):
    return page_view(page_id)


@bp.route('/action_page',methods=['GET','POST'])
@login_required
def action_page():
    return pages_action(request)

@bp.route('/edit_page',methods=['GET','POST'])
@login_required
def edit_page():
    pass

from werkzeug.exceptions import HTTPException

#@bp.errorhandler(Exception)
#def handle_exception(e):
    # pass through HTTP errors
#    if isinstance(e, HTTPException):
#        return e

    # now you're handling non-HTTP exceptions only
#    return render_template("error.html", e=e), 500
