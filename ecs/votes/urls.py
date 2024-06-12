from django.conf import settings
from django.urls import path, re_path

from ecs.votes import views


urlpatterns = (
    path('<int:vote_pk>/download/', views.download_vote, name='votes.download_vote'),
    path('<int:vote_pk>/english/', views.request_english_vote, name='votes.request_english_vote'),
    re_path('english/download/(?P<shasum>[0-9a-f]{40})/', views.download_english_vote, name='votes.download_english_vote'),
    path('<int:vote_pk>/sign', views.vote_sign, name='votes.vote_sign'),
)

if settings.DEBUG:
    urlpatterns += (
        path('<int:vote_pk>/pdf/debug/', views.vote_pdf_debug, name='votes.vote_pdf_debug'),
        path('<int:vote_pk>/pdf/english/debug/', views.vote_pdf_english_debug, name='votes.vote_pdf_english_debug'),
    )
