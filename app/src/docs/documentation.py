#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template

from sqlalchemy import select

from app import db
from app.src.models import Register

def documentation_view(args):
    topic = args.get('topic')

    match topic:
        case 'cr':
            return render_template('docs/cr.html')
        case 'cl_in':
            return render_template('docs/cl_inbox.html')
        case 'cl_out':
            return render_template('docs/cl_outbox.html')
        case 'config':
            return render_template('docs/registration.html')
        case _:
            return render_template('docs/main.html')

