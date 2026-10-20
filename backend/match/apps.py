from django.apps import AppConfig


class MatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "match"
    verbose_name = "iBilik CRM Match"

    def ready(self):
        from match import signals  # noqa: F401
