from rest_framework import serializers
from .models import User, Ombor, Kategoriya, Birlik, Mahsulot, Purchase, PurchaseItem, Sotuv, SotuvItem, Payment, \
    OmborMahsulot
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from rest_framework import exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
        'id', 'username', 'password', 'email', 'user_type', 'address', 'phone_number', 'is_active', 'last_sotuv_vaqti',
        'balance', 'created_by')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = get_user_model().objects.create_user(**validated_data, password=password)
        return user

    def update(self, instance, validated_data):
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)

    def validate_email(self, value):
        if "@" not in value:
            raise serializers.ValidationError("Email manzilida @ belgisi bo'lishi kerak.")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get('username', None)
        password = data.get('password', None)

        if username and password:
            user = authenticate(username=username, password=password)
            if user:
                if user.is_active:
                    data['user'] = user
                else:
                    raise exceptions.AuthenticationFailed('User is inactive.')
            else:
                raise exceptions.AuthenticationFailed('Invalid credentials.')
        else:
            raise exceptions.AuthenticationFailed('Must include "username" and "password".')
        return data


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class OmborSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ombor
        fields = '__all__'


class OmborMahsulotSerializer(serializers.ModelSerializer):
    mahsulot_name = serializers.ReadOnlyField(source='mahsulot.name')
    ombor_name = serializers.ReadOnlyField(source='ombor.name')

    class Meta:
        model = OmborMahsulot
        fields = ['id', 'ombor', 'ombor_name', 'mahsulot', 'mahsulot_name', 'soni']


class KategoriyaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kategoriya
        fields = '__all__'


class BirlikSerializer(serializers.ModelSerializer):
    class Meta:
        model = Birlik
        fields = '__all__'


class MahsulotSerializer(serializers.ModelSerializer):
    rasm = serializers.SerializerMethodField()

    def get_rasm(self, obj):
        if obj.rasm:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.rasm.url)
            return f"https://lemoonapi.cdpos.uz:444{obj.rasm.url}"  # Agar request bo‘lmasa, statik URL
        return None

    class Meta:
        model = Mahsulot
        fields = '__all__'

    def validate_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Mahsulot nomi juda qisqa bo'lishi mumkin emas.")
        return value

    def validate_narx(self, value):
        if value <= 0:
            raise serializers.ValidationError("Mahsulot narxi 0 dan katta bo'lishi kerak.")
        return value


class PurchaseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = ['mahsulot', 'soni', 'narx', 'yaroqlilik_muddati']

class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True)
    yetkazib_beruvchi = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Purchase
        fields = ['ombor', 'sana', 'yetkazib_beruvchi', 'items', 'total_sum'] # total_sum maydonini qo'shish
        extra_kwargs = {'id': {'read_only': True}, 'total_sum': {'read_only': True}}  # total_sum ham faqat o‘qish uchun

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        purchase = Purchase.objects.create(**validated_data)

        total_sum = 0
        for item_data in items_data:
            purchase_item = PurchaseItem.objects.create(purchase=purchase, **item_data)
            total_sum += purchase_item.soni * purchase_item.narx

        purchase.total_sum = total_sum
        purchase.save()  # Balansni avtomatik yangilash uchun

        return purchase


class SotuvItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SotuvItem
        fields = ['mahsulot', 'soni', 'narx']

class SotuvSerializer(serializers.ModelSerializer):
    items = SotuvItemSerializer(many=True)

    class Meta:
        model = Sotuv
        fields = ['id','sana', 'sotib_oluvchi', 'total_sum', 'ombor', 'items'] # id olib tashlandi, total_sum ni qo'shdik
        extra_kwargs = {'id': {'read_only': True}, 'total_sum': {'read_only': True}, 'sana': {'read_only': True}}  # id va sana faqat o‘qish uchun

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sotuv = Sotuv.objects.create(**validated_data)

        total_sum = 0
        for item_data in items_data:
            sotuv_item = SotuvItem.objects.create(sotuv=sotuv, **item_data)
            total_sum += sotuv_item.soni * sotuv_item.narx

        sotuv.total_sum = total_sum
        sotuv.save()  # total_sum va balansni yangilash

        return sotuv


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


class TokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token