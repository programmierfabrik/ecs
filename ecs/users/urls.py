from django.urls import include, path, re_path

from ecs.users import views


urlpatterns = (
    path('accounts/login/', views.login, name='users.login'),
    path('accounts/logout/', views.logout),
    path('accounts/register/', views.register, name='users.register'),

    path('activate/<str:token>', views.activate, name='users.activate'),
    path('profile/', views.profile, name='users.profile'),
    path('profile/edit/', views.edit_profile),
    path('profile/change-password/', views.change_password),
    path('request-password-reset/', views.request_password_reset, name='users.request_password_reset'),
    path('password-reset/<str:token>', views.do_password_reset),
    path('users/<int:user_pk>/indisposition/', views.indisposition),
    path('users/notify_return/', views.notify_return),
    path('users/(<int:user_pk>/toggle_active/', views.toggle_active),
    path('users/(<int:user_pk>/details/', views.details),
    path('users/administration/', views.administration, name='users.administration'),
    path('users/invite/', views.invite, name='users.invite'),
    path('users/login_history/', views.login_history, name='users.login_history'),
    re_path(r'^accept_invitation/(?P<invitation_uuid>[\da-zA-Z]{32})/$', views.accept_invitation),
)
