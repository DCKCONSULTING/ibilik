from django.core.management.base import BaseCommand

from accounts.services import initialize_access_control


class Command(BaseCommand):
    help = "Create Manager and Staff groups and assign their default permissions."

    def handle(self, *args, **options):
        initialize_access_control()
        self.stdout.write(self.style.SUCCESS("Initialized iBilik CRM roles and permissions."))
