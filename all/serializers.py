from rest_framework import serializers
from .models import User, Ombor, Kategoriya, Birlik, Mahsulot, Purchase, PurchaseItem, Sotuv, SotuvItem, Payment, \
    OmborMahsulot, SotuvQaytarish, SotuvQaytarishItem, ActivityLog
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from rest_framework import exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            'id', 'username', 'password', 'email', 'user_type', 'address', 'phone_number', 'is_active',
            'last_sotuv_vaqti', 'balance', 'created_by', 'image'
        )
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


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'action', 'timestamp', 'details']


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
            base_url = 'https://lemoonapi.cdpos.uz:444'
            return f"{base_url}{obj.rasm.url}"
        return None

    class Meta:
        model = Mahsulot
        fields = ['id', 'name', 'sku', 'birlik', 'kategoriya', 'narx', 'rasm']

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
        fields = ['ombor', 'sana', 'yetkazib_beruvchi', 'items', 'total_sum']
        extra_kwargs = {'id': {'read_only': True}, 'total_sum': {'read_only': True}}

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        purchase = Purchase.objects.create(**validated_data)
        total_sum = 0
        for item_data in items_data:
            purchase_item = PurchaseItem.objects.create(purchase=purchase, **item_data)
            total_sum += purchase_item.soni * purchase_item.narx
        purchase.total_sum = total_sum
        purchase.save()
        return purchase

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        instance.items.all().delete()
        instance.ombor = validated_data.get('ombor', instance.ombor)
        instance.sana = validated_data.get('sana', instance.sana)
        instance.yetkazib_beruvchi = validated_data.get('yetkazib_beruvchi', instance.yetkazib_beruvchi)
        instance.save()
        total_sum = 0
        if items_data:
            for item_data in items_data:
                purchase_item = PurchaseItem.objects.create(purchase=instance, **item_data)
                total_sum += purchase_item.soni * purchase_item.narx
        instance.total_sum = total_sum
        instance.save()
        return instance


class SotuvItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SotuvItem
        fields = ['mahsulot', 'soni', 'narx']


class SotuvSerializer(serializers.ModelSerializer):
    items = SotuvItemSerializer(many=True)

    class Meta:
        model = Sotuv
        fields = ['id', 'sana', 'sotib_oluvchi', 'total_sum', 'ombor', 'items']
        extra_kwargs = {'id': {'read_only': True}, 'total_sum': {'read_only': True}, 'sana': {'read_only': True}}

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sotuv = Sotuv.objects.create(**validated_data)
        total_sum = 0
        for item_data in items_data:
            sotuv_item = SotuvItem.objects.create(sotuv=sotuv, **item_data)
            total_sum += sotuv_item.soni * sotuv_item.narx
        sotuv.total_sum = total_sum
        sotuv.save()
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


class SotuvQaytarishItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SotuvQaytarishItem
        fields = ['mahsulot', 'soni', 'narx']


class SotuvQaytarishSerializer(serializers.ModelSerializer):
    items = SotuvQaytarishItemSerializer(many=True)

    class Meta:
        model = SotuvQaytarish
        fields = ['id', 'sana', 'qaytaruvchi', 'total_sum', 'ombor', 'condition', 'items']
        extra_kwargs = {
            'id': {'read_only': True},
            'sana': {'read_only': True},
            'total_sum': {'read_only': True}
        }

    def validate(self, data):
        qaytaruvchi = data.get('qaytaruvchi')
        items = data.get('items', [])
        ombor = data.get('ombor')
        condition = data.get('condition')

        if not items:
            raise serializers.ValidationError("Kamida bitta mahsulot qaytarilishi kerak.")

        try:
            qaytaruvchi_ombor = Ombor.objects.get(responsible_person=qaytaruvchi)
        except Ombor.DoesNotExist:
            raise serializers.ValidationError("Qaytaruvchiga bog‘langan ombor topilmadi.")

        for item in items:
            mahsulot = item['mahsulot']
            soni = item['soni']
            try:
                ombor_mahsulot = OmborMahsulot.objects.get(ombor=qaytaruvchi_ombor, mahsulot=mahsulot)
                if ombor_mahsulot.soni < soni:
                    raise serializers.ValidationError(
                        f"{mahsulot.name} uchun qaytaruvchi omborda yetarli mahsulot yo‘q. Mavjud: {ombor_mahsulot.soni}, talab qilingan: {soni}"
                    )
            except OmborMahsulot.DoesNotExist:
                raise serializers.ValidationError(f"{mahsulot.name} mahsuloti qaytaruvchi omborda mavjud emas.")

        return data

    def create(self, validated_data):
        from django.db import transaction
        items_data = validated_data.pop('items')
        qaytaruvchi = validated_data['qaytaruvchi']
        ombor = validated_data['ombor']
        condition = validated_data['condition']

        try:
            qaytaruvchi_ombor = Ombor.objects.get(responsible_person=qaytaruvchi)
        except Ombor.DoesNotExist:
            raise serializers.ValidationError("Qaytaruvchiga bog‘langan ombor topilmadi.")

        with transaction.atomic():
            sotuv_qaytarish = SotuvQaytarish.objects.create(**validated_data)
            total_sum = 0

            for item_data in items_data:
                mahsulot = item_data['mahsulot']
                soni = item_data['soni']
                narx = item_data['narx']

                ombor_mahsulot = OmborMahsulot.objects.get(ombor=qaytaruvchi_ombor, mahsulot=mahsulot)
                if ombor_mahsulot.soni < soni:
                    raise serializers.ValidationError(f"{mahsulot.name} uchun omborda yetarli mahsulot yo‘q.")
                ombor_mahsulot.soni -= soni
                ombor_mahsulot.save()

                qaytarish_ombor_mahsulot, created = OmborMahsulot.objects.get_or_create(
                    ombor=ombor,
                    mahsulot=mahsulot,
                    defaults={'soni': 0}
                )
                qaytarish_ombor_mahsulot.save()

                sotuv_qaytarish_item = SotuvQaytarishItem.objects.create(
                    sotuv_qaytarish=sotuv_qaytarish,
                    mahsulot=mahsulot,
                    soni=soni,
                    narx=narx
                )
                total_sum += soni * narx

            sotuv_qaytarish.total_sum = total_sum
            sotuv_qaytarish.save()
            return sotuv_qaytarish