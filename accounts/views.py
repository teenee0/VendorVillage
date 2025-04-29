

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.http import Http404
from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout

from accounts.forms import RegistrationForm
@login_required
def account(request):
    user = request.user
    business_status = request.user.groups.filter(name='Business').exists()
    context = {'user': user,
               'business_status': business_status}
    return render(request, 'accounts/account.html', context)
@login_required
def my_business(request):
    if request.user.groups.filter(name='Business').exists():
        user_businesses = request.user.businesses.all()
        context = {'user_businesses': user_businesses}
        return render(request, 'accounts/businesses.html', context)
    else:
        raise Http404

def logout_view(request):
    logout(request)
    return redirect('/')

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('accounts:account')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


# API
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework import status
from django.contrib.auth import authenticate
from .serializers import UserSerializer
from .JWT_AUTH import CookieJWTAuthentication 

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Сериализация данных
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Создание refresh токена для пользователя
        refresh = RefreshToken.for_user(user)
        
        # Формирование ответа
        response = Response({
            'detail': 'Registration successful',
        })

        # Устанавливаем access токен в куку
        response.set_cookie(
            key='access',
            value=str(refresh.access_token),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax',
            max_age=60 * 60 * 24,  # 1 день
            path='/'
        )
        
        # Устанавливаем refresh токен в куку
        response.set_cookie(
            key='refresh',
            value=str(refresh),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax',
            max_age=60 * 60 * 24 * 7,  # 7 дней
            path='/accounts/api/token/refresh/'
        )

        return response


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({'error': 'Invalid credentials'}, 
                             status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        
        # Формирование ответа
        response = Response({
            'detail': 'Login successful',
        })
        
        # Устанавливаем access токен в куку
        response.set_cookie(
            key='access',
            value=str(refresh.access_token),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax',
            max_age=60 * 5,  # 5минут
            path='/'
        )
        
        # Устанавливаем refresh токен в куку
        response.set_cookie(
            key='refresh',
            value=str(refresh),
            httponly=True,
            secure=not settings.DEBUG,
            samesite='Lax',
            max_age=60 * 60 * 24 * 90,  # 90 дней
            path='/accounts/api/token/refresh/'
        )
        
        return response


@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def me(request):
    # Если дошли сюда — пользователь авторизован
    return Response({
        'authenticated': True,
        'user': UserSerializer(request.user).data
    })


@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def account_view(request):
    return Response({'username': request.user.username})


@api_view(['GET'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def account_info(request):
    user = request.user
    is_business = user.roles.filter(name='Business').exists()
    return Response({
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'is_business': is_business,
        'roles': [r.name for r in user.roles.all()]
    })


@api_view(['POST'])
@authentication_classes([CookieJWTAuthentication])
@permission_classes([IsAuthenticated])
def logout_api(request):
    response = Response({'detail': 'Logout successful'}, status=status.HTTP_200_OK)
    response.delete_cookie('access', path='/')
    response.delete_cookie('refresh', path='/accounts/api/token/refresh/')
    return response


# пример авторизации на класс вью
# class AccountView(APIView):
#     authentication_classes = [CookieJWTAuthentication]
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         return Response({'username': request.user.username})
# для функций достаточно после апи вью сделать декоратор 
# @authentication_classes([CookieJWTAuthentication])
