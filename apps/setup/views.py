# apps/setup/views.py
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth import login

from django.contrib.auth.models import User

from apps.core.models import (
    Empresa,
    Sucursal,
)


from apps.sales.models import Caja

from apps.sales.models_caja_enterprise import TurnoCaja

from apps.inventory.models import (
    Color,
    TipoTela,
    Talla,
)

from apps.customers.models import Cliente

from apps.setup.forms import SetupForm

from apps.setup.service.setup_service import SetupService

from apps.setup.service.setup_checker import SetupChecker



class SetupWizardView(View):


    template_name = "setup/wizard.html"



    def estado_configuracion(self):


        empresa = Empresa.objects.exists()


        sucursal = Sucursal.objects.exists()


        usuario = User.objects.exists()


        caja = Caja.objects.exists()


        turno = TurnoCaja.objects.filter(
            estado="ABIERTO"
        ).exists()


        datos_base = (

            Color.objects.exists()

            and TipoTela.objects.exists()

            and Talla.objects.exists()

            and Cliente.objects.exists()

        )


        return {


            "empresa": empresa,

            "sucursal": sucursal,

            "usuario": usuario,

            "caja": caja,

            "turno": turno,

            "datos_base": datos_base,

        }



    def get(self, request):


        form = SetupForm()


        return render(

            request,

            self.template_name,

            {

                "form": form,

                "estado": self.estado_configuracion()

            }

        )



    def post(self, request):


        form = SetupForm(
            request.POST
        )


        if form.is_valid():


            resultado = SetupService.crear_sistema(

                form.cleaned_data

            )


            login(
                request,
                resultado["usuario"]
            )

            print(
                "LOGIN SETUP:",
                request.user,
                request.user.is_authenticated,
                request.session.session_key
            )



            return redirect("/")



        return render(

            request,

            self.template_name,

            {

                "form": form,

                "estado": self.estado_configuracion()

            }

        )
