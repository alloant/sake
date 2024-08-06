#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, session, current_app


def dashboard_view(request):
    return render_template('main.html',sock_server = current_app.config['SOCK_SERVER'])



