# init.py

from flask import Flask, session
from flask_login import LoginManager 
from flask_bootstrap import Bootstrap5

#from flask_admin import Admin

from config import Config

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def create_app(config_class=Config):
    app = Flask(__name__)
    bootstrap = Bootstrap5(app)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate = Migrate(app, db)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # set optional bootswatch theme
    #app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

    #admin = Admin(app, name='sake', template_mode='bootstrap3')
    # Add administrative views here    
    
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprint for auth routes in our app
    from .auth import bp as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from .register import bp as register_blueprint
    app.register_blueprint(register_blueprint)
    
    from .docs import bp as documentation_blueprint
    app.register_blueprint(documentation_blueprint)
    
    return app


