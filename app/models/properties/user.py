import re
from sqlalchemy import case, and_, or_, not_, select, type_coerce, literal_column, func, union
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method


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

