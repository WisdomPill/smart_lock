from rest_framework.authentication import BaseAuthentication


class NoAuthentication(BaseAuthentication):
    """
    No authentication
    """

    def authenticate(self, request):
        """ """
        ...
