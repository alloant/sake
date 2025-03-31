# auth.py
import re

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session, make_response
from flask_login import login_user, logout_user, login_required, current_user

from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

from sqlalchemy import select, and_, or_

from app import db
from app.src.forms.login import LoginForm, RegistrationForm, UserForm
from app.src.models import User, Register, Group

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        user = db.session.scalar(select(User).where(User.alias==form.alias.data))

        if not user or not check_password_hash(user.get_setting('password'),form.password.data):
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
            #return redirect(url_for('register.register', reg='all_all_pending', page=1))
            return redirect(url_for('register.register'))

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
            if user.get_setting('password') != '':  
                flash('Name user already exists','warning')
                return render_template('auth/auth.html', login=False, form=form)
            
            user.name = form.name.data
            user.alias = form.alias.data
            user.email = form.email.data
            user.set_setting('password',generate_password_hash(form.password.data,method='scrypt'))
            user.set_setting('password_nas',cipher.encrypt(str.encode(form.password.data)))

        else:
            alias = form.alias.data.split(" ")
            groups = ""
            if len(alias) == 2:
                if alias[0] in ['d','sd','sd1','sd2','scl','sacd','of']:
                    ctr = User.query.filter_by(User.alias==alias[1],User.groups.contains('ctr')).first()
                    if not ctr or alias[0] == 'of':
                        flash('User is not in Synology','warning')
                        return render_template('auth/auth.html', login=False, form=form)
            
                category = 'of' if alias[0] == 'of' else 'cl'

            new_user = User(name=form.name.data,alias=form.alias.data, email=form.email.data, category=category)
            
            # add the new user to the database
            db.session.add(new_user)
            
            new_user.set_setting('password',generate_password_hash(form.password.data,method='scrypt'))
            new_user.set_setting('password_nas',cipher.encrypt(str.encode(form.password.data)))
 
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
    is_ctr = True if request.args.get('ctrs','false') == 'true' else False
    if not ('admin' in current_user.groups or 'scr' in current_user.groups):
        return redirect(request.referrer)
    output = request.form.to_dict()
    if is_ctr:
        gps = ['ctr']
    else:
        gps = ['dr','of','cl']

    if 'search' in output:
        users = db.session.scalars(select(User).where(and_(or_(User.alias.contains(output['search']),User.name.contains(output['search'])),User.category.in_(gps))).order_by(User.alias))
    else:
        users = db.session.scalars(select(User).where(User.category.in_(gps)).order_by(User.alias))

    return render_template('users/list_users.html', users=users)


@bp.route('/main_users')
@login_required
def main_users():
    is_ctr = True if request.args.get('ctrs','false') == 'true' else False

    if not ('admin' in current_user.groups or 'scr' in current_user.groups):
        return redirect(request.referrer)
    
    if is_ctr:
        users = db.session.scalars(select(User).where(User.category=='ctr').order_by(User.alias))
        title_page = "Ctrs"
        ctrs = "true"
    else:
        users = db.session.scalars(select(User).where(User.category.in_(['dr','of'])).order_by(User.alias))
        title_page = "Users"
        ctrs = "false"

    return render_template('users/main.html', users=users, title_page=title_page, ctrs=ctrs)


@bp.route('/edit_user', methods=['GET', 'POST'])
@login_required
def edit_user():
    user_id = request.args.get('user')
    print('kk',user_id)
    if isinstance(user_id,int):
        user = db.session.scalars(select(User).where(User.id==user_id)).first()
    elif isinstance(user_id,str):
        if user_id.isdigit():
            user = db.session.scalars(select(User).where(User.id==int(user_id))).first()
        else:
            user = db.session.scalars(select(User).where(User.alias==user_id)).first()
    
    is_ctr = request.args.get('is_ctr',False)
 
    form = UserForm(request.form,obj=user)
   
    if user.category == 'ctr':
        groups = db.session.scalars(select(Group).where(Group.category=='ctr')).all()
    else:
        groups = db.session.scalars(select(Group).where(Group.category=='user')).all()
    form.groups.choices = [group.text for group in groups]

    registers = db.session.scalars(select(Register).where(Register.active==1,Register.groups.any(Group.text=='personal'))).all()
    form.registers.choices = [register.alias for register in registers]

    ctrs = db.session.scalars(select(User).where(and_(User.active==1,User.category=='ctr')).order_by(User.alias)).all()
    form.ctrs.choices = [ctr.alias for ctr in ctrs]

    print('here:',request.method)
    if request.method == 'POST':
        print('post')
        user.alias = form.alias.data
        user.name = form.name.data
        user.email = form.email.data
        
        if 'admin' in current_user.groups:
            user.local_path = form.local_path.data
            
            if 'admin' in current_user.groups:
                user.active = form.active.data
                if user.category != 'ctr':
                    user.admin_active = form.admin_active.data
            
            
            for group in form.groups.choices:
                if group in form.groups.data:
                    user.add_group(group)
                else:
                    user.del_group(group)

            for register in registers:
                if register.alias in form.registers.data:
                    register.set_user_access('editor',user)
                else:
                    register.set_user_access('',user)
            
            for ctr in ctrs:
                if ctr.alias in form.ctrs.data:
                    if not ctr in user.ctrs:
                        user.ctrs.append(ctr)
                else:
                    if ctr in user.ctrs:
                        user.ctrs.remove(ctr)

            if form.notifications_active.data:
                user.set_setting('notifications',True)
            else:
                user.set_setting('notifications',False)

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
            form.groups.data.append(group.text)
        
        for register in registers:
            if register.get_user_access(user) == 'editor':
                form.registers.data.append(register.alias)
        
        for ctr in ctrs:
            if ctr in user.ctrs:
                form.ctrs.data.append(ctr.alias)

        if user.get_setting('notifications'):
            form.notifications_active.data = True

    
    if 'admin' in current_user.groups or 'scr' in current_user.groups:
        is_admin = True
    else:
        is_admin = False
     
    return render_template('modals/modal_edit_user.html', form=form, user=user, is_admin=is_admin, is_ctr=is_ctr)


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
