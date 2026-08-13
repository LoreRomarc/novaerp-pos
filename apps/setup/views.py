# apps/setup/views.py
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views import View

from .forms import SetupForm
from .service.setup_service import SetupService


class SetupWizardView(View):

    template_name = "setup/wizard.html"

    def get(self, request):

        form = SetupForm()

        return render(
            request,
            self.template_name,
            {
                "form": form,
            },
        )

    def post(self, request):

        form = SetupForm(request.POST)

        if not form.is_valid():

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                },
                status=400,
            )

        try:

            resultado = SetupService.crear_sistema(
                form.cleaned_data
            )

            messages.success(
                request,
                "El sistema fue configurado correctamente.",
            )

            return redirect("login")

        except Exception as error:

            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "error": str(error),
                },
                status=400,
            )