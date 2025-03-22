from rest_framework import viewsets, permissions, filters, status, views, response
from .models import User, Ombor, Kategoriya, Birlik, Mahsulot, Purchase, PurchaseItem, Sotuv, SotuvItem, Payment, \
    OmborMahsulot, SotuvQaytarishItem, SotuvQaytarish, ActivityLog
from .serializers import UserSerializer, OmborSerializer, KategoriyaSerializer, BirlikSerializer, MahsulotSerializer, \
    PurchaseSerializer, PurchaseItemSerializer, SotuvSerializer, SotuvItemSerializer, PaymentSerializer, \
    LoginSerializer, OmborMahsulotSerializer, TokenSerializer, LogoutSerializer, SotuvQaytarishSerializer, \
    SotuvQaytarishItemSerializer, ActivityLogSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime
from .permissions import CanCreateShopPermission
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import datetime, time, timedelta


class CustomPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        base_url = settings.BASE_URL
        next_link = self.get_next_link()
        previous_link = self.get_previous_link()
        if next_link:
            next_link = next_link.replace('http://127.0.0.1:1111', base_url)
        if previous_link:
            previous_link = previous_link.replace('http://127.0.0.1:1111', base_url)
        return Response({
            'count': self.page.paginator.count,
            'next': next_link,
            'previous': previous_link,
            'results': data
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def sotuv_hisoboti(request):
    sotuvlar = Sotuv.objects.annotate(month=TruncMonth('sana')).values('month').annotate(
        total_sum=Sum('total_sum')).order_by('month')
    data = [{'id': idx + 1, 'month': item['month'].strftime('%Y-%m'), 'total_sum': float(item['total_sum']),
             'created_by': request.user.id, 'created_at': datetime.now().isoformat()} for idx, item in
            enumerate(sotuvlar)]
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def xarid_hisoboti(request):
    xaridlar = Purchase.objects.annotate(month=TruncMonth('sana')).values('month').annotate(
        total_sum=Sum('total_sum')).order_by('month')
    data = [{'id': idx + 1, 'month': item['month'].strftime('%Y-%m'), 'total_sum': float(item['total_sum']),
             'created_by': request.user.id, 'created_at': datetime.now().isoformat()} for idx, item in
            enumerate(xaridlar)]
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ombor_hisoboti(request):
    omborlar = OmborMahsulot.objects.values('ombor__name').annotate(total_mahsulot=Sum('soni'))
    data = [{'id': idx + 1, 'ombor__name': item['ombor__name'], 'total_mahsulot': item['total_mahsulot'],
             'created_by': request.user.id, 'created_at': datetime.now().isoformat()} for idx, item in
            enumerate(omborlar)]
    return Response(data)


class DealerShopsReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, dealer_id):
        if request.user.user_type not in ['admin', 'dealer']:
            return Response({"detail": "Faqat admin yoki dealerlar bu hisobotni ko‘ra oladi."},
                            status=status.HTTP_403_FORBIDDEN)

        dealer = User.objects.filter(id=dealer_id, user_type='dealer').first()
        if not dealer:
            return Response({"detail": "Diler topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        shops = User.objects.filter(created_by=dealer, user_type='shop')
        total_balance = shops.aggregate(total_balance=Sum('balance'))['total_balance'] or 0
        serializer = UserSerializer(shops, many=True)

        return Response({
            'dealer': dealer.username,
            'shops': serializer.data,
            'total_balance': float(total_balance)
        })


User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated, CanCreateShopPermission]

    def get_queryset(self):
        user = self.request.user
        if user.user_type in ['admin', 'omborchi']:
            return User.objects.all().order_by('id')
        elif user.user_type == 'dealer':
            return User.objects.filter(created_by=user).order_by('id')
        return User.objects.filter(id=user.id).order_by('id')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_type = serializer.validated_data.get('user_type')
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        if self.request.user.user_type == 'dealer':
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    def update(self, request, pk=None):
        user = self.get_object()
        if request.user.user_type in ['admin', 'omborchi']:
            serializer = UserSerializer(user, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response({"detail": "Sizda userni o'zgartirish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)

    def destroy(self, request, pk=None):
        user = self.get_object()
        if request.user.user_type in ['admin', 'omborchi']:
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"detail": "Sizda userni o'chirish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=['get'])
    def current_user(self, request):
        serializer = self.get_serializer(self.request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def create_klient(self, request):
        user = request.user
        if user.user_type in ['dealer', 'shop']:
            serializer = UserSerializer(data=request.data)
            if serializer.is_valid():
                klient = serializer.save(user_type='klient')
                return Response(UserSerializer(klient).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Sizda klient yaratish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)


class OmborViewSet(viewsets.ModelViewSet):
    queryset = Ombor.objects.all().order_by('id')
    serializer_class = OmborSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Ombor.objects.none()
        user = self.request.user
        if user.is_authenticated:
            if user.user_type in ['admin', 'omborchi']:
                return Ombor.objects.all().order_by('id')
            return Ombor.objects.filter(responsible_person=user).order_by('id')
        return Ombor.objects.none()

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.user_type in ['admin', 'omborchi', 'dealer', 'shop']:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        return Response({"detail": "Sizda ombor yaratish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)

    def perform_create(self, serializer):
        serializer.save(responsible_person=self.request.user)


class OmborMahsulotViewSet(viewsets.ModelViewSet):
    queryset = OmborMahsulot.objects.all().order_by('id')
    serializer_class = OmborMahsulotSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated]


class KategoriyaViewSet(viewsets.ModelViewSet):
    queryset = Kategoriya.objects.all().order_by('id')
    serializer_class = KategoriyaSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated]


class BirlikViewSet(viewsets.ModelViewSet):
    queryset = Birlik.objects.all().order_by('id')
    serializer_class = BirlikSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated]


class MahsulotViewSet(viewsets.ModelViewSet):
    queryset = Mahsulot.objects.all().order_by('id')
    serializer_class = MahsulotSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'sku', 'kategoriya__name']
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination

    def get_serializer_context(self):
        return {'request': self.request}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    pagination_class = CustomPagination

    def reverse_warehouse_stock(self, purchase):
        with transaction.atomic():
            for item in purchase.items.all():
                try:
                    warehouse_product = OmborMahsulot.objects.get(
                        ombor=purchase.ombor,
                        mahsulot=item.mahsulot
                    )
                    warehouse_product.soni -= item.soni
                    if warehouse_product.soni < 0:
                        raise ValueError(f"{item.mahsulot.name} uchun omborda yetarli mahsulot yo‘q")
                    warehouse_product.save()
                except OmborMahsulot.DoesNotExist:
                    continue

    def update_warehouse_stock(self, purchase_data, ombor_id):
        with transaction.atomic():
            for item in purchase_data['items']:
                mahsulot_id = item['mahsulot']
                soni = item['soni']
                warehouse_product, created = OmborMahsulot.objects.get_or_create(
                    ombor_id=ombor_id,
                    mahsulot_id=mahsulot_id,
                    defaults={'soni': 0}
                )
                warehouse_product.soni += soni
                warehouse_product.save()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.reverse_warehouse_stock(instance)
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except OmborMahsulot.DoesNotExist:
            return Response({"detail": "Omborda mahsulot topilmadi, o‘chirish imkonsiz"},
                            status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"O‘chirishda xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            self.reverse_warehouse_stock(instance)
            instance.items.all().delete()
            self.perform_update(serializer)
            self.update_warehouse_stock(serializer.validated_data, instance.ombor_id)
        return Response(serializer.data)


class SotuvViewSet(viewsets.ModelViewSet):
    queryset = Sotuv.objects.all().order_by('-id')
    serializer_class = SotuvSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sana']
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        today = timezone.now().date()
        date_filter = self.request.query_params.get('date_filter', None)
        if date_filter:
            if date_filter == 'today':
                start_of_day = datetime.combine(today, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'yesterday':
                yesterday = today - timedelta(days=1)
                start_of_day = datetime.combine(yesterday, time.min)
                end_of_day = datetime.combine(yesterday, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'last_7_days':
                last_7_days = today - timedelta(days=6)
                start_of_day = datetime.combine(last_7_days, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'this_month':
                first_day_of_month = today.replace(day=1)
                start_of_day = datetime.combine(first_day_of_month, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'this_year':
                first_day_of_year = today.replace(month=1, day=1)
                start_of_day = datetime.combine(first_day_of_year, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

    def destroy(self, request, pk=None):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()

    def destroy(self, request, pk=None):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginAPIView(views.APIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return response.Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)


class LogoutAPIView(views.APIView):
    serializer_class = LogoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh_token = serializer.validated_data['refresh_token']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return response.Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return response.Response({'error': 'Invalid refresh token'}, status=status.HTTP_400_BAD_REQUEST)


class TokenAPIView(views.APIView):
    serializer_class = TokenSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            return response.Response(serializer.validated_data, status=status.HTTP_200_OK)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActivityLogViewSet(viewsets.ModelViewSet):
    queryset = ActivityLog.objects.all().order_by('-timestamp')
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user']
    pagination_class = CustomPagination


from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from datetime import datetime, time, timedelta
from django.utils import timezone
from .models import SotuvQaytarish, Ombor, OmborMahsulot
from .serializers import SotuvQaytarishSerializer

class SotuvQaytarishViewSet(viewsets.ModelViewSet):
    queryset = SotuvQaytarish.objects.all().order_by('-id')
    serializer_class = SotuvQaytarishSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sana']
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        today = timezone.now().date()
        date_filter = self.request.query_params.get('date_filter', None)
        if date_filter:
            if date_filter == 'today':
                start_of_day = datetime.combine(today, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'yesterday':
                yesterday = today - timedelta(days=1)
                start_of_day = datetime.combine(yesterday, time.min)
                end_of_day = datetime.combine(yesterday, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'last_7_days':
                last_7_days = today - timedelta(days=6)
                start_of_day = datetime.combine(last_7_days, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'this_month':
                first_day_of_month = today.replace(day=1)
                start_of_day = datetime.combine(first_day_of_month, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
            elif date_filter == 'this_year':
                first_day_of_year = today.replace(month=1, day=1)
                start_of_day = datetime.combine(first_day_of_year, time.min)
                end_of_day = datetime.combine(today, time.max)
                queryset = queryset.filter(sana__gte=start_of_day, sana__lte=end_of_day)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save()

    def reverse_warehouse_stock(self, sotuv_qaytarish):
        """Ombordagi mahsulot sonini teskari o'zgartirish."""
        qaytaruvchi = sotuv_qaytarish.qaytaruvchi
        qaytarish_ombor = sotuv_qaytarish.ombor
        condition = sotuv_qaytarish.condition

        try:
            qaytaruvchi_ombor = Ombor.objects.get(responsible_person=qaytaruvchi)
        except Ombor.DoesNotExist:
            raise ValueError("Qaytaruvchiga bog‘langan ombor topilmadi.")

        for item in sotuv_qaytarish.items.all():
            try:
                # Qaytaruvchi omboriga mahsulotni qaytarish
                ombor_mahsulot_qaytaruvchi = OmborMahsulot.objects.get(
                    ombor=qaytaruvchi_ombor,
                    mahsulot=item.mahsulot
                )
                ombor_mahsulot_qaytaruvchi.soni += item.soni
                ombor_mahsulot_qaytaruvchi.save()

                # Qaytarish omboridan mahsulotni ayirish
                ombor_mahsulot_qaytarish = OmborMahsulot.objects.get(
                    ombor=qaytarish_ombor,
                    mahsulot=item.mahsulot
                )
                ombor_mahsulot_qaytarish.soni -= item.soni
                ombor_mahsulot_qaytarish.save()

                # Sog'lom mahsulotlar uchun admin omboridan mahsulotni ayirish
                if condition == 'healthy':
                    admin_ombor = Ombor.objects.filter(responsible_person__user_type='admin').first()
                    if admin_ombor:
                        ombor_mahsulot_admin = OmborMahsulot.objects.get(
                            ombor=admin_ombor,
                            mahsulot=item.mahsulot
                        )
                        ombor_mahsulot_admin.soni -= item.soni
                        ombor_mahsulot_admin.save()

            except OmborMahsulot.DoesNotExist:
                raise ValueError(f"{item.mahsulot.name} omborda topilmadi")

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            with transaction.atomic():
                self.reverse_warehouse_stock(instance)
                instance.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)

        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"detail": f"O‘chirishda xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)