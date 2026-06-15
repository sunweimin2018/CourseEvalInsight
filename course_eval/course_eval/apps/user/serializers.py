from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=50)
    password = serializers.CharField(min_length=6, max_length=128)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)

    def validate_username(self, value):
        if not value[0].isalpha():
            raise serializers.ValidationError('Username must start with a letter')
        if not value.isalnum():
            raise serializers.ValidationError('Username can only contain letters and digits')
        return value


class UserInfoSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role')

    class Meta:
        model = User
        fields = ['id', 'username', 'role']


class UserListSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role')
    create_time = serializers.DateTimeField(source='profile.create_time')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'create_time']


class UserDetailSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', required=False)
    password = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role']

    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if role is not None:
            profile = instance.profile
            profile.role = role
            profile.save()
        return instance


class ProfileSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    current_password = serializers.CharField(write_only=True, required=False)
    new_password = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'current_password', 'new_password']

    def validate(self, attrs):
        current = attrs.pop('current_password', None)
        new = attrs.pop('new_password', None)
        if new and not current:
            raise serializers.ValidationError({'current_password': 'Current password is required to set a new password'})
        if current:
            if not self.instance.check_password(current):
                raise serializers.ValidationError({'current_password': 'Current password is incorrect'})
            attrs['password'] = new
        return attrs

    def update(self, instance, validated_data):
        phone = validated_data.pop('phone', None)
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if phone is not None:
            instance.profile.phone = phone
            instance.profile.save()
        return instance
