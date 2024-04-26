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
        if 'cr' in self.groups:
            return True
        elif len([g for g in self.groups if 'cl_' in g]) > 1:
            return True

        return False
