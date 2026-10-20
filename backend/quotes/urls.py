from django.urls import path

from quotes import views

urlpatterns = [
    path("quotes/", views.quote_collection_view, name="quote-collection"),
    path("quotes/<int:quote_id>/", views.quote_detail_view, name="quote-detail"),
]
