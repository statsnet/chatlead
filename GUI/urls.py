from django.urls import path

from . import views
from . import api
from django.conf.urls.static import static

from chat_api.settings import MEDIA_URL, UPLOAD_PATH, STATIC_URL, STATIC_ROOT

urlpatterns = [
                  path(r"vk_api/<int:pk>", views.vk_api, name="vk_api_pk"),
                  path(r"fb_api", views.fb_api),
                  path(r"facebook_webhook/", views.facebook_webhook, name="facebook_webhook"),
                  *[
                      path(f"api/{ApiMethod.__name__}/", ApiMethod().view, name=ApiMethod.__name__)
                      for ApiMethod in api.all_methods
                  ]
              ] + static(STATIC_URL, document_root=STATIC_ROOT) + static(MEDIA_URL, document_root=UPLOAD_PATH)

print(urlpatterns)
