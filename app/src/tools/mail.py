#!/usr/bin/env python
# -*- coding: utf-8 -*-

import smtplib
from email.mime.text import MIMEText

import threading

from config import Config

def send_email(subject, body, recipients):
    print('send_email')
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = Config.EMAIL_ADDRESS
    msg['To'] = recipients
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(Config.EMAIL_ADDRESS, Config.EMAIL_SECRET)
       smtp_server.sendmail(Config.EMAIL_ADDRESS, recipients, msg.as_string())

def send_emails(nt,kind='to ctr',targets=[]):
    # Start the background task
    thread = threading.Thread(target=send_emails_threading,args=(nt,kind,targets))
    thread.start()

def send_emails_threading(nt,kind,targets):
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(Config.EMAIL_ADDRESS, Config.EMAIL_SECRET)
        for rec in nt.receiver:
            if kind in ['from despacho','proposal'] and not rec.get_setting('notifications'):
                continue

            if targets and not rec in targets:
                continue
            if rec.email:
                msg = MIMEText("")
                if kind == 'to ctr':
                    msg['Subject'] = f"New mail for {rec.alias} ({nt.fullkey})"
                elif kind == 'from despacho':
                    msg['Subject'] = f"A new note ({nt.fullkey}) has been assgined to you ({rec.alias})"
                elif kind == 'proposal':
                    msg['Subject'] = f"You ({rec.alias}) have a new proposal pending ({nt.fullkey})"
                elif kind in ['approved','denied']:
                    msg['Subject'] = f"Your proposal ({nt.fullkey}) has been ({kind})"
                else:
                    msg['Subject'] = ""
                msg['From'] = Config.EMAIL_ADDRESS
                msg['To'] = rec.email
                
       
                for mail in rec.email.replace(' ','').split(','):
                    smtp_server.sendmail(Config.EMAIL_ADDRESS, mail, msg.as_string())

