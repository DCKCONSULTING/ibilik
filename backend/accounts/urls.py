from django.urls import path

from accounts import property_excel_views, property_views, resource_views, views

urlpatterns = [
    path("auth/csrf/", views.csrf_view, name="auth-csrf"),
    path("auth/login/", views.login_view, name="auth-login"),
    path("auth/logout/", views.logout_view, name="auth-logout"),
    path("auth/me/", views.me_view, name="auth-me"),
    path("auth/password/", views.me_password_view, name="auth-password"),
    path("auth/deactivate/", views.me_deactivate_view, name="auth-deactivate"),
    path("roles/", views.role_collection_view, name="role-list"),
    path("roles/<str:role_code>/", views.role_detail_view, name="role-detail"),
    path("permissions/", views.permission_list_view, name="permission-list"),
    path("users/", views.user_collection_view, name="user-collection"),
    path("users/<int:user_id>/", views.user_detail_view, name="user-detail"),
    path("users/<int:user_id>/password/", views.user_password_view, name="user-password"),
    path("dashboard/", resource_views.dashboard_view, name="resource-dashboard"),
    path("properties/", property_views.property_collection_view, name="property-collection"),
    path("properties/export/", property_excel_views.properties_export_view, name="property-export"),
    path("properties/portfolio-export/", property_excel_views.portfolio_export_view, name="property-portfolio-export"),
    path("properties/import-template/", property_excel_views.import_template_view, name="property-import-template"),
    path("properties/import/preview/", property_excel_views.import_preview_view, name="property-import-preview"),
    path("properties/import/", property_excel_views.import_commit_view, name="property-import-commit"),
    path("locations/export/", property_excel_views.locations_export_view, name="location-export"),
    path("properties/<int:property_id>/", property_views.property_detail_view, name="property-detail"),
    path("properties/<int:property_id>/staff/", property_views.property_staff_collection_view, name="property-staff-collection"),
    path(
        "properties/<int:property_id>/staff/<int:user_id>/",
        property_views.property_staff_detail_view,
        name="property-staff-detail",
    ),
    path("availability/", resource_views.availability_view, name="resource-availability"),
    path("quotes/approve/", resource_views.quotes_approve_view, name="resource-quotes-approve"),
    path("bookings/cancel/", resource_views.bookings_cancel_view, name="resource-bookings-cancel"),
    path("calendar/", resource_views.calendar_view, name="resource-calendar"),
    path("reports/", resource_views.reports_view, name="resource-reports"),
    path("settings/", resource_views.settings_view, name="resource-settings"),
]
