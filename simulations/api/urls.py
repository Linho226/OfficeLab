from django.urls import path

from simulations.api.auth_views import LoginView, LogoutView, SessionView
from simulations.api.views import (
    ScenarioListView,
    SavedAttemptListView,
    AttemptCheckView,
    AttemptRestartView,
    AttemptDetailView,
    AttemptEventView,
    AttemptHintView,
    AttemptListView,
    AttemptSubmitView,
    ScenarioDetailView,
)


app_name = "simulations_api"

urlpatterns = [
    path("scenarios/", ScenarioListView.as_view(), name="scenario-list"),
    path("attempts/", SavedAttemptListView.as_view(), name="saved-attempt-list"),
    path("attempts/<uuid:attempt_id>/check/", AttemptCheckView.as_view(), name="attempt-check"),
    path("attempts/<uuid:attempt_id>/restart/", AttemptRestartView.as_view(), name="attempt-restart"),
    path("attempts/<uuid:attempt_id>/hint/", AttemptHintView.as_view(), name="attempt-hint"),
    path("auth/session/", SessionView.as_view(), name="auth-session"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path(
        "scenarios/<str:code>/",
        ScenarioDetailView.as_view(),
        name="scenario-detail",
    ),
    path(
        "scenarios/<str:code>/attempts/",
        AttemptListView.as_view(),
        name="attempt-list",
    ),
    path(
        "attempts/<uuid:attempt_id>/",
        AttemptDetailView.as_view(),
        name="attempt-detail",
    ),
    path(
        "attempts/<uuid:attempt_id>/events/",
        AttemptEventView.as_view(),
        name="attempt-event",
    ),
    path(
        "attempts/<uuid:attempt_id>/submit/",
        AttemptSubmitView.as_view(),
        name="attempt-submit",
    ),
]
