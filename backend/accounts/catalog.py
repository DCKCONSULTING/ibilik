"""Central catalog of iBilik CRM roles and application permissions.

Django stores permissions as ``app_label.codename``. The public API exposes
them as ``<module>.<action>`` (for example ``customers.view_customer``).
"""

from __future__ import annotations

from dataclasses import dataclass


ROLE_SUPERUSER = "SUPERUSER"
ROLE_TOP_MANAGER = "TOP_MANAGER"
ROLE_MANAGER = "MANAGER"
ROLE_STAFF = "STAFF"

ROLE_DISPLAY_NAMES = {
    ROLE_SUPERUSER: "System Admin",
    ROLE_TOP_MANAGER: "Top Manager",
    ROLE_MANAGER: "Manager",
    ROLE_STAFF: "Staff",
}

ROLE_LEVELS = {
    ROLE_SUPERUSER: 0,
    ROLE_TOP_MANAGER: 1,
    ROLE_MANAGER: 2,
    ROLE_STAFF: 3,
}

# Reserved for later product growth. Creating a group with one of these names
# is enough to introduce the role without rewriting views.
FUTURE_ROLES = (
    "ADMIN",
    "SALES",
    "RESERVATION",
    "FINANCE",
    "HOUSEKEEPING",
    "PROPERTY_MANAGER",
    "SUPPORT",
    "VIEWER",
)

KNOWN_ROLES = (ROLE_SUPERUSER, ROLE_TOP_MANAGER, ROLE_MANAGER, ROLE_STAFF) + FUTURE_ROLES

GROUP_TOP_MANAGER = "Top Manager"
GROUP_MANAGER = "Manager"
GROUP_STAFF = "Staff"

ROLE_GROUPS = {
    ROLE_TOP_MANAGER: GROUP_TOP_MANAGER,
    ROLE_MANAGER: GROUP_MANAGER,
    ROLE_STAFF: GROUP_STAFF,
}

GROUP_ROLES = {group: role for role, group in ROLE_GROUPS.items()}

APP_SECTIONS = (
    {"id": "workspace", "name": "Workspace"},
    {"id": "sales", "name": "Sales & Bookings"},
    {"id": "property", "name": "Property Management"},
    {"id": "reporting", "name": "Reporting"},
    {"id": "staff", "name": "Staff"},
    {"id": "management", "name": "Management"},
    {"id": "settings", "name": "Settings"},
)

MODULE_SECTIONS = {
    "dashboard": "workspace",
    "customers": "workspace",
    "inbox": "workspace",
    "opportunities": "workspace",
    "cases": "workspace",
    "calendar": "workspace",
    "quotes": "sales",
    "bookings": "sales",
    "payments": "sales",
    "match": "sales",
    "properties": "property",
    "availability": "property",
    "locations": "property",
    "reports": "reporting",
    "users": "staff",
    "settings": "settings",
}

PERMISSION_SECTIONS = {
    "users.manage_roles": "management",
    "users.manage_permissions": "management",
}


@dataclass(frozen=True)
class PermissionDefinition:
    api_codename: str
    name: str
    module: str
    django_codename: str

    @property
    def django_perm(self) -> str:
        return f"accounts.{self.django_codename}"


def _perm(api_codename: str, name: str) -> PermissionDefinition:
    module, action = api_codename.split(".", 1)
    return PermissionDefinition(
        api_codename=api_codename,
        name=name,
        module=module,
        django_codename=f"{module}_{action}",
    )


PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = (
    _perm("dashboard.view_dashboard", "Can view the dashboard"),
    _perm("customers.view_customer", "Can view customers"),
    _perm("customers.add_customer", "Can add customers"),
    _perm("customers.change_customer", "Can change customers"),
    _perm("customers.delete_customer", "Can delete customers"),
    _perm("inbox.view_inbox", "Can view the inbox"),
    _perm("inbox.send_message", "Can send inbox messages"),
    _perm("opportunities.view_opportunity", "Can view the CRM pipeline"),
    _perm("opportunities.add_opportunity", "Can add CRM pipeline records"),
    _perm("opportunities.change_opportunity", "Can change CRM pipeline records"),
    _perm("opportunities.delete_opportunity", "Can delete CRM pipeline records"),
    _perm("cases.view_case", "Can view cases"),
    _perm("cases.add_case", "Can add cases"),
    _perm("cases.change_case", "Can change cases"),
    _perm("cases.delete_case", "Can delete cases"),
    _perm("properties.view_property", "Can view properties"),
    _perm("properties.add_property", "Can add properties"),
    _perm("properties.change_property", "Can change properties"),
    _perm("properties.manage_staff", "Can manage property staff"),
    _perm("availability.view_availability", "Can view availability"),
    _perm("locations.view_location", "Can view locations"),
    _perm("locations.check_in", "Can check guests in"),
    _perm("locations.check_out", "Can check guests out"),
    _perm("locations.manage_cleaning", "Can manage location cleaning"),
    _perm("locations.manage_maintenance", "Can manage location maintenance"),
    _perm("locations.change_status", "Can change location operational status"),
    _perm("locations.override_check_in", "Can override blocked check-in"),
    _perm("quotes.view_quote", "Can view quotes"),
    _perm("quotes.create_quote", "Can create quotes"),
    _perm("quotes.change_quote", "Can change quotes"),
    _perm("quotes.approve_quote", "Can approve quotes"),
    _perm("bookings.view_booking", "Can view bookings"),
    _perm("bookings.create_booking", "Can create bookings"),
    _perm("bookings.change_booking", "Can change bookings"),
    _perm("bookings.cancel_booking", "Can cancel bookings"),
    _perm("payments.view_payment", "Can view payments"),
    _perm("payments.create_payment", "Can create payments"),
    _perm("payments.change_payment", "Can change payments"),
    _perm("payments.verify_payment", "Can verify payments"),
    _perm("payments.reject_payment", "Can reject payments"),
    _perm("payments.request_refund", "Can request refunds"),
    _perm("payments.refund_payment", "Can refund payments"),
    _perm("payments.send_reminder", "Can send payment reminders"),
    _perm("payments.add_charge", "Can add reservation charges"),
    _perm("payments.add_penalty", "Can add reservation penalties"),
    _perm("payments.void_charge", "Can void charges and penalties"),
    _perm("match.view_match", "View Match"),
    _perm("match.view_all_requests", "View All Requests"),
    _perm("match.view_assigned_requests", "View Assigned Requests"),
    _perm("match.assign_request", "Assign Requests"),
    _perm("match.reassign_request", "Reassign Requests"),
    _perm("match.unassign_request", "Unassign Requests"),
    _perm("match.change_status", "Change Request Status"),
    _perm("match.change_priority", "Change Request Priority"),
    _perm("match.add_notes", "Add Internal Notes"),
    _perm("match.resolve_request", "Resolve Requests"),
    _perm("match.delete_request", "Delete Requests"),
    _perm("calendar.view_calendar", "Can view the calendar"),
    _perm("reports.view_report", "Can view reports"),
    _perm("users.view_user", "Can view users"),
    _perm("users.manage_user", "Can manage users"),
    _perm("users.manage_roles", "Can manage roles"),
    _perm("users.manage_permissions", "Can manage permissions"),
    _perm("settings.change_setting", "Can change operational settings"),
)

PERMISSION_BY_API = {item.api_codename: item for item in PERMISSION_DEFINITIONS}
PERMISSION_BY_DJANGO = {item.django_perm: item for item in PERMISSION_DEFINITIONS}

STAFF_PERMISSIONS = (
    "dashboard.view_dashboard",
    "customers.view_customer",
    "customers.add_customer",
    "customers.change_customer",
    "inbox.view_inbox",
    "inbox.send_message",
    "opportunities.view_opportunity",
    "opportunities.add_opportunity",
    "opportunities.change_opportunity",
    "cases.view_case",
    "cases.add_case",
    "cases.change_case",
    "properties.view_property",
    "properties.add_property",
    "properties.change_property",
    "availability.view_availability",
    "locations.view_location",
    "locations.check_in",
    "locations.check_out",
    "locations.manage_cleaning",
    "locations.manage_maintenance",
    "locations.change_status",
    "quotes.view_quote",
    "quotes.create_quote",
    "quotes.change_quote",
    "bookings.view_booking",
    "bookings.create_booking",
    "bookings.change_booking",
    "calendar.view_calendar",
    "payments.view_payment",
    "payments.create_payment",
    "payments.change_payment",
    "payments.request_refund",
    "payments.send_reminder",
    "payments.add_charge",
    "payments.add_penalty",
    "match.view_match",
    "match.view_assigned_requests",
    "match.change_status",
    "match.add_notes",
    "match.resolve_request",
)

MANAGER_PERMISSIONS = STAFF_PERMISSIONS + (
    "opportunities.delete_opportunity",
    "cases.delete_case",
    "customers.delete_customer",
    "quotes.approve_quote",
    "bookings.cancel_booking",
    "payments.verify_payment",
    "payments.reject_payment",
    "payments.refund_payment",
    "payments.void_charge",
    "reports.view_report",
    "users.view_user",
    "settings.change_setting",
    "properties.manage_staff",
    "locations.override_check_in",
    "match.view_all_requests",
    "match.assign_request",
    "match.reassign_request",
    "match.unassign_request",
    "match.change_priority",
    "match.delete_request",
)

TOP_MANAGER_PERMISSIONS = MANAGER_PERMISSIONS + ("users.manage_user",)

ROLE_DEFAULT_PERMISSIONS = {
    ROLE_TOP_MANAGER: TOP_MANAGER_PERMISSIONS,
    ROLE_MANAGER: MANAGER_PERMISSIONS,
    ROLE_STAFF: STAFF_PERMISSIONS,
}


def permission_section(api_codename: str, module: str) -> str:
    return PERMISSION_SECTIONS.get(api_codename, MODULE_SECTIONS.get(module, module))


def role_display_name(role: str | None) -> str:
    if not role:
        return "No role"
    return ROLE_DISPLAY_NAMES.get(role, role.replace("_", " ").title())


def api_permission_from_django(django_perm: str) -> str | None:
    definition = PERMISSION_BY_DJANGO.get(django_perm)
    return definition.api_codename if definition else None
