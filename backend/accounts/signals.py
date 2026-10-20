from django.db.models.signals import post_migrate
from django.dispatch import receiver

from accounts.services import initialize_access_control


@receiver(post_migrate)
def seed_roles_and_permissions(sender, **kwargs):
    if sender.name != "accounts":
        return
    initialize_access_control()
