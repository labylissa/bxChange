"""Role hierarchy constants and permission definitions."""

ROLE_LEVEL: dict[str, int] = {
    "super_admin": 4,
    "admin": 3,
    "developer": 2,
    "viewer": 1,
}

# What each role is allowed to do — used for documentation and guard logic
ROLE_PERMISSIONS: dict[str, dict[str, bool]] = {
    "super_admin": {
        "manage_tenants": True,
        "manage_all_users": True,
        "impersonate": True,
        "manage_own_tenant_users": True,
        "manage_connectors": True,
        "view_logs": True,
        "write": True,
    },
    "admin": {
        "manage_tenants": False,
        "manage_all_users": False,
        "impersonate": False,
        "manage_own_tenant_users": True,
        "manage_connectors": True,
        "view_logs": True,
        "write": True,
    },
    "developer": {
        "manage_tenants": False,
        "manage_all_users": False,
        "impersonate": False,
        "manage_own_tenant_users": False,
        "manage_connectors": True,
        "view_logs": True,
        "write": True,
    },
    "viewer": {
        "manage_tenants": False,
        "manage_all_users": False,
        "impersonate": False,
        "manage_own_tenant_users": False,
        "manage_connectors": False,
        "view_logs": True,
        "write": False,
    },
}
