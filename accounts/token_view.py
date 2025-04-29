from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.permissions import AllowAny
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import User

class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token_str = request.COOKIES.get('refresh')

        if not refresh_token_str:
            return Response(
                {'error': 'Refresh token is missing'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh_token = RefreshToken(refresh_token_str)
            user_id = refresh_token['user_id']
            user = User.objects.get(id=user_id)
            
            # можно оставить старый refresh токен и выдать новый access
            access_token = refresh_token.access_token

            response = Response({'detail': 'refresh successful'}, status=status.HTTP_200_OK)

            response.set_cookie(
                key='access',
                value=str(access_token),
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=60 * 5,  # 5 минут
                path='/'
            )
            return response

        except (TokenError, InvalidToken):
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
        
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
