from django.urls import path

from match import views

urlpatterns = [
    path("match/requests/", views.request_collection_view, name="match-request-collection"),
    path("match/summary/", views.request_summary_view, name="match-summary"),
    path("match/requests/<int:request_id>/", views.request_detail_view, name="match-request-detail"),
    path("match/requests/<int:request_id>/assign/", views.request_assign_view, name="match-request-assign"),
    path("match/requests/<int:request_id>/reassign/", views.request_reassign_view, name="match-request-reassign"),
    path("match/requests/<int:request_id>/unassign/", views.request_unassign_view, name="match-request-unassign"),
    path("match/requests/<int:request_id>/notes/", views.request_notes_view, name="match-request-notes"),
    path("match/requests/<int:request_id>/history/", views.request_history_view, name="match-request-history"),
    path("match/requests/<int:request_id>/assign-automatically/", views.request_auto_assign_view, name="match-request-auto-assign"),
    path("match/staff-workload/", views.staff_workload_view, name="match-staff-workload"),
    path("match/settings/", views.match_settings_view, name="match-settings"),
]
