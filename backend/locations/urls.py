from django.urls import path

from locations import views

urlpatterns = [
    path(
        "properties/<int:property_id>/locations/",
        views.property_location_collection_view,
        name="property-location-collection",
    ),
    path("locations/<int:location_id>/", views.location_detail_view, name="location-detail"),
    path(
        "locations/<int:location_id>/deactivate/",
        views.location_deactivate_view,
        name="location-deactivate",
    ),
    path("locations/<int:location_id>/check-in/", views.location_check_in_view, name="location-check-in"),
    path("locations/<int:location_id>/check-out/", views.location_check_out_view, name="location-check-out"),
    path("locations/<int:location_id>/status/", views.location_status_view, name="location-status"),
    path(
        "locations/<int:location_id>/cleaning/start/",
        views.location_cleaning_start_view,
        name="location-cleaning-start",
    ),
    path(
        "locations/<int:location_id>/cleaning/complete/",
        views.location_cleaning_complete_view,
        name="location-cleaning-complete",
    ),
    path(
        "locations/<int:location_id>/maintenance/",
        views.location_maintenance_start_view,
        name="location-maintenance-start",
    ),
    path(
        "locations/<int:location_id>/maintenance/<int:issue_id>/resolve/",
        views.location_maintenance_resolve_view,
        name="location-maintenance-resolve",
    ),
    path(
        "locations/<int:location_id>/maintenance/resolve/",
        views.location_maintenance_resolve_view,
        name="location-maintenance-resolve-current",
    ),
]
