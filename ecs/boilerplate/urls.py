from django.urls import path

from ecs.boilerplate import views


urlpatterns = (
    path('list/', views.list_boilerplate, name='boilerplate.list_boilerplate'),
    path('new/', views.edit_boilerplate),
    path('(<int:text_pk>)/edit/', views.edit_boilerplate),
    path('(<int:text_pk>)/delete/', views.delete_boilerplate),
    path('select/', views.select_boilerplate),
)
