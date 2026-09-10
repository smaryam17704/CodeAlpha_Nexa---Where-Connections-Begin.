from django.core.management.base import BaseCommand
from accounts.models import Interest

INTERESTS = [
    ('Technology', '💻'), ('Design', '🎨'), ('Photography', '📷'),
    ('Music', '🎵'), ('Travel', '✈️'), ('Gaming', '🎮'),
    ('Movies', '🎬'), ('Books', '📚'), ('Food', '🍜'),
    ('Fitness', '💪'), ('Art', '🖌️'), ('Science', '🔬'),
]


class Command(BaseCommand):
    help = 'Seed the default Nexa interest categories'

    def handle(self, *args, **options):
        created = 0
        for name, icon in INTERESTS:
            _, was_created = Interest.objects.get_or_create(name=name, defaults={'icon': icon})
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'Seeded interests ({created} new).'))
