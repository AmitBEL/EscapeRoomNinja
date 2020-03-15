from django.db.models import Q
from rest_framework import authentication, permissions, status
from recommendationSystem.recombeeIntegration import RECOMMENDATION_SIZE
from recommendationSystem.recombeeIntegration import RecombeeIntegrationClient
from rest_framework import authentication, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from core import serializers
from core.models import Room, Game
from core.serializers import RoomSerializer


# converts a serialization of a model to a list of a specific field


def serializerToIdList(serializer, IDfield):
    listToReturn = []
    for obj in serializer.data:
        listToReturn.append(obj[IDfield])
    return listToReturn


# general recommendation for a non-logged in user
class generalRecommendationView(APIView):
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    def get(self, request, format=None):
        if request.user.is_anonymous:
            queryset = Room.objects.all().order_by('-totalRating')[:RECOMMENDATION_SIZE]
        else:
            already_played = Game.objects.filter(user__id=request.user.id).values_list('room_id', flat=True).distinct()
            queryset = Room.objects.filter(~Q(id__in=already_played)).order_by('-totalRating')[:RECOMMENDATION_SIZE]
        serializer = RoomSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)


# a recommendation for a logged in user
class personalizedRecommendationView(APIView):
    # user should be logged in
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        client = RecombeeIntegrationClient()
        user_id = request.user.id
        if user_id == None:
            return Response('{"message":"User not logged in!"}', status=status.HTTP_401_UNAUTHORIZED)
        recommended_for_user = client.get_recommendation(user_id)
        # extracting room ids
        value_list = []
        for room in recommended_for_user:
            value_list.append(room['id'])
        # get serialized version of all the rooms as json
        reccomended_rooms_as_json = serializers.RoomSerializer(Room.objects.filter(id__in=value_list), many=True)

        return Response(reccomended_rooms_as_json.data)
