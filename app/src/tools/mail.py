#!/usr/bin/env python
# -*- coding: utf-8 -*-

import smtplib
from email.mime.text import MIMEText

from config import Config

def send_email(subject, body, recipients):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = Config.EMAIL_ADDRESS
    msg['To'] = recipients
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(Config.EMAIL_ADDRESS, Config.EMAIL_SECRET)
       smtp_server.sendmail(Config.EMAIL_ADDRESS, recipients, msg.as_string())

