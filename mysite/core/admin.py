from django.contrib import admin
from . import models


class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)


admin.site.register(models.Room, RoomAdmin)


class GameAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'user')


admin.site.register(models.Game, GameAdmin)

admin.site.register(models.User)


class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'game')


admin.site.register(models.Review, ReviewAdmin)
