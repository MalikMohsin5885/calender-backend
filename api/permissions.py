# api/permissions.py
def user_has_permission(user, perm):
    return perm in user.get_permissions()
