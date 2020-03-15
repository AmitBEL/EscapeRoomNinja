from rest_framework.permissions import BasePermission
from rest_framework.exceptions import APIException
from rest_framework import status


class NeedLogin(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'יש להתחבר על מנת לבצע את הפעולה'
    default_code = 'not_authenticated'


class UserHasPermissionOnGame(BasePermission):
    message = 'לא ניתן לערוך את המשחק'

    def has_object_permission(self, request, view, obj):
        game_user = obj.user
        if game_user == request.user:
            return True
        return False

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            raise NeedLogin()
        return True


class UserHasPermissionOnReview(BasePermission):
    """ related to ReviewViewSet """
    message = 'לא ניתן לערוך את התגובה'

    def has_object_permission(self, request, view, obj):
        # checking the user of the game being reviewed
        game_user = obj.game.user
        if game_user == request.user:
            return True
        return False

    def has_permission(self, request, view):
        if view.action in ['create'] and not request.user.is_authenticated:
            raise NeedLogin()
        return True
