from rest_framework import permissions


class CanCreateShopPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # Agar GET so‘rovi bo‘lsa, hamma uchun ruxsat
        if request.method in permissions.SAFE_METHODS:
            return True

        # Autentifikatsiya qilinmagan foydalanuvchilar uchun ruxsat yo‘q
        if not request.user.is_authenticated:
            return False

        # Admin va Omborchi hamma turdagi foydalanuvchilarni qo‘shishi mumkin
        if request.user.user_type in ['admin', 'omborchi']:
            return True

        # Dealer faqat shop qo‘shishi mumkin
        if request.user.user_type == 'dealer':
            user_type = request.data.get('user_type')
            return user_type == 'shop'

        # Boshqa rollar (masalan, shop) hech narsa qo‘sholmaydi
        return False