# apps/setup/views.py
from django.shortcuts import redirect, render
from django.views import View

from .forms import SetupForm
from .service.setup_checker import SetupChecker
from .service.setup_service import SetupService


class SetupWizardView(View):
    template_name = "setup/wizard.html"

    def get(self, request):
        # El setup solo puede ejecutarse una vez.
        if SetupChecker.sistema_configurado():
            return redirect("inicio")

        return render(
            request,
            self.template_name,
            {
                "form": SetupForm(),
                "sistema_instalado": False,
            },
        )

    def post(self, request):
        # Protección adicional ante reenvíos, doble clics
        # o acceso directo a la URL.
        if SetupChecker.sistema_configurado():
            return redirect("inicio")

        form = SetupForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "sistema_instalado": False,
                },
                status=400,
            )

        try:
            SetupService.crear_sistema(form.cleaned_data)

        except Exception as error:
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "error": str(error),
                    "sistema_instalado": False,
                },
                status=400,
            )

        return redirect("login")