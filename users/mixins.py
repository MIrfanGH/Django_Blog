from django.contrib.auth.mixins import UserPassesTestMixin

class RoleRequiredMixin(UserPassesTestMixin):    # for RBAC feature 
    required_role = None  

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.profile.role == self.required_role


class AuthorRequiredMixin(RoleRequiredMixin):
    required_role = 'Author'


class AdminRequiredMixin(RoleRequiredMixin):
    required_role = 'Admin'
