from rest_framework import serializers
from .models import User, Ombor, Kategoriya, Birlik, Mahsulot, Purchase, PurchaseItem, Sotuv, SotuvItem, Payment, \
    OmborMahsulot, SotuvQaytarish, SotuvQaytarishItem, ActivityLog, DealerRequestItem, DealerRequest
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
        fields = ['id', 'user', 'action', 'timestamp', 'details']  # 'time' olib tashlandi


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
        fields = ['id', 'name', 'sku', 'birlik', 'kategoriya', 'narx', 'rasm', 'time']

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
        fields = ['ombor', 'sana', 'yetkazib_beruvchi', 'items', 'total_sum', 'time']
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
        fields = ['id', 'sana', 'sotib_oluvchi', 'total_sum', 'ombor', 'items', 'time']
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


from rest_framework import serializers
from django.db import transaction
from .models import SotuvQaytarish, SotuvQaytarishItem, Ombor, OmborMahsulot, User


class SotuvQaytarishItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SotuvQaytarishItem
        fields = ['mahsulot', 'soni', 'narx', 'is_defective']


class SotuvQaytarishSerializer(serializers.ModelSerializer):
    items = SotuvQaytarishItemSerializer(many=True)

    class Meta:
        model = SotuvQaytarish
        fields = ['id', 'sana', 'qaytaruvchi', 'total_sum', 'ombor', 'condition', 'items', 'time']
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

    def update_user_balance(self, qaytaruvchi, total_sum):
        """Qaytaruvchi balansini yangilash."""
        qaytaruvchi.balance += total_sum  # Balansga total_sum qo'shiladi
        qaytaruvchi.save()

    def update_warehouse_stock(self, qaytaruvchi, ombor, items, condition):
        """Ombordagi mahsulot sonini yangilash."""
        qaytaruvchi_ombor = Ombor.objects.filter(responsible_person=qaytaruvchi).first()
        if not qaytaruvchi_ombor:
            raise serializers.ValidationError("Qaytaruvchiga biriktirilgan ombor topilmadi.")

        for item_data in items:
            mahsulot = item_data['mahsulot']
            soni = item_data['soni']

            # Qaytaruvchi omboridan mahsulotni ayirish
            ombor_mahsulot_qaytaruvchi, created = OmborMahsulot.objects.get_or_create(
                ombor=qaytaruvchi_ombor,
                mahsulot=mahsulot,
                defaults={'soni': 0}
            )
            if ombor_mahsulot_qaytaruvchi.soni < soni:
                raise serializers.ValidationError(f"{mahsulot.name} uchun omborda yetarli mahsulot yo‘q.")
            ombor_mahsulot_qaytaruvchi.soni -= soni
            ombor_mahsulot_qaytaruvchi.save()

            # Agar condition 'healthy' bo'lsa, tanlangan omborga mahsulot qo'shiladi
            if condition == 'healthy':
                ombor_mahsulot_qabul_qiluvchi, created = OmborMahsulot.objects.get_or_create(
                    ombor=ombor,
                    mahsulot=mahsulot,
                    defaults={'soni': 0}
                )
                ombor_mahsulot_qabul_qiluvchi.soni += soni
                ombor_mahsulot_qabul_qiluvchi.save()

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        qaytaruvchi = validated_data['qaytaruvchi']
        ombor = validated_data['ombor']
        condition = validated_data['condition']

        with transaction.atomic():
            sotuv_qaytarish = SotuvQaytarish.objects.create(**validated_data)
            total_sum = 0

            for item_data in items_data:
                mahsulot = item_data['mahsulot']
                soni = item_data['soni']
                narx = item_data['narx']

                sotuv_qaytarish_item = SotuvQaytarishItem.objects.create(
                    sotuv_qaytarish=sotuv_qaytarish,
                    mahsulot=mahsulot,
                    soni=soni,
                    narx=narx
                )
                total_sum += soni * narx

            sotuv_qaytarish.total_sum = total_sum
            sotuv_qaytarish.save()

            self.update_user_balance(qaytaruvchi, total_sum)
            self.update_warehouse_stock(qaytaruvchi, ombor, items_data, condition)

            return sotuv_qaytarish


class DealerRequestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealerRequestItem
        fields = ['product', 'quantity', 'price']


class DealerRequestSerializer(serializers.ModelSerializer):
    items = DealerRequestItemSerializer(many=True)

    class Meta:
        model = DealerRequest
        fields = ['id', 'dealer', 'shop', 'condition', 'status', 'total_sum', 'is_active', 'created_at', 'updated_at', 'items']
        extra_kwargs = {
            'id': {'read_only': True},
            'total_sum': {'read_only': True},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }

    def validate(self, data):
        user = self.context['request'].user
        shop = data.get('shop')
        items = data.get('items', [])
        dealer = data.get('dealer', None)

        if user.user_type not in ['dealer', 'admin']:
            raise serializers.ValidationError("Faqat diler yoki admin so‘rov yubora oladi.")
        if shop.user_type == 'admin':
            raise serializers.ValidationError("Shop admin bo‘lmasligi kerak.")
        if dealer and dealer.user_type == 'admin':
            raise serializers.ValidationError("Dealer admin bo‘lmasligi kerak.")
        if not items:
            raise serializers.ValidationError("Kamida bitta mahsulot qo‘shilishi kerak.")

        shop_ombor = Ombor.objects.filter(responsible_person=shop).first()
        if not shop_ombor:
            raise serializers.ValidationError("Do‘kon ombori topilmadi.")

        for item in items:
            product = item['product']
            quantity = item['quantity']
            ombor_mahsulot = OmborMahsulot.objects.filter(ombor=shop_ombor, mahsulot=product).first()
            if not ombor_mahsulot or ombor_mahsulot.soni < quantity:
                raise serializers.ValidationError(f"{product.name} uchun do‘kon omborida yetarli mahsulot yo‘q.")

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        if user.user_type == 'dealer' and 'dealer' not in validated_data:
            validated_data['dealer'] = user
        dealer_request = DealerRequest.objects.create(**validated_data)

        total_sum = 0
        for item_data in items_data:
            dealer_request_item = DealerRequestItem.objects.create(dealer_request=dealer_request, **item_data)
            total_sum += item_data['quantity'] * item_data['price']

        dealer_request.total_sum = total_sum
        dealer_request.save()
        return dealer_request