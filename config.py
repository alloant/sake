import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    DEBUG= os.environ.get('DEBUG')
    SYNOLOGY_SERVER= os.environ.get('SYNOLOGY_SERVER')
    SYNOLOGY_PORT= os.environ.get('SYNOLOGY_PORT')
    SYNOLOGY_FOLDER_NOTES= os.environ.get('SYNOLOGY_FOLDER_NOTES')
    EMAIL_ADDRESS= os.environ.get('EMAIL_ADDRESS')
    EMAIL_SECRET= os.environ.get('EMAIL_SECRET')
    EMAIL_CARDUMEN_USER= os.environ.get('EMAIL_CARDUMEN_USER')
    EMAIL_CARDUMEN_SERVER= os.environ.get('EMAIL_CARDUMEN_SERVER')
    EMAIL_CARDUMEN_SECRET= os.environ.get('EMAIL_CARDUMEN_SECRET')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')\
        or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_size': 20}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LANGUAGES = ['en','ja','es']
    SOCK_SERVER = os.environ.get('SOCK_SERVER')
    PATH_PEM = os.environ.get('PATH_PEM')\
        or '/cert'

