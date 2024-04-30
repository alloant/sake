#!/usr/bin/env python
# -*- coding: utf-8 -*-

from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.models.note import Note
from app.models.user import User
from app import db


