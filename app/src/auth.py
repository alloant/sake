# auth.py
import re

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session, make_response
from flask_login import login_user, logout_user, login_required, current_user

from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

from sqlalchemy import select, and_, or_

from app import db
from app.src.forms.login import LoginForm, RegistrationForm, UserForm
from app.src.models import User, Register

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        user = db.session.scalar(select(User).where(User.alias==form.alias.data))

        if not user or not check_password_hash(user.password,form.password.data):
            flash('User or password is not correct','danger')
            return render_template('auth/auth.html',login=True, form=form)

        login_user(user)

        if session.get('theme') is None:
            session.permanent = True
            session['theme'] = 'light-mode'

        if session.get('version') is None:
            session.permanent = True
            session['version'] = 'old'

        if user.all_registers:
            return redirect(url_for('register.register', reg='all_all_pending', page=1))

        registers = db.session.scalars(select(Register).where(Register.active==1)).all()
        for register in registers:
            if 'subregister' in register.groups:
                for sb in register.get_subregisters():
                    return redirect(url_for('register.register', reg=f'{register.alias}_in_{sb}', page=1))


    return render_template('auth/auth.html',login=True, form=form)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegistrationForm(request.form)
    if request.method == 'POST' and form.validate():
        user = db.session.scalar(select(User).where(User.alias==form.alias.data))
        cipher = Fernet(current_app.config['SECRET_KEY'])
        
        if user:
            if user.password != '':  
                flash('Name user already exists','warning')
                return render_template('auth/auth.html', login=False, form=form)
            
            user.name = form.name.data
            user.alias = form.alias.data
            user.email = form.email.data
            user.password = generate_password_hash(form.password.data,method='scrypt')
            user.password_nas = cipher.encrypt(str.encode(form.password.data))
        else:
            alias = form.alias.data.split(" ")
            groups = ""
            if len(alias) == 2:
                if alias[0] in ['d','sd','sd1','sd2','scl','sacd','of']:
                    ctr = User.query.filter_by(User.alias==alias[1],User.groups.contains('ctr')).first()
                    if not ctr or alias[0] == 'of':
                        flash('User is not in Synology','warning')
                        return render_template('auth/auth.html', login=False, form=form)
            
                groups = 'Aes-of' if alias[0] == 'of' else alias[1]

            # create new user with the form data. Hash the password so plaintext version isn't saved.
            new_user = User(name=form.name.data,alias=form.alias.data, email=form.email.data, u_groups=groups, password=generate_password_hash(form.password.data), password_nas=cipher.encrypt(str.encode(form.password.data)))

            # add the new user to the database
            db.session.add(new_user)
        
        db.session.commit()

        return redirect(url_for('auth.login'))

    return render_template('auth/auth.html', login=False, form=form)

@bp.route('/theme')
@login_required
def theme():
    version = request.args.get('version','')
    if version:
        session['version'] = version
    else:
        session['theme'] = 'light-mode' if session['theme'] == 'dark-mode' else 'dark-mode'
    return redirect('/')
    return redirect(request.referrer)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@bp.route('/users', methods=['GET', 'POST'])
@login_required
def list_users():
    if not ('admin' in current_user.groups or 'scr' in current_user.groups):
        return redirect(request.referrer)
    output = request.form.to_dict()

    if 'search' in output:
        users = db.session.scalars(select(User).where(and_(or_(User.alias.contains(output['search']),User.name.contains(output['search'])),User.u_groups.regexp_match(r'\bsake\b'))).order_by(User.alias))
    else:
        users = db.session.scalars(select(User).where(User.u_groups.regexp_match(r'\bsake\b')).order_by(User.alias))

    return render_template('users/list_users.html', users=users)


@bp.route('/main_users')
@login_required
def main_users():
    if not ('admin' in current_user.groups or 'scr' in current_user.groups):
        return redirect(request.referrer)

    users = db.session.scalars(select(User).where(User.u_groups.regexp_match(r'\bsake\b')).order_by(User.alias))

    return render_template('users/main.html', users=users)


@bp.route('/edit_user', methods=['GET', 'POST'])
@login_required
def edit_user():
    user_id = request.args.get('user')
    user = db.session.scalars(select(User).where(User.id==user_id)).first()
    is_ctr = request.args.get('ctr',False)
 
    form = UserForm(request.form,obj=user)
    
    groups_choices = ['sake','admin','cr','of','despacho','scr','permanente']

    group1 = len(groups_choices)

    registers = db.session.scalars(select(Register).where(and_(Register.active==1,Register.r_groups.regexp_match(r'\bpersonal\b'))))


    for register in registers:
        groups_choices.append(f"{register.alias}")
    
    group2 = len(groups_choices)

    ctrs = db.session.scalars(select(User).where(and_(User.active==1,User.u_groups.regexp_match(r'\bctr\b'))).order_by(User.alias))

    for ctr in ctrs:
        groups_choices.append(f"{ctr.alias}")
    
    group3 = len(groups_choices)
    
    form.groups.choices = [(group,group) for group in groups_choices]

    
    #form.active.data =  1 if user.active else 0
    #form.admin_active.data = 1 if user.admin_active else 0
    if request.method == 'POST':
        user.alias = form.alias.data
        user.name = form.name.data
        user.email = form.email.data
        
        if 'admin' in current_user.groups:
            user.local_path = form.local_path.data
            #user.u_groups = form.u_groups.data
       
            user.active = form.active.data
            user.admin_active = form.admin_active.data

            if 'of' in form.groups.data:
                rst = ['o_cg','o_asr','o_ctr','o_r','o_mat','ct_mat']
            elif 'cr' in form.groups.data:
                rst = ['v_cg','v_asr','v_ctr','v_r','o_mat','ct_mat']
            else:
                rst = []
            
            for group in form.groups.data:
                if group in groups_choices[:group1]:
                    rst.append(group)

                if group in groups_choices[group1:group2]:
                    rst.append(f"e_{group}")

                if group in groups_choices[group2:]:
                    rst.append(f"v_ctr_{group}")
            
            user.u_groups = ",".join([g for g in rst if g])

        db.session.commit()

        if user == current_user:
            res = make_response()
            #res.headers['HX-Refresh'] = True
            res.headers['HX-Redirect'] = "/"
            return res
        else:
            return ""
    else:
        form.active.data = user.active
        form.admin_active.data = user.admin_active
        
        for group in user.groups:
            if group in groups_choices:
                form.groups.data.append(group)
            
            if re.match(fr'e_\w+',group):
                form.groups.data.append(group.split('_')[1])

            if re.match(fr'[veo]_ctr_\w+',group):
                form.groups.data.append(group.split('_')[2])

    
    if 'admin' in current_user.groups or 'scr' in current_user.groups:
        is_admin = True
    else:
        is_admin = False

    return render_template('modals/modal_edit_user.html', form=form, user=user, group1=group1, group2=group2, group3=group3, is_admin=is_admin, is_ctr=is_ctr)


@bp.route('/language')
def set_language(language=None):
    lang = request.args.get('lang')
    session['language'] = lang
    return redirect('/')
    return redirect(request.referrer)


from werkzeug.exceptions import HTTPException

#@bp.errorhandler(Exception)
#def handle_exception(e):
    # pass through HTTP errors
#    if isinstance(e, HTTPException):
#        return e

    # now you're handling non-HTTP exceptions only
#    return render_template("error.html", e=e), 500
