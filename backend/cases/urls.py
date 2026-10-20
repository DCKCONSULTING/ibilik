from django.urls import path

from cases import views

urlpatterns = [
    path("calendar/events/", views.calendar_events_view, name="calendar-events"),
    path("follow-ups/", views.global_follow_up_collection_view, name="follow-up-collection"),
    path("follow-ups/<int:follow_up_id>/", views.global_follow_up_detail_view, name="follow-up-detail"),
    path("follow-ups/<int:follow_up_id>/complete/", views.global_follow_up_complete_view, name="follow-up-complete"),
    path("cases/", views.case_collection_view, name="case-collection"),
    path("cases/<int:case_id>/", views.case_detail_view, name="case-detail"),
    path("cases/<int:case_id>/stage/", views.case_stage_view, name="case-stage"),
    path("cases/<int:case_id>/actions/", views.case_action_view, name="case-action"),
    path("cases/<int:case_id>/follow-ups/", views.follow_up_collection_view, name="case-follow-ups"),
    path("cases/<int:case_id>/follow-ups/<int:follow_up_id>/", views.follow_up_detail_view, name="case-follow-up-detail"),
    path("cases/<int:case_id>/follow-ups/<int:follow_up_id>/complete/", views.follow_up_complete_view, name="case-follow-up-complete"),
    path("cases/<int:case_id>/activities/", views.activity_collection_view, name="case-activities"),
    path("pipeline/", views.case_collection_view, name="pipeline-collection"),
    path("pipeline/<int:case_id>/", views.case_detail_view, name="pipeline-detail"),
    path("pipeline/<int:case_id>/stage/", views.case_stage_view, name="pipeline-stage"),
    path("pipeline/<int:case_id>/actions/", views.case_action_view, name="pipeline-action"),
    path("opportunities/", views.case_collection_view, name="opportunity-collection"),
    path("opportunities/<int:case_id>/", views.case_detail_view, name="opportunity-detail"),
    path("opportunities/<int:case_id>/stage/", views.case_stage_view, name="opportunity-stage"),
    path("opportunities/<int:case_id>/actions/", views.case_action_view, name="opportunity-action"),
]
