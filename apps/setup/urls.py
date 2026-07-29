# apps/setup/urls.py
from django.urls import path

from .views import SetupWizardView



app_name = "setup"



urlpatterns = [

    path(

        "",

        SetupWizardView.as_view(),

        name="wizard"

    ),

]
