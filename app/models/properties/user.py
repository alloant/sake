import re
from sqlalchemy import case, and_, or_, not_, select, type_coerce, literal_column, func, union
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method

from flask import session
from xml.etree import ElementTree as ET

from flask_babel import gettext


class UserProp(object):
    @property
    def groups(self):
        return self.u_groups.split(',') if self.u_groups else []

    @property
    def admin(self):
        if 'admin' in self.groups and self.admin_active:
            return True
        return False

    @property
    def fullName(self):
        rst = f"{self.alias}"
        if self.name: rst = f"{rst} - {self.name}"
        if self.description: rst = f"{rst} ({self.description})"

        return rst

    @property
    def severalCalendars(self):
        rst = re.findall(r'\b[evo]_[a-z]+_*[A-Za-z0-9-]*\b',self.u_groups)
        if len(rst) > 1:
            return True

        return False

    @hybrid_method
    def contains_group(cls,group):
        return cls.u_groups.regexp_match(fr'(^|[^-])\b{group}\b($|[^-])')

    def register_icon_html(self,register, size=35):
        match register:
            case 'pendings':
                href = '/register?reg=all_all_pending'
                title = gettext('Pending')
            case 'minutas':
                href = '/register?reg=mat_all_'
                title = gettext('Matters')
            case 'register':
                href = '#'
                title = gettext('Register')
            case 'despacho':
                href = '/register?reg=des_in_'
                title = gettext('Despacho')
            case 'inbox':
                href = '/register?reg=inbox_scr'
                title = gettext('Inbox')
            case 'outbox':
                href = '/register?reg=box_out_'
                title = gettext('Outbox')

        dark = f'-dark' if session['theme'] == 'dark-mode' else ''

        if register == 'register':
            #<a href="#" class="d-flex align-items-center justify-content-center link-light text-decoration-none py-1 py-lg-3 px-1" id="dropdownRegister" data-bs-toggle="dropdown" aria-expanded="false">
            a = ET.Element('a',attrib={'class':'text-decoration-none','href':href,'data-bs-toggle':'tooltip','data-bs-placement':'right','data-bs-original-title':title})
            a.attrib['id'] = "dropdownRegister"
            a.attrib['data-bs-toggle'] = "dropdown"
            a.attrib['aria-expanded'] = "false"
            
        else:
            a = ET.Element('a',attrib={'class':'position-relative text-decoration-none','href':href,'data-bs-toggle':'tooltip','data-bs-placement':'right','data-bs-original-title':title})
       
        if register == 'pendings' and self.has_pendings:
            dark += '-red'
        elif register == 'minutas':
            mats = self.pending_matters
            if mats > 0:
                sp = ET.Element('span',attrib={'class':'position-absolute top-0 start-50 translate-middle badge bg-danger','style':'font-size: 1vmin'})
                sp.text = str(mats)
                a.append(sp)

        
        img = ET.Element('img',attrib={'class':'mb-lg-4 mb-sm-1 me-sm-1','src':f'static/icons/00-{register}{dark}.svg','width':f'{size}vmin','height':f'{size}vmin'})
        a.append(img)

        return ET.tostring(a,encoding='unicode',method='html')

