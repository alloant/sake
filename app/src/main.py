#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, session

from sqlalchemy import select

from app import db
from app.src.models import Register


def dashboard_view(request):
    registers = db.session.scalars(select(Register).where(Register.active==1)).all()
    return render_template('main.html', registers=registers)



