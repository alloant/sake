from synology_drive_api.drive import SynologyDrive
from synochat.webhooks import IncomingWebhook

from tempfile import NamedTemporaryFile

import time
import logging
from pathlib import Path

from flask import current_app, flash
from flask_login import current_user

from cryptography.fernet import Fernet


INV_EXT = {'osheet':'xlsx','odoc':'docx'}
EXT = {'xls':'osheet','xlsx':'osheet','docx':'odoc','rtf':'odoc'}

def wrap_error(func, *args):
    try:
        USER = current_user.alias

        cipher = Fernet(current_app.config['SECRET_KEY'])
        #print("!@#!@#!@#",cipher.decrypt(""))
        PASSWD = cipher.decrypt(current_user.get_setting('password_nas'))

        
        if current_app.config['DEBUG'] == 'True':
            server = current_app.config['SYNOLOGY_SERVER']
        else:
            server = "127.0.0.1"
        
        with SynologyDrive(USER,PASSWD,server,dsm_version='7',https=True) as synd:
            return func(synd,*args)
        flash('The connection to Synology fail. If this keeps happening maybe your username or password is not the same as in Synology','danger')
        return None
    except Exception as err:
        if type(err).__name__ == 'SynologyException':
            message = f"Synology error: {err.message} in {func.__name__} with parameters {args}"
        else:
            message = f"{err} in {func.__name__} with parameters {args}"
        
        logging.warning(message)
        #if current_app.config['DEBUG']:
        #flash(message)
        #raise   


# Wrapped functions
def preview(link):
    return wrap_error(_preview,link)

def toggle_share_permissions(path:str,role):
    return wrap_error(_toggle_share_permissions,path,role)

def files_path(path:str):
    return wrap_error(_files_path,path)

def delete_path(path:str):
    return wrap_error(_delete_path,path)

def rename_path(path:str,new_name:str):
    return wrap_error(_rename_path,new_name,path)

def get_info(path:str,attr:str=None):
    return wrap_error(_get_info,path,attr)

def move_path(path:str,dest:str):
    return wrap_error(_move_path,path,dest)

def copy_path(path:str,dest:str):
    return wrap_error(_copy_path,path,dest)

def copy_office_path(path:str,dest:str):
    return wrap_error(_copy_office_path,path,dest)

def convert_office(path:str,delete:bool = False):
    return wrap_error(_convert_office,path,delete)

def download_path(path:str,dest=None):
    return wrap_error(_download_path,path,dest)

def upload_path(path:str,dest:str):
    return wrap_error(_upload_path,path,dest)

def create_folder(path:str,folder:str):
    return wrap_error(_create_folder,path,folder)

def upload_register(wb,name,dest):
    return wrap_error(_upload_register,name,dest)

def create_task(cal_id:str,summary:str):
    return wrap_error(_create_task,cal_id,summary)

# Original functions

def _preview(synd,link):
    return synd.preview(link)

def _toggle_share_permissions(synd,path,role):
    return synd.toggle_share_permissions(path,role)

def _files_path(synd,path):
    if path == "/team-folders":
        teams = []
        for team,id_team in synd.get_teamfolder_info().items():
            teams.append({'name':team,'display_path':f"/team-folders/{team}","id":id_team,'type':'dir','permanent_link':''})
        return  teams
    return synd.list_folder(path)['data']['items']

def _delete_path(synd,path):
    return synd.delete_path(path)

def _rename_path(synd,new_name,path):
    return synd.rename_path(new_name,path)

def _get_info(synd,path,attr):
    info =  synd.get_file_or_folder_info(path)
    
    if attr and 'data' in info and attr in info['data']:
        if attr in info['data']:
            return info['data'][attr]

    return info

def _move_path(synd,path,new_path):
    rst = synd.move_path(path,new_path)
    task_id = rst['data']['async_task_id']

    rst = synd.get_task_status(task_id)

    while(rst['data']['result'][0]['data']['progress'] < 100 or rst['data']['has_fail']):
        time.sleep(0.2)
        rst = synd.get_task_status(task_id)

    rst_data = rst['data']['result'][0]['data']['result']

    if not 'targets' in rst_data:
        logging.error(f'Synology cannot move the file {path} to {new_path}')
        return None
    else:
        if 'error' in rst_data['targets']:
            logging.error(rst_data['targets']['error'])
            return None
        else:
            return {'id':rst_data['targets'][0]['file_id'],'path':new_path}

def _copy_office_path(synd,path,dest):
    rst = synd.copy_office(path,dest)

def _copy_path(synd,path,dest):
    rst = synd.copy(path,dest)
    #if 'data' in rst:
    #    if 'async_task_id'in rst['data']:
    #        rst = synd.get_file_or_folder_info(dest)
    return rst

def _convert_office(synd,path,delete=False):
    rst = synd.convert_to_online_office(path,delete_original_file=delete)
    task_id = rst['data']['async_task_id']
    
    rst = synd.get_task_status(task_id)
    while(not rst['data']['has_fail'] and rst['data']['result'][0]['data']['status'] == 'in_progress'):
        time.sleep(1)
        rst = synd.get_task_status(task_id)
   
    ext = path.split(".")[-1]
    path = path.split(".")[:-1]

    #ext = 'odoc' if ext in ['doc','docx'] else 'osheet'

    path = ".".join(path+[EXT[ext]])
    
    new_file = synd.get_file_or_folder_info(path)
    new_file_id = new_file['data']['file_id']
    new_permanent_link = new_file['data']['permanent_link']
    new_file_path = new_file['data']['display_path']

    return {'path':new_file_path, 'fid': new_file_id, 'link': new_permanent_link}

def _download_path(synd,path,dest):
    if not path.isdigit():
        #name = get_info(path,attr='name')
        name = path.split('/')[-1]
    else:
        name = Path(path).name

    ext = Path(name).suffix[1:]

    # Could be a synology file or not
    if ext in INV_EXT:
        ext = INV_EXT[ext]
        bio = synd.download_synology_office_file(path)
    else:
        bio = synd.download_file(path)
    
    # I could save it in dest or return the bytes
    if dest:
        with open(f'{dest}/{Path(name).stem}.{ext}','wb') as f:
            f.write(bio.read())
            return True
        return False
    else:
        return bio
    

def _upload_path(synd,file,dest):
    return synd.upload_file(file, dest_folder_path=dest)

def _create_folder(synd,path,folder):
    print('Starting folder',path)
    files = files_path(path)
    
    folder_exists = False
    for fl in files:
        if fl['name'] == folder:
            folder_exists = True
            break
    
    if folder_exists:
        folder_info = synd.get_file_or_folder_info(f"{path}/{folder}")['data']
        folder_id = folder_info['file_id']
        p_link = folder_info['permanent_link']
    else:
        print('creating:',folder,path)
        rst = synd.create_folder(folder,path)
        
        if rst:
            if 'permanent_link' in rst:
                self.permanent_link = rst['permanent_link']
                
        folder_id = rst['data']['file_id']
        p_link = rst['data']['permanent_link']

    return {'id':folder_id,'permanent_link':p_link}


def send_message(rec,RECIPIENTS,message):
    try:
        webhook = IncomingWebhook(current_app.config['SYNOLOGY_SERVER'], RECIPIENTS[rec]['token'], port=5001)
        webhook.send(message)
        return True
    except Exception as err:
        logging.error(err)
        logging.error(f"Cannot send message to {rec}")
        return False

def _create_task(synd,cal_id,summary):
    synd.create_task(cal_id,summary)
