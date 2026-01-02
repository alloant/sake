from synology_drive_api.drive import SynologyDrive
from synochat.webhooks import IncomingWebhook

from tempfile import NamedTemporaryFile

import time
import logging
from pathlib import Path

from libsynomail import EXT, INV_EXT

def init_connection(user,passwd):
    global USER
    USER = user
    
    global PASSWD
    PASSWD = passwd

def wrap_error(func, *args):
    try:
        with SynologyDrive(USER,PASSWD,"nas.prome.sg",dsm_version='7') as synd:
            return func(synd,*args)
        return None
    except Exception as err:
        if type(err).__name__ == 'SynologyException':
            message = f"Synology error: {err.message} in {func.__name__} with parameters {args}"
        else:
            message = f"{err} in {func.__name__} with parameters {args}"
        logging.warning(message)


# Wrapped functions

def get_teams():
    return wrap_error(_get_teams)

def files_path(path:str):
    return wrap_error(_files_path,path)

def rename_path(path:str,new_name:str):
    return wrap_error(_rename_path,new_name,path)

def get_info(path:str,attr:str=None):
    return wrap_error(_get_info,path,attr)

def move_path(path:str,dest:str):
    return wrap_error(_move_path,path,dest)

def copy_path(path:str,dest:str):
    return wrap_error(_copy_path,path,dest)

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

def _get_teams(synd):
    return list(synd.get_teamfolder_info().keys())

def _files_path(synd,path):
    return synd.list_folder(path)['data']['items']

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


def _copy_path(synd,path,dest):
    #if path.isdigit(): path = f"id:{path}"
    #if Path(dest).suffix[1:] in INV_EXT:
    #    return synd.copy(path,dest)
    #else:
    #    return synd.copy_drive(path,dest)
    return synd.copy(path,dest)


def _convert_office(synd,path,delete):
    rst = synd.convert_to_online_office(path,delete_original_file=delete)
    task_id = rst['data']['async_task_id']
    
    rst = synd.get_task_status(task_id)
    while(not rst['data']['has_fail'] and rst['data']['result'][0]['data']['status'] == 'in_progress'):
        time.sleep(1)
        rst = synd.get_task_status(task_id)
    
    
    file_path = synd.get_file_or_folder_info(path)['data']['display_path'] 
    ext = Path(file_path).suffix[1:]
    name = file_path.replace(ext,EXT[ext])

    new_file = synd.get_file_or_folder_info(name)
    new_file_id = new_file['data']['file_id']
    new_permanent_link = new_file['data']['permanent_link']
    new_file_path = new_file['data']['display_path']

    return {'name':Path(name).name,'path':new_file_path,'id':new_file_id,'permanent_link':new_permanent_link}

def _download_path(synd,path,dest):
    if not path.isdigit():
        name = get_info(path,attr='name')
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
        rst = synd.create_folder(folder,path)

        folder_id = rst['data']['file_id']
        p_link = rst['data']['permanent_link']

    return {'id':folder_id,'permanent_link':p_link}


def send_message(rec,RECIPIENTS,message):
    try:
        webhook = IncomingWebhook('nas.prome.sg', RECIPIENTS[rec]['token'], port=5001)
        webhook.send(message)
        return True
    except Exception as err:
        logging.error(err)
        logging.error(f"Cannot send message to {rec}")
        return False

def _create_task(synd,cal_id,summary):
    synd.create_task(cal_id,summary)
