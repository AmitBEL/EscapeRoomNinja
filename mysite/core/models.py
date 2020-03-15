from django.utils import timezone
from django.contrib.auth import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinLengthValidator
from django.db import models
from random import random, choice
import string


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        print(extra_fields)
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(email=self.normalize_email(email), is_superuser=False, is_staff=False, **extra_fields)
        if password is None:
            password = ''.join(choice(string.ascii_letters + string.digits) for _ in range(15))
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(email=self.normalize_email(email), is_superuser=True, is_staff=True, **extra_fields)
        if password is None:
            password = ''.join(choice(string.ascii_letters + string.digits) for _ in range(15))
        user.set_password(password)
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=255, unique=True)
    first_name = models.CharField(max_length=255, validators=[MinLengthValidator(2)])
    last_name = models.CharField(max_length=255, validators=[MinLengthValidator(2)])
    searchable = models.BooleanField(default=False)
    is_staff = models.BooleanField('staff status', default=False)
    reviews_count = models.IntegerField(default=0)
    rooms_count = models.IntegerField(default=0)
    average_time = models.IntegerField(default=0)  # Sum of all the room time
    room_time_count = models.IntegerField(default=0)  # The number of room times
    objects = UserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        name = self.first_name + ' ' + self.last_name
        return name


class Room(models.Model):
    name = models.CharField(max_length=255, validators=[MinLengthValidator(2)])
    description = models.CharField(max_length=1000)
    address = models.CharField(max_length=255)
    website = models.CharField(max_length=255)
    telephone_num = models.CharField(max_length=20)
    totalRating = models.DecimalField(decimal_places=1, max_digits=10, default=0)  # Sum of all the total ratings
    totalRating_rank_average = models.DecimalField(default=0, decimal_places=8, max_digits=10)

    totalRating_count = models.IntegerField(default=0)  # The number of ratings
    scary_rank_count = models.IntegerField(default=0)  # The number of ratings
    difficulty_rank_count = models.IntegerField(default=0)  # The number of ratings
    owner = models.CharField(max_length=255)
    scary_rank = models.DecimalField(default=0, decimal_places=1, max_digits=10)  # Sum of all the scary ratings
    scary_rank_average = models.DecimalField(default=0, decimal_places=8, max_digits=10)
    difficulty_rank = models.DecimalField(default=0, decimal_places=1,
                                          max_digits=10)  # Sum of all the difficulty ratings
    difficulty_rank_average = models.DecimalField(default=0, decimal_places=8, max_digits=9)

    duration = models.IntegerField(default=60)
    is_kids = models.BooleanField(default=False)
    is_culinary = models.BooleanField(default=False)
    is_pregnant = models.BooleanField(default=False)
    is_deaf = models.BooleanField(default=False)
    minimal_people_amount = models.IntegerField()
    maximal_people_amount = models.IntegerField()
    city = models.CharField(max_length=255)
    latitude = models.DecimalField(decimal_places=7, max_digits=14, default=0)
    longitude = models.DecimalField(decimal_places=7, max_digits=14, default=0)
    pub_date = models.DateTimeField(default=timezone.now, null=True)
    room_tile_image = models.TextField()
    large_image = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('name', 'owner', 'city')


class Game(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    time = models.IntegerField(default=0)
    otherPlayers = models.CharField(max_length=2550, blank=True)
    date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        # return {'user': self.user, 'room': self.room}
        return 'user: ' + self.user.__str__() + ', room: ' + self.room.__str__()


class Review(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    commentDate = models.DateField(auto_now_add=True)
    text = models.TextField(blank=True)
    title = models.CharField(max_length=550, blank=True)
    scary = models.IntegerField(default=0)
    difficulty = models.IntegerField(default=0)
    scenery = models.IntegerField(default=0)
    totalRating = models.IntegerField()

    def __str__(self):
        return self.game.__str__()
