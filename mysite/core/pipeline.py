from django.http import HttpResponse
from rest_framework import status
from social_core.exceptions import AuthFailed
from social_django.middleware import SocialAuthExceptionMiddleware

from .models import User


class MySocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def process_exception(self, request, exception):
        if isinstance(exception, AuthFailed):
            return HttpResponse(list("אופס, משתמש עם האימייל הזה כבר קיים"),status=status.HTTP_409_CONFLICT)


def check_email_exists(backend, details, uid, user=None, *args, **kwargs):
    email = details.get('email', '')

    # check if given email is in use
    exists = User.objects.filter(email=email).exists()

    # user is not logged in, social profile with given uid doesn't exist
    # and email is in use
    if not user and exists:
        raise AuthFailed(backend)