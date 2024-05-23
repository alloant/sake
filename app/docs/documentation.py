#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template

from sqlalchemy import select

from app import db
from app.models import Register

def documentation_view(args):
    topic = args.get('topic')

    registers = db.session.scalars(select(Register).where(Register.active==1)).all()
    match topic:
        case 'cr':
            return render_template('docs/cr.html', registers=registers)
        case 'cl_in':
            return render_template('docs/cl_inbox.html', registers=registers)
        case 'cl_out':
            return render_template('docs/cl_outbox.html', registers=registers)
        case 'config':
            return render_template('docs/registration.html', registers=registers)
        case _:
            return render_template('docs/main.html', registers=registers)

