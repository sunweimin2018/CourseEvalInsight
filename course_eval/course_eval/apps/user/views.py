from datetime import datetime

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from course_eval.utils.response import api_response
from .models import UserProfile
from .permissions import IsAdminUser
from .redis_client import (
    add_to_blacklist,
    store_refresh_token,
    revoke_user_tokens,
    validate_refresh_token,
)
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserInfoSerializer,
    UserListSerializer,
    UserDetailSerializer,
    ProfileSerializer,
)


def _generate_tokens(user):
    refresh = RefreshToken.for_user(user)
    ttl = int(refresh.lifetime.total_seconds())
    store_refresh_token(user.id, refresh['jti'], ttl)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(code=400, msg='Invalid input', http_status=400)

        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if not user:
            return api_response(code=401, msg='用户名或密码错误', http_status=401)

        UserProfile.objects.get_or_create(user=user)
        tokens = _generate_tokens(user)
        user_info = UserInfoSerializer(user).data
        return api_response(data={'access': tokens['access'], 'refresh': tokens['refresh'], 'user': user_info})


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            msg = '. '.join(f'{k}: {v[0]}' for k, v in errors.items())
            return api_response(code=400, msg=msg, http_status=400)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        phone = serializer.validated_data.get('phone', '')
        email = serializer.validated_data.get('email', '')

        if User.objects.filter(username=username).exists():
            return api_response(code=400, msg='Username already exists', http_status=400)

        user = User.objects.create_user(username=username, password=password, email=email)
        UserProfile.objects.create(user=user, phone=phone)
        tokens = _generate_tokens(user)
        user_info = UserInfoSerializer(user).data
        return api_response(data={'access': tokens['access'], 'refresh': tokens['refresh'], 'user': user_info})


class LogoutView(APIView):
    def post(self, request):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            from rest_framework_simplejwt.tokens import AccessToken
            try:
                raw_token = auth_header.split(' ')[1]
                token = AccessToken(raw_token)
                access_ttl = (datetime.fromtimestamp(token['exp']) - datetime.now()).total_seconds()
                if access_ttl > 0:
                    add_to_blacklist(token['jti'], int(access_ttl))
            except Exception:
                pass

        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                jti = token['jti']
                user_id = token['user_id']
                revoke_user_tokens(user_id)
                add_to_blacklist(token['jti'], int(token.lifetime.total_seconds()))
            except Exception:
                pass

        return api_response(msg='Logged out')


class TokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return api_response(code=400, msg='Refresh token is required', http_status=400)

        try:
            token = RefreshToken(refresh_token)
            jti = token['jti']
            user_id = token['user_id']

            if not validate_refresh_token(user_id, jti):
                return api_response(code=401, msg='Refresh token revoked', http_status=401)

            revoke_user_tokens(user_id)
            add_to_blacklist(jti, int(token.lifetime.total_seconds()))
            token.blacklist()

            user = User.objects.get(pk=user_id)
            tokens = _generate_tokens(user)
            return api_response(data={'access': tokens['access'], 'refresh': tokens['refresh']})
        except Exception:
            return api_response(code=401, msg='Invalid refresh token', http_status=401)


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        search = request.query_params.get('search', '')

        queryset = User.objects.filter(profile__role='user').select_related('profile')
        if search:
            queryset = queryset.filter(username__icontains=search)

        total = queryset.count()
        start = (page - 1) * page_size
        users = queryset.order_by('-profile__create_time')[start : start + page_size]

        return api_response(data={
            'users': UserListSerializer(users, many=True).data,
            'total': total,
            'page': page,
            'page_size': page_size,
        })

    def post(self, request):
        serializer = UserDetailSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(code=400, msg=str(serializer.errors), http_status=400)

        username = serializer.validated_data['username']
        if User.objects.filter(username=username).exists():
            return api_response(code=400, msg='Username already exists', http_status=400)

        password = serializer.validated_data.pop('password', 'default123')
        role = serializer.validated_data.pop('role', 'user')
        user = User.objects.create_user(username=username, password=password)
        user.email = serializer.validated_data.get('email', '')
        user.save()
        UserProfile.objects.update_or_create(user=user, defaults={'role': role})
        return api_response(data=UserListSerializer(user).data, msg='User created')


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, pk):
        try:
            user = User.objects.select_related('profile').get(pk=pk)
        except User.DoesNotExist:
            return api_response(code=404, msg='User not found', http_status=404)
        return api_response(data=UserDetailSerializer(user).data)

    def put(self, request, pk):
        try:
            user = User.objects.select_related('profile').get(pk=pk)
        except User.DoesNotExist:
            return api_response(code=404, msg='User not found', http_status=404)

        serializer = UserDetailSerializer(user, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_response(code=400, msg=str(serializer.errors), http_status=400)
        serializer.save()
        return api_response(data=UserListSerializer(user).data, msg='User updated')

    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return api_response(code=404, msg='User not found', http_status=404)
        if user.profile.role == 'admin':
            return api_response(code=400, msg='Cannot delete admin user', http_status=400)
        user.delete()
        return api_response(msg='User deleted')


class CheckUsernameView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        username = request.query_params.get('username', '')
        if not username:
            return api_response(code=400, msg='Username is required', http_status=400)
        exists = User.objects.filter(username=username).exists()
        return api_response(data={'exists': exists})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_response(data=ProfileSerializer(request.user).data)

    def put(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return api_response(code=400, msg=str(serializer.errors), http_status=400)
        serializer.save()
        return api_response(data=ProfileSerializer(request.user).data, msg='Profile updated')
