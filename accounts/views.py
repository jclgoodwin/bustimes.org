from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.contrib.auth.views import PasswordResetConfirmView

from .forms import RegistrationForm


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save(request=request)
    else:
        form = RegistrationForm()

    return render(request, 'register.html', {
        'form': form,
    })


class RegisterConfirmView(PasswordResetConfirmView):
    pass
