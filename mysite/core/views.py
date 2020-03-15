import os
from functools import reduce
from operator import or_

from django.db.models import Q, Count, Sum
from recombee_api_client.exceptions import ResponseException
from requests import HTTPError
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import MissingBackend, AuthTokenError, AuthForbidden
from social_django.utils import load_strategy, load_backend

from core.models import Review, Room
from url_filter.integrations.drf import DjangoFilterBackend
from rest_framework import viewsets, mixins, status, permissions, authentication, generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from core.models import User, Game
from core.serializers import UserSerializer, AuthTokenSerializer, RoomSerializer, RoomNameSerializer
from recommendationSystem.recombeeIntegration import RecombeeIntegrationClient
from . import serializers
from .permissions import UserHasPermissionOnGame, UserHasPermissionOnReview


# ---------------- Aux functions ---------------------------------------

def update_user_after_create_game(user, game_time):
    user.rooms_count += 1
    if game_time > 0:
        user.average_time += game_time
        user.room_time_count += 1
    # if not game_time == 0:
    #     user.average_time = (user.average_time * user.room_time_count + game_time) / (user.room_time_count + 1)
    #     user.room_time_count += 1
    user.save()


def update_user_after_update_game(user, new_game_time, old_game_time):
    if old_game_time == 0:
        if new_game_time > 0:
            user.average_time += new_game_time
            user.room_time_count += 1
            # user.average_time = (user.average_time * user.room_time_count + new_game_time) / (
            #         user.room_time_count + 1)
            # user.room_time_count += 1
    else:
        if new_game_time == 0:
            user.average_time -= old_game_time
            user.room_time_count -= 1
            # user.average_time = (user.average_time * user.room_time_count - old_game_time.time) / (
            #         user.room_time_count - 1)
            # user.room_time_count -= 1
        else:
            user.average_time -= old_game_time
            user.average_time += new_game_time
            # time_difference = new_game_time - old_game_time.time
            # user.average_time = (user.average_time * user.room_time_count + time_difference) / (
            #     user.room_time_count)
    user.save()


def update_user_after_delete_game(user, game_time):
    user.rooms_count -= 1
    if game_time > 0:
        user.average_time -= game_time
        user.room_time_count -= 1
    # if 0 < game_time < 240:
    #     user.average_time = (user.average_time * user.room_time_count - game_time) / (user.room_time_count - 1)
    #     user.room_time_count -= 1

    user.save()


def try_get_review_of_game(game):
    try:
        review = Review.objects.get(game=game)
        return review
    except Review.DoesNotExist:
        return None


def sort_by_average(room):
    count = room.totalRating_count
    total = room.totalRating
    if count == 0:
        return 0
    return total / count


def update_room_rate_after_delete_review(review, room_id):
    """ update room rating when a review was deleted """
    try:
        room_object = Room.objects.get(pk=room_id)
    except Room.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    # Total rank
    room_object.totalRating -= review.totalRating
    room_object.totalRating_count -= 1
    if room_object.totalRating_count == 0:
        room_object.totalRating_rank_average = 0
    else:
        room_object.totalRating_rank_average = room_object.totalRating / room_object.totalRating_count
    # if room_object.totalRating_count == 1:
    #     room_object.totalRating = 0
    # else:
    #     room_object.totalRating = (room_object.totalRating * room_object.totalRating_count -
    #                                review.totalRating) / (room_object.totalRating_count - 1)
    # room_object.totalRating_count -= 1

    # Scary ranking
    if review.scary > 0:
        room_object.scary_rank -= review.scary
        room_object.scary_rank_count -= 1
        if room_object.scary_rank_count == 0:
            room_object.scary_rank_average = 0
        else:
            room_object.scary_rank_average = room_object.scary_rank / room_object.scary_rank_count
    # if room_object.scary_rank_count > 0 and review.scary != 0:
    #     if room_object.scary_rank_count == 1:
    #         room_object.scary_rank = 0
    #     else:
    #         room_object.scary_rank = (room_object.scary_rank * room_object.scary_rank_count -
    #                                   review.scary) / (room_object.scary_rank_count - 1)
    #     room_object.scary_rank_count -= 1

    # Difficulty ranking
    if review.difficulty > 0:
        room_object.difficulty_rank -= review.difficulty
        room_object.difficulty_rank_count -= 1
        if room_object.difficulty_rank_count == 0:
            room_object.difficulty_rank_average = 0
        else:
            room_object.difficulty_rank_average = room_object.difficulty_rank / room_object.difficulty_rank_count
    # if room_object.difficulty_rank_count > 0 and review.difficulty != 0:
    #     if room_object.difficulty_rank_count == 1:
    #         room_object.difficulty_rank = 0
    #     else:
    #         room_object.difficulty_rank = (room_object.difficulty_rank * room_object.difficulty_rank_count -
    #                                        review.difficulty) / (room_object.difficulty_rank_count - 1)
    #     room_object.difficulty_rank_count -= 1

    room_object.save()


def update_user_reviews_count_after_create_review(user):
    """ update user reviews_count when a review was created """
    user.reviews_count += 1
    user.save()


def update_user_reviews_count_after_delete_review(user):
    user.reviews_count -= 1
    user.save()


def update_room_rate_after_create_review(request, room):
    """ update room ratings when a review was created """
    if 'totalRating' in request.data:
        room.totalRating += int(request.data['totalRating'])
        room.totalRating_count += 1
        room.totalRating_rank_average = room.totalRating / room.totalRating_count
        # room.totalRating = (room.totalRating * room.totalRating_count +
        #                     request.data['totalRating']) / (room.totalRating_count + 1)
        # room.totalRating_count += 1

    if 'scary' in request.data:
        room.scary_rank += int(request.data['scary'])
        room.scary_rank_count += 1
        room.scary_rank_average = room.scary_rank / room.scary_rank_count
        # room.scary_rank = (room.scary_rank * room.scary_rank_count +
        #                    request.data['scary']) / (room.scary_rank_count + 1)
        # room.scary_rank_count += 1

    if 'difficulty' in request.data:
        room.difficulty_rank += int(request.data['difficulty'])
        room.difficulty_rank_count += 1
        room.difficulty_rank_average = room.difficulty_rank / room.difficulty_rank_count
        # room.difficulty_rank = (room.difficulty_rank * room.difficulty_rank_count +
        #                         request.data['difficulty']) / (room.difficulty_rank_count + 1)
        # room.difficulty_rank_count += 1

    room.save()


def dic_to_list(dic):
    output = list()
    if isinstance(dic, str):
        output.append(dic)
    else:
        for value in dic.values():
            if isinstance(value, str):
                output.append(value)
            else:
                output.append(value[0])

    return output


def get_difficulties(param):
    ranges = []
    if 'easy' in param:
        ranges.append(Q(difficulty_rank_average__range=[0, 1]))
    if 'normal' in param:
        ranges.append(Q(difficulty_rank_average__range=[1.00000001, 2]))
    if 'hard' in param:
        ranges.append(Q(difficulty_rank_average__range=[2.00000001, 3]))
    query = reduce(or_, ranges, Q())
    return query


def get_scariness(param):
    ranges = []
    if 'not_scary' in param:
        ranges.append(Q(scary_rank_average__range=[0, 3.99999999]))
    if 'little_scary' in param:
        ranges.append(Q(scary_rank_average__range=[4, 6.99999999]))
    if 'very_scary' in param:
        ranges.append(Q(scary_rank_average__range=[7, 10]))
    query = reduce(or_, ranges, Q())
    return query


# ---------------- Views ---------------------------------------

class ManageUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


class CreateUserView(CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):  # <- here i forgot self
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # send room rating update to recombee
        recombee_client = RecombeeIntegrationClient()
        try:
            recombee_client.send_user(serializer.data['id'])
        except ResponseException:
            print("user with id", serializer.data['id'], "is already exists in recombee")

        headers = self.get_success_headers(serializer.data)
        token, created = Token.objects.get_or_create(user=serializer.instance)
        return Response({'token': token.key, 'user': serializer.data}, status=status.HTTP_201_CREATED, headers=headers)


class CreateTokenView(ObtainAuthToken):
    serializer_class = AuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        userSerializer = UserSerializer(user)
        return Response({'token': token.key, 'user': userSerializer.data})


class SearchFieldsView(generics.GenericAPIView):

    def get(self, request):
        cities_list = Room.objects.all().values_list('city', flat=True).distinct()
        owners_list = Room.objects.all().values_list('owner', flat=True).distinct()
        rooms_list = Room.objects.all()
        romms_list = RoomNameSerializer(rooms_list, many=True)
        search_fields = {'cities_list': cities_list, 'owners_list': owners_list, 'rooms_list': romms_list.data}
        return Response(search_fields)


# ---------------- ViewSets ---------------------------------------

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = {TokenAuthentication, }
    permission_classes = {IsAuthenticatedOrReadOnly, }
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_fields = ['pk']

    def filter_queryset(self, queryset):
        first_name = self.request.query_params.get('first_name')
        last_name = self.request.query_params.get('last_name')
        get_users = User.objects.filter(searchable=True)
        if first_name:
            get_users = get_users.filter(first_name__contains=first_name)
        if last_name:
            get_users = get_users.filter(last_name__contains=last_name)
        if not get_users:
            raise ValidationError('לא נמצא משתמש - אינו קיים או משתמש פרטי')
        return get_users


# DONE

class RoomViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    authentication_classes = {TokenAuthentication, }
    permission_classes = {IsAuthenticatedOrReadOnly, }
    queryset = Room.objects.all()
    serializer_class = serializers.RoomSerializer
    filter_backends = [DjangoFilterBackend]
    filter_fields = '__all__'
    lookup_fields = ['pk']
    allowed_order = ['name', '-name', 'totalRating', '-totalRating']

    def retrieve(self, request, *args, **kwargs):
        room = self.get_object()
        room_serializer = self.get_serializer(room)

        if (request.user.is_authenticated):
            recombee_client = RecombeeIntegrationClient()
            recombee_client.send_room_viewing(room.id, request.user.id)

        return Response(room_serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if 'difficulty' in request.query_params:
            difficulty_level = get_difficulties(request.query_params['difficulty'])
            queryset = queryset.filter(difficulty_level)

        if 'scariness' in request.query_params:
            scariness_level = get_scariness(request.query_params['scariness'])
            queryset = queryset.filter(scariness_level)

        if 'order' in request.query_params:
            order = request.query_params['order']
            if order in self.allowed_order:
                if order == 'name' or order == '-name':
                    queryset = queryset.order_by(order)
                else:
                    reverse = (order == '-totalRating')
                    queryset = sorted(queryset, key=sort_by_average, reverse=reverse)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)

            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data)

    # def get_queryset(self):
    #     queryset = self.queryset
    #     number_of_players = self.request.query_params.get('numberOfPlayers', None)
    #     totalRating = self.request.query_params.get('totalRating', None)
    #     if number_of_players is not None:
    #         queryset = queryset.filter(minimal_people_amount__lte=number_of_players,
    #                                    maximal_people_amount__gte=number_of_players)
    #
    #     if totalRating is not None:
    #         queryset = queryset.filter(totalRating__gte=totalRating)
    #
    #     return queryset


# DONE
class GameViewSet(viewsets.ModelViewSet):
    """ related to the url: user/game """
    authentication_classes = (TokenAuthentication,)
    permission_classes = (UserHasPermissionOnGame,)
    queryset = Game.objects.all()
    serializer_class = serializers.GameSerializer

    def create(self, request, *args, **kwargs):
        """ create new game """
        if 'room' not in request.data:
            return Response(data=list('לא נמצא חדר'), status=status.HTTP_404_NOT_FOUND)

        # check if the room exists
        try:
            game_room = Room.objects.get(id=request.data['room'])
        except Room.DoesNotExist:
            return Response(data=list('חדר לא קיים'), status=status.HTTP_404_NOT_FOUND)

        user = request.user

        # check if the game already exists
        if self.queryset.filter(user=user, room=game_room).exists():
            return Response(data=['החדר כבר ברשימת החדרים ששיחקת'], status=status.HTTP_403_FORBIDDEN)

        # validate the request.data
        game_serializer = self.serializer_class(data=request.data)
        if not game_serializer.is_valid():
            return Response(dic_to_list(game_serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        # update all the relevant models and return the new game
        game_serializer.save(user=request.user, room=game_room)
        game_time = game_serializer.data.get('time', 0)
        update_user_after_create_game(user=user, game_time=game_time)
        recombee_client = RecombeeIntegrationClient()
        recombee_client.send_room_done_by_user(game_room.id, user.id)
        return Response(game_serializer.data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        game = self.get_object()
        game_room = game.room
        if 'room' in request.data:
            if game_room.id != request.data['room']:
                return Response(['החדר לא תואם למשחק'], status=status.HTTP_400_BAD_REQUEST)

        partial = kwargs.pop('partial', False)
        if not partial:
            if 'room' not in request.data:
                return Response(data=['לא נמצא חדר'], status=status.HTTP_404_NOT_FOUND)

        game_serializer = self.get_serializer(game, data=request.data, partial=partial)
        if not game_serializer.is_valid():
            return Response(dic_to_list(game_serializer.errors), status=status.HTTP_400_BAD_REQUEST)
        if 'time' in request.data:
            new_game_time = request.data['time']
        else:
            new_game_time = 0
        old_game_time = game.time
        self.perform_update(game_serializer)
        update_user_after_update_game(user=game.user, old_game_time=old_game_time, new_game_time=new_game_time)
        return Response(game_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        game = self.get_object()
        review = try_get_review_of_game(game)
        user = game.user
        room_id = game.room.id
        user_id = user.id
        self.perform_destroy(instance=game)
        # destroy the review of the game if exists
        if review is not None:
            update_room_rate_after_delete_review(review, room_id)
            update_user_reviews_count_after_delete_review(user=user)
        recombee_client = RecombeeIntegrationClient()
        try:
            recombee_client.cancel_room_done_by_user(room_id, user_id)
            recombee_client.cancel_room_rating_by_user(room_id, user_id)
        except:
            print("dont have review to delete")
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        user = instance.user
        game_time = instance.time
        super().perform_destroy(instance)
        update_user_after_delete_game(user=user, game_time=game_time)


# DONE
class ReviewViewSet(viewsets.ModelViewSet):
    """ related to the url: room/review """
    authentication_classes = {TokenAuthentication, }
    permission_classes = {UserHasPermissionOnReview, }
    queryset = Review.objects.all()
    serializer_class = serializers.ReviewSerializer

    def create(self, request, room_pk):
        """ create new review """
        try:
            room = Room.objects.get(pk=room_pk)
        except Room.DoesNotExist:
            return Response(data=['לא נמצא חדר'], status=status.HTTP_404_NOT_FOUND)

        user = request.user
        game, created = Game.objects.get_or_create(room=room, user=user)

        # check if a review for the game already exists
        if Review.objects.filter(game=game).exists():
            return Response(data=['כבר הגבת על החדר'], status=status.HTTP_403_FORBIDDEN)

        # insert the game to the data
        data = request.data.copy()
        data['game'] = game.pk

        # validate the request.data
        review_serializer = self.serializer_class(data=data)
        if not review_serializer.is_valid():
            return Response(dic_to_list(review_serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        # update all the relevant models and return the new review
        review_serializer.save()
        if created:
            # if a new game was created we need to update the user_room_count
            user.rooms_count += 1
            recombee_client = RecombeeIntegrationClient()
            recombee_client.send_room_done_by_user(room.id, user.id)
            user.save()
        update_room_rate_after_create_review(request=self.request, room=room)
        update_user_reviews_count_after_create_review(user=user)
        # send room rating update to recombee
        recombee_client = RecombeeIntegrationClient()
        recombee_client.send_room_rating_by_user(room.id, user.id, int(request.data['totalRating']))
        roomSerializer = RoomSerializer(room)
        recombee_client.update_room_rating(roomSerializer)
        return Response(review_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """ update a review """
        review_before_update = self.get_object()
        data = request.data
        data['game'] = review_before_update.game.pk
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(review_before_update, data=data, partial=partial)
        if not serializer.is_valid():
            return Response(dic_to_list(serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        # self.update_room_rate_after_update_review(request, review_before_update)
        self.perform_update(serializer)
        roomObject = Room.objects.get(pk=kwargs['room_pk'])
        self.update_room_rate_after_update_review(roomObject)
        recombee_client = RecombeeIntegrationClient()
        recombee_client.update_room_rating_by_user(roomObject.id, review_before_update.game.user.id,
                                                   review_before_update.totalRating)
        recombee_client.update_room_rating(RoomSerializer(roomObject))
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        room_id = instance.game.room.pk
        super().perform_destroy(instance)
        update_room_rate_after_delete_review(review=instance, room_id=room_id)
        update_user_reviews_count_after_delete_review(user=instance.game.user)
        recombee_client = RecombeeIntegrationClient()
        recombee_client.cancel_room_rating_by_user(room_id=instance.game.room.id, user_id=instance.game.user.id)
        recombee_client.update_room_rating(RoomSerializer(instance.game.room))

    def get_queryset(self):
        """ get all the reviews of a room """
        queryset = self.queryset
        query_set = queryset.filter(game__room=self.kwargs['room_pk'])
        return query_set

    def update_room_rate_after_update_review(self, roomObject):
        ratings_counter = Review.objects.filter(game__room__id=roomObject.id).aggregate(
            totalRating=Count('pk', filter=Q(totalRating__gt=0)),
            difficulty=Count('pk', filter=Q(difficulty__gt=0)),
            scary=Count('pk', filter=Q(scary__gt=0)))
        ratings_sum = Review.objects.filter(game__room__id=roomObject.id).aggregate(Sum('totalRating'),
                                                                                    Sum('difficulty'),
                                                                                    Sum('scary'))

        roomObject.totalRating = ratings_sum['totalRating__sum']
        roomObject.totalRating_count = ratings_counter['totalRating']
        if roomObject.totalRating_count == 0:
            roomObject.totalRating_rank_average = 0
        else:
            roomObject.totalRating_rank_average = roomObject.totalRating / roomObject.totalRating_count

        roomObject.difficulty_rank = ratings_sum['difficulty__sum']
        roomObject.difficulty_rank_count = ratings_counter['difficulty']
        if roomObject.difficulty_rank_count == 0:
            roomObject.difficulty_rank_average = 0
        else:
            roomObject.difficulty_rank_average = roomObject.difficulty_rank / roomObject.difficulty_rank_count

        roomObject.scary_rank = ratings_sum['scary__sum']
        roomObject.scary_rank_count = ratings_counter['scary']
        if roomObject.scary_rank_count == 0:
            roomObject.scary_rank_average = 0
        else:
            roomObject.scary_rank_average = roomObject.scary_rank / roomObject.scary_rank_count

        roomObject.save()

    # def update_room_rate_after_update_review(self, request, review_before_update):
    #     """ update room rating when a review was updated """
    #     review_instance = self.get_object()
    #     update_room_rate_after_delete_review(review=review_before_update)
    #     room = Room.objects.get(pk=review_instance.game.room.pk)
    #     update_room_rate_after_create_review(request=request, room=room)


class SocialLoginView(generics.GenericAPIView):
    """Log in using facebook"""
    serializer_class = serializers.SocialSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Authenticate user through the provider and access_token"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.data.get('provider', None)
        strategy = load_strategy(request)

        try:
            backend = load_backend(strategy=strategy, name=provider,
                                   redirect_uri=None)

        except MissingBackend:
            return Response(data=['Please provide a valid provider'],
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            if isinstance(backend, BaseOAuth2):
                access_token = serializer.data.get('access_token')
            user = backend.do_auth(access_token)
        except HTTPError as error:
            return Response(["Invalid token"], status=status.HTTP_400_BAD_REQUEST)
        except AuthTokenError as error:
            return Response(["Invalid credentials"], status=status.HTTP_400_BAD_REQUEST)

        try:
            authenticated_user = backend.do_auth(access_token, user=user)

        except HTTPError as error:
            return Response(["Invalid token"], status=status.HTTP_400_BAD_REQUEST)


        except AuthForbidden as error:
            return Response(["Invalid token"], status=status.HTTP_400_BAD_REQUEST)

        if authenticated_user and authenticated_user.is_active:
            token, created = Token.objects.get_or_create(user=authenticated_user)
            if created:
                # send room rating update to recombee
                recombee_client = RecombeeIntegrationClient()
                try:
                    recombee_client.send_user(authenticated_user.id)
                except ResponseException:
                    print("user with id", authenticated_user.id, "is already exists in recombee")
            user = UserSerializer(authenticated_user)
            response = {
                "user": user.data,
                "token": token.key,
            }

            return Response(status=status.HTTP_200_OK, data=response)
