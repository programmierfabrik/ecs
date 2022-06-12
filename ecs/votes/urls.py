from django.conf import settings
from django.urls import path

from ecs.votes import views


urlpatterns = (
    path('<int:vote_pk>/download/', views.download_vote),
    path('<int:vote_pk>/sign', views.vote_sign),
)

if settings.DEBUG:
    urlpatterns += (
        path('<int:vote_pk>/pdf/debug/', views.vote_pdf_debug),
    )
