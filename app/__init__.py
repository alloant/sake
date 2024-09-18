# init.py

from flask import Flask, session, request, render_template
from flask_babel import Babel
from flask_login import LoginManager, current_user
from flask_bootstrap import Bootstrap5
from flask_mobility import Mobility
from flask_sock import Sock
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
#from flask_admin.theme import Bootstrap4Theme

from config import Config

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
sock = Sock()
sock_clients = {}


@sock.route('/update_sidebar')
def update_sidebar(ws):
    sock_clients[current_user.alias] = ws

    while True:
        data = ws.receive()
        ws.send(data)

def create_app(config_class=Config):
    app = Flask(__name__)

    sock.init_app(app)
    Mobility(app)
    bootstrap = Bootstrap5(app)
    babel = Babel(app, locale_selector=get_locale)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate = Migrate(app, db)
    
#    with app.app_context():
#        db.create_all()
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)


    from app.src.models import User, Note
    #admin = Admin(app, name='sake', template_mode='bootstrap4')
    # Add administrative views here    
    admin = Admin(app, name='sake')
    admin.add_view(ModelView(User, db.session))
    admin.add_view(ModelView(Note, db.session))   
    

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprint for auth routes in our app
    from app.src.auth import bp as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from app.src.notes import bp as notes_blueprint
    app.register_blueprint(notes_blueprint)
    
    from app.src.docs import bp as documentation_blueprint
    app.register_blueprint(documentation_blueprint)
    
    return app

#@babel.localeselector
def get_locale():
    # if the user has set up the language manually it will be stored in the session,
    # so we use the locale from the user settings
    try:
        language = session['language']
    except KeyError:
        language = None
    if language is not None:
        return language
    return request.accept_languages.best_match(['en','ja'])
