import os
import django

os.environ["DJANGO_SETTINGS_MODULE"] = 'mysite.settings'
django.setup()

from opencage.geocoder import OpenCageGeocode
from core.models import Room
from pprint import pprint

key = 'overrided_by_local_settings'
geocoder = OpenCageGeocode(key)
all_rooms = Room.objects.all()
for room in all_rooms:
    address = room.city + ',' + room.address
    results = geocoder.geocode(address, language='he')
    if len(results) == 0 or 'geometry' not in results[0]:
        continue
    if 'lat' not in results[0]['geometry'] or 'lng' not in results[0]['geometry']:
        continue
    print(str(room.id), room.name, (results[0]['geometry']['lat'],
                                     results[0]['geometry']['lng']))
    room.latitude = results[0]['geometry']['lat']
    room.longitude = results[0]['geometry']['lng']
    room.save()
