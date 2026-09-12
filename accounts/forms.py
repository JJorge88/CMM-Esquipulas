from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

from .models import PerfilUsuario


class DatosUsuarioForm(forms.Form):
    first_name = forms.CharField(
        label="Nombres", max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="Apellidos", max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    username = forms.CharField(
        label="Nombre de usuario", max_length=150,
        validators=[UnicodeUsernameValidator()],
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Correo electrónico", required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    telefono = forms.CharField(
        label="Teléfono", max_length=20, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    rol = forms.ChoiceField(
        label="Rol", choices=PerfilUsuario.Rol.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    estado_activo = forms.BooleanField(
        label="Cuenta activa", required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"]
        existentes = User.objects.filter(username__iexact=username)
        if self.usuario is not None:
            existentes = existentes.exclude(pk=self.usuario.pk)
        if existentes.exists():
            raise ValidationError("Este nombre de usuario ya está en uso.")
        return username


class CrearUsuarioForm(DatosUsuarioForm):
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def clean(self):
        datos = super().clean()
        password1 = datos.get("password1")
        password2 = datos.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif password1 and password2:
            usuario_provisional = User(
                username=datos.get("username", ""),
                first_name=datos.get("first_name", ""),
                last_name=datos.get("last_name", ""),
                email=datos.get("email", ""),
            )
            try:
                validate_password(password1, user=usuario_provisional)
            except ValidationError as error:
                self.add_error("password1", error)
        return datos


class EditarUsuarioForm(DatosUsuarioForm):
    def __init__(self, *args, usuario, actor, **kwargs):
        self.actor = actor
        super().__init__(*args, usuario=usuario, **kwargs)
        if usuario.pk == actor.pk:
            self.fields["rol"].disabled = True

    def clean_rol(self):
        rol = self.cleaned_data["rol"]
        if (
            self.usuario.pk == self.actor.pk
            and self.is_bound
            and self.data.get("rol") not in (None, rol)
        ):
            raise ValidationError("No puede cambiar su propio rol.")
        return rol

    def clean_estado_activo(self):
        activo = self.cleaned_data["estado_activo"]
        if self.usuario.pk == self.actor.pk and not activo:
            raise ValidationError("No puede desactivar su propia cuenta.")
        return activo


class FiltroUsuariosForm(forms.Form):
    busqueda = forms.CharField(
        label="Buscar usuario", required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Usuario o nombre"}
        ),
    )
    rol = forms.ChoiceField(
        label="Rol", required=False,
        choices=[("", "Todos los roles"), *PerfilUsuario.Rol.choices],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    estado = forms.ChoiceField(
        label="Estado", required=False,
        choices=(("", "Todos"), ("activo", "Activo"), ("inactivo", "Inactivo")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
