from rest_framework import viewsets, permissions, filters, status, views, response
from .models import User, Ombor, Kategoriya, Birlik, Mahsulot, Purchase, PurchaseItem, Sotuv, SotuvItem, Payment, OmborMahsulot, SotuvQaytarishItem, SotuvQaytarish
from .serializers import UserSerializer, OmborSerializer, KategoriyaSerializer, BirlikSerializer, MahsulotSerializer, PurchaseSerializer, PurchaseItemSerializer, SotuvSerializer, SotuvItemSerializer, PaymentSerializer, LoginSerializer, OmborMahsulotSerializer, TokenSerializer, LogoutSerializer, SotuvQaytarishSerializer, SotuvQaytarishItemSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime
from .permissions import CanCreateShopPermission  # Yangi ruxsat sinfi import qilinadi
from rest_framework.pagination import PageNumberPagination
from django.conf import settings
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend


class CustomPagination(PageNumberPagination):
    def get_paginated_response(self, data):
        base_url = settings.BASE_URL  # 'https://lemoonapi.cdpos.uz:444'
        next_link = self.get_next_link()
        previous_link = self.get_previous_link()

        # Noto‘g‘ri domenni to‘g‘rilash
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
    """Sotuvlar bo'yicha hisobot"""
    sotuvlar = Sotuv.objects.annotate(month=TruncMonth('sana')).values('month').annotate(total_sum=Sum('total_sum')).order_by('month')
    data = [{'id': idx + 1, 'month': item['month'].strftime('%Y-%m'), 'total_sum': float(item['total_sum']), 'created_by': request.user.id, 'created_at': datetime.now().isoformat()} for idx, item in enumerate(sotuvlar)]
    return Response(data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def xarid_hisoboti(request):
    """Xaridlar bo'yicha hisobot"""
    xaridlar = Purchase.objects.annotate(month=TruncMonth('sana')).values('month').annotate(total_sum=Sum('total_sum')).order_by('month')
    data = [{'id': idx + 1, 'month': item['month'].strftime('%Y-%m'), 'total_sum': float(item['total_sum']), 'created_by': request.user.id, 'created_at': datetime.now().isoformat()} for idx, item in enumerate(xaridlar)]
    return Response(data)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def ombor_hisoboti(request):
    """Omborlar bo'yicha hisobot"""
    omborlar = OmborMahsulot.objects.values('ombor__name').annotate(total_mahsulot=Sum('soni'))
    data = [{'id': idx + 1, 'ombor__name': item['ombor__name'], 'total_mahsulot': item['total_mahsulot'], 'created_by': request.user.id, 'created_at': datetime.now().isoformat()} for idx, item in enumerate(omborlar)]
    return Response(data)

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, CanCreateShopPermission]  # Yangi ruxsat sinfi qo‘shildi

    def get_queryset(self):
        user = self.request.user
        if user.user_type in ['admin', 'omborchi']:
            return User.objects.all().order_by('id')
        elif user.user_type == 'dealer':
            # Dealer faqat o‘zi qo‘shgan shop’larni ko‘radi
            return User.objects.filter(created_by=user).order_by('id')
        return User.objects.filter(id=user.id).order_by('id')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_type = serializer.validated_data.get('user_type')

        # Dealer faqat shop qo‘shishi mumkin, bu permission sinfida tekshiriladi
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # Agar dealer qo‘shayotgan bo‘lsa, created_by maydonini o‘rnatamiz
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
        else:
            return Response({"detail": "Sizda userni o'zgartirish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)

    def destroy(self, request, pk=None):
        user = self.get_object()
        if request.user.user_type in ['admin', 'omborchi']:
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
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
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "Sizda klient yaratish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)

# Qolgan ViewSet’lar o‘zgarmaydi
class OmborViewSet(viewsets.ModelViewSet):
    queryset = Ombor.objects.all().order_by('id')
    serializer_class = OmborSerializer
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
        else:
            return Response({"detail": "Sizda ombor yaratish huquqi yo'q."}, status=status.HTTP_403_FORBIDDEN)

    def perform_create(self, serializer):
        serializer.save(responsible_person=self.request.user)

class OmborMahsulotViewSet(viewsets.ModelViewSet):
    queryset = OmborMahsulot.objects.all().order_by('id')
    serializer_class = OmborMahsulotSerializer
    permission_classes = [permissions.IsAuthenticated]

class KategoriyaViewSet(viewsets.ModelViewSet):
    queryset = Kategoriya.objects.all().order_by('id')
    serializer_class = KategoriyaSerializer
    permission_classes = [permissions.IsAuthenticated]

class BirlikViewSet(viewsets.ModelViewSet):
    queryset = Birlik.objects.all().order_by('id')
    serializer_class = BirlikSerializer
    permission_classes = [permissions.IsAuthenticated]

class MahsulotViewSet(viewsets.ModelViewSet):
    queryset = Mahsulot.objects.all().order_by('id')
    serializer_class = MahsulotSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'sku', 'kategoriya__name']
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination  # Custom pagination qo‘shildi

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

    def reverse_warehouse_stock(self, purchase):
        """Purchase o‘chirilganda yoki tahrirlanganda eski zaxirani qaytarish"""
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
                    continue  # Agar mahsulot omborda bo‘lmasa, o‘tib ketamiz

    def update_warehouse_stock(self, purchase_data, ombor_id):
        """Yangi zaxirani qo‘shish"""
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
            self.reverse_warehouse_stock(instance)  # Ombordan sonni ayirish
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except OmborMahsulot.DoesNotExist:
            return Response({"detail": "Omborda mahsulot topilmadi, o‘chirish imkonsiz"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"O‘chirishda xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            # Eski zaxirani qaytarish (sonni ayirish)
            self.reverse_warehouse_stock(instance)
            # Eski item'larni o‘chirish
            instance.items.all().delete()
            # Yangi ma'lumotni saqlash va zaxirani yangilash (sonni qo‘shish)
            self.perform_update(serializer)
            self.update_warehouse_stock(serializer.validated_data, instance.ombor_id)

        return Response(serializer.data)


class SotuvViewSet(viewsets.ModelViewSet):
    queryset = Sotuv.objects.all().order_by('id')
    serializer_class = SotuvSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sana']  # Sana bo‘yicha umumiy filtrlash uchun

    def get_queryset(self):
        queryset = super().get_queryset()
        today = datetime.date.today()

        # Filtrlarni qo‘shimcha qo‘shish
        date_filter = self.request.query_params.get('date_filter', None)
        if date_filter:
            if date_filter == 'today':
                queryset = queryset.filter(sana__date=today)
            elif date_filter == 'yesterday':
                yesterday = today - datetime.timedelta(days=1)
                queryset = queryset.filter(sana__date=yesterday)
            elif date_filter == 'last_7_days':
                last_7_days = today - datetime.timedelta(days=6)
                queryset = queryset.filter(sana__date__range=[last_7_days, today])
            elif date_filter == 'this_month':
                first_day_of_month = today.replace(day=1)
                queryset = queryset.filter(sana__date__range=[first_day_of_month, today])
            elif date_filter == 'this_year':
                first_day_of_year = today.replace(month=1, day=1)
                queryset = queryset.filter(sana__date__range=[first_day_of_year, today])

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
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class SotuvQaytarishViewSet(viewsets.ModelViewSet):
    queryset = SotuvQaytarish.objects.all().order_by('id')
    serializer_class = SotuvQaytarishSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['sana']  # Sana bo‘yicha umumiy filtrlash uchun

    def get_queryset(self):
        queryset = super().get_queryset()
        today = datetime.date.today()

        # Filtrlarni qo‘shimcha qo‘shish
        date_filter = self.request.query_params.get('date_filter', None)
        if date_filter:
            if date_filter == 'today':
                queryset = queryset.filter(sana__date=today)
            elif date_filter == 'yesterday':
                yesterday = today - datetime.timedelta(days=1)
                queryset = queryset.filter(sana__date=yesterday)
            elif date_filter == 'last_7_days':
                last_7_days = today - datetime.timedelta(days=6)
                queryset = queryset.filter(sana__date__range=[last_7_days, today])
            elif date_filter == 'this_month':
                first_day_of_month = today.replace(day=1)
                queryset = queryset.filter(sana__date__range=[first_day_of_month, today])
            elif date_filter == 'this_year':
                first_day_of_year = today.replace(month=1, day=1)
                queryset = queryset.filter(sana__date__range=[first_day_of_year, today])

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
        qaytaruvchi = sotuv_qaytarish.qaytaruvchi
        qaytarish_ombor = sotuv_qaytarish.ombor

        try:
            qaytaruvchi_ombor = Ombor.objects.get(responsible_person=qaytaruvchi)
        except Ombor.DoesNotExist:
            raise ValueError("Qaytaruvchiga bog‘langan ombor topilmadi.")

        with transaction.atomic():
            for item in sotuv_qaytarish.items.all():
                ombor_mahsulot_qaytaruvchi, created = OmborMahsulot.objects.get_or_create(
                    ombor=qaytaruvchi_ombor,
                    mahsulot=item.mahsulot,
                    defaults={'soni': 0}
                )
                ombor_mahsulot_qaytaruvchi.soni += item.soni
                ombor_mahsulot_qaytaruvchi.save()

                try:
                    ombor_mahsulot_qaytarish = OmborMahsulot.objects.get(
                        ombor=qaytarish_ombor,
                        mahsulot=item.mahsulot
                    )
                    ombor_mahsulot_qaytarish.soni -= item.soni
                    if ombor_mahsulot_qaytarish.soni < 0:
                        raise ValueError(f"{item.mahsulot.name} uchun qaytarish omborda yetarli mahsulot yo‘q")
                    ombor_mahsulot_qaytarish.save()
                except OmborMahsulot.DoesNotExist:
                    raise ValueError(f"{item.mahsulot.name} qaytarish omborda topilmadi")

            qaytaruvchi.balance -= sotuv_qaytarish.total_sum
            qaytaruvchi.save()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.reverse_warehouse_stock(instance)
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": f"O‘chirishda xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)