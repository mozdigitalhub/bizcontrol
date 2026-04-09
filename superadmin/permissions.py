def is_platform_superadmin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name="SuperAdmin").exists()
