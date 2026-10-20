from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "iBilik CRM administration"
admin.site.site_title = "iBilik CRM admin"
admin.site.index_title = "System administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("payments.urls")),
    path("api/", include("quotes.urls")),
    path("api/", include("bookings.urls")),
    path("api/", include("locations.urls")),
    path("api/", include("accounts.urls")),
    path("api/", include("crm.urls")),
    path("api/", include("cases.urls")),
    path("api/", include("match.urls")),
]
