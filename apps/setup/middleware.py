# apps/setup/middleware.py
from django.shortcuts import redirect
from django.urls import reverse

from apps.setup.service.setup_checker import SetupChecker



class SetupWizardMiddleware:


    def __init__(self, get_response):

        self.get_response = get_response



    def __call__(self, request):


        # ==========================================
        # RUTAS QUE NUNCA DEBEN BLOQUEARSE
        # ==========================================

        rutas_excluidas = [

            reverse("setup:wizard"),

            "/admin/",

            "/login/",

            "/logout/",

            "/static/",

            "/media/",

        ]



        # ==========================================
        # SI YA ESTA CONFIGURADO
        # CONTINUAR NORMAL
        # ==========================================

        if SetupChecker.sistema_configurado():

            return self.get_response(request)



        # ==========================================
        # PERMITIR RECURSOS DEL SETUP
        # ==========================================

        for ruta in rutas_excluidas:


            if request.path.startswith(ruta):

                return self.get_response(request)



        # ==========================================
        # REDIRIGIR AL ASISTENTE
        # ==========================================

        return redirect(
            "setup:wizard"
        )

