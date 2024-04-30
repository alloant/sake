import re

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
        rst = re.findall(r'\b[evo]_[a-z]+_*[a-z0-9]*\b',self.u_groups)
        if len(rst) > 1:
            return True

        return False
