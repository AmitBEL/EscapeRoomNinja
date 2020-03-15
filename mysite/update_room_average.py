import os
import django

os.environ["DJANGO_SETTINGS_MODULE"] = 'mysite.settings'
django.setup()

from core.models import Room

all_rooms = Room.objects.all()
for room in all_rooms:
    if room.totalRating_count == 0:
        room.totalRating_rank_average = 0
    else:
        room.totalRating_rank_average = room.totalRating / room.totalRating_count

    if room.scary_rank_count == 0:
        room.scary_rank_average = 0
    else:
        room.scary_rank_average = room.scary_rank / room.scary_rank_count

    if room.difficulty_rank_count == 0:
        room.difficulty_rank_average = 0
    else:
        room.difficulty_rank_average = room.difficulty_rank / room.difficulty_rank_count
    room.save()
