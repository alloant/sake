# auth.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required

from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

from sqlalchemy import select

from app import db
from .forms.login import LoginForm, RegistrationForm, UserForm
from .models import User
from app.tools import check_folders_synology

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        user = db.session.scalar(select(User).where(User.alias==form.alias.data))

        if not user or not check_password_hash(user.password,form.password.data):
            flash('User or password is not correct')
            return render_template('auth/auth.html',login=True, form=form)

        login_user(user)
        #check_folders_synology()

        if 'cr' in user.groups:
            return redirect(url_for('register.register',reg='pen_in_'))
        else:
            for gp in user.groups:
                if gp[:3] == 'cl_':
                    break
            
            return redirect(url_for('register.register',reg=f'cl_in_{gp[3:]}'))

    
    return render_template('auth/auth.html',login=True, form=form)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegistrationForm(request.form)
    if request.method == 'POST' and form.validate():
        user = db.session.scalar(select(User).where(User.alias==form.alias.data))
        cipher = Fernet(current_app.config['SECRET_KEY'])
        
        if user:
            if user.password != '':  
                flash('Name user already exists')
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
                        flash('User is not in Synology')
                        return render_template('auth/auth.html', login=False, form=form)
            
                groups = 'Aes-of' if alias[0] == 'of' else alias[1]

            # create new user with the form data. Hash the password so plaintext version isn't saved.
            new_user = User(name=form.name.data,alias=form.alias.data, email=form.email.data, u_groups=groups, password=generate_password_hash(form.password.data), password_nas=cipher.encrypt(str.encode(form.password.data)))

            # add the new user to the database
            db.session.add(new_user)
        
        db.session.commit()

        return redirect(url_for('auth.login'))

    return render_template('auth/auth.html', login=False, form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/edit_user', methods=['GET', 'POST'])
@login_required
def edit_user():
    user_id = request.args.get('user')
    user = db.session.scalars(select(User).where(User.id==user_id)).first()
 
    form = UserForm(request.form,obj=user)

    #form.active.data =  1 if user.active else 0
    #form.admin_active.data = 1 if user.admin_active else 0
    
    if request.method == 'POST' and form.validate():
        user.alias = form.alias.data
        user.name = form.name.data
        user.email = form.email.data
        
        if user.admin:
            user.local_path = form.local_path.data
            user.u_groups = form.u_groups.data
       
            user.active = form.active.data
            user.admin_active = form.admin_active.data

        db.session.commit()

        return redirect(url_for('register.register',reg='lasturl'))
    else:
        form.active.data = user.active
        form.admin_active.data = user.admin_active

    
    
    return render_template('auth/user.html', form=form, user=user)

