
from django import forms
from django.contrib.auth import password_validation, authenticate, login

from .models import User, Manager

class CustomAuthenticationForm(forms.Form):
	email = forms.CharField(
		label="",
		widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Email'})
	)
	password = forms.CharField(
		label="",
		strip=False,
		widget=forms.PasswordInput(attrs={'placeholder': 'Пароль'}),
	)

	error_messages = {
		'invalid_login': "Пожалуйста, введите корректный логин и пароль",
		'inactive': "This account is inactive.",
	}

	def __init__(self, request=None, *args, **kwargs):
		self.request = request
		self.user_cache = None
		super().__init__(*args, **kwargs)

	def clean(self):
		email = self.cleaned_data.get('email')
		password = self.cleaned_data.get('password')

		if email and password:
			if User.objects.filter(email=email, password=password).exists():
				# self.user_cache = authenticate(self.request, email=email, password=password)
				self.user_cache = User.objects.get(email=email, password=password)
				self.confirm_login_allowed(self.user_cache)
			else:
				raise self.get_invalid_login_error()

		return self.cleaned_data

	def confirm_login_allowed(self, user):
		if not user.is_active:
			raise forms.ValidationError(
				self.error_messages['inactive'],
				code='inactive',
			)

	def get_user(self):
		return self.user_cache

	def get_invalid_login_error(self):
		return forms.ValidationError(
			self.error_messages['invalid_login'],
			code='invalid_login',
		)

class CustomUserCreationForm(forms.ModelForm):

	error_messages = {
		'password_mismatch': "The two password fields didn't match.",
	}
	password1 = forms.CharField(
		label="",
		strip=False,
		widget=forms.PasswordInput(attrs={'placeholder': 'Пароль'})
	)
	password2 = forms.CharField(
		label="",
		widget=forms.PasswordInput(attrs={'placeholder': 'Повторите пароль'}),
		strip=False
	)

	class Meta:
		model = User
		fields = ('email',)
		labels = {
			'email': '',
		}
		widgets = {
			'email': forms.TextInput(attrs={'placeholder': 'Email'}),
        }

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	# def clean_insta(self):
		# insta = self.cleaned_data['insta']
		# if not check_insta(insta):
			# raise ValidationError('Такого инстаграма нет')
		# return insta

	def clean_password2(self):
		password1 = self.cleaned_data.get("password1")
		password2 = self.cleaned_data.get("password2")
		if password1 and password2 and password1 != password2:
			raise forms.ValidationError(
				self.error_messages['password_mismatch'],
				code='password_mismatch',
			)
		return password2

	def _post_clean(self):
		super()._post_clean()
		password = self.cleaned_data.get('password2')
		if password:
			try:
				password_validation.validate_password(password, self.instance)
			except forms.ValidationError as error:
				self.add_error('password2', error)

	def save(self, commit=True):
		user = super().save(commit=False)
		user.set_password(self.cleaned_data["password1"])
		if commit:
			user.save()

		email = self.cleaned_data.get('email')
		password = self.cleaned_data.get('password')

		if email is not None and password:
			user_cache = authenticate(self.request, email=email, password=password)
			if user_cache is not None:
				login(self.request, user_cache)

		return user

class ManagerCreationForm(forms.ModelForm):

	class Meta:
		model = Manager
		fields = (
			"whatsapp_instance", "whatsapp_token",
			"telegram_token",
			"vk_group_access_token",
			"facebook_token", "facebook_group_id",
			"default_response", "welcome_message",
		)
		labels = {field: "" for field in fields}
		help_texts = {field: "" for field in fields}
		widgets = {field: forms.TextInput(attrs={'placeholder': field.replace("_", " ").title()}) for field in fields}

# class ManagerCreationForm(forms.Form):
	# instance = forms.CharField(
		# label="",
		# widget=forms.TextInput(attrs={'placeholder': 'instance'}),
	# )
	# token = forms.CharField(
		# label="",
		# widget=forms.TextInput(attrs={'placeholder': 'token'})
	# )
	# default_response = forms.CharField(
		# label="",
		# widget=forms.TextInput(attrs={'placeholder': 'default response'})
	# )
	# welcome_message = forms.CharField(
		# label="",
		# widget=forms.TextInput(attrs={'placeholder': 'default response'})
	# )

	# 'autofocus': True,

	# error_messages = {}

	# def __init__(self, request=None, *args, **kwargs):
		# self.request = request
		# super().__init__(*args, **kwargs)

	# def clean(self):
		# return self.cleaned_data

