from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from core import views

app_name = 'core'

userRoutes = DefaultRouter()
userRoutes.register(r'user/search', views.UserViewSet)
userRoutes.register(r'user/game', views.GameViewSet)

roomRoutes = DefaultRouter()
roomRoutes.register('room', views.RoomViewSet)

reviewRouter = routers.NestedSimpleRouter(roomRoutes, r'room', lookup='room')
reviewRouter.register(r'review', views.ReviewViewSet)

urlpatterns = [
    path('', include(roomRoutes.urls)),
    path('', include(reviewRouter.urls)),
    path('user/create/', views.CreateUserView.as_view(), name='create'),
    path('user/token/', views.CreateTokenView.as_view(), name='token'),
    path('user/profile/', views.ManageUserView.as_view(), name='profile'),
    path('', include(userRoutes.urls)),
    path('search_fields/', views.SearchFieldsView.as_view(), name='search'),
    path('user/auth/', views.SocialLoginView.as_view())
]
