from django.urls import path

from bookings import views

urlpatterns = [
    path("bookings/", views.booking_collection_view, name="booking-collection"),
    path("bookings/<int:booking_id>/", views.booking_detail_view, name="booking-detail"),
]
