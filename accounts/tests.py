from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import Interest, Profile
from social.models import Follow


class RegistrationTests(TestCase):
    def test_registration_succeeds_with_valid_data(self):
        resp = self.client.post(reverse('accounts:signup'), {
            'username': 'newuser', 'email': 'newuser@example.com',
            'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        self.assertRedirects(resp, reverse('accounts:onboarding_profile'))
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assertTrue(Profile.objects.filter(user__username='newuser').exists())

    def test_duplicate_username_rejected(self):
        self.client.post(reverse('accounts:signup'), {
            'username': 'dupe', 'email': 'a@example.com', 'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        self.client.logout()
        resp = self.client.post(reverse('accounts:signup'), {
            'username': 'dupe', 'email': 'b@example.com', 'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        self.assertEqual(resp.status_code, 200)  # re-renders form with error, no redirect
        self.assertContains(resp, 'already taken')

    def test_invalid_registration_rejected_password_mismatch(self):
        resp = self.client.post(reverse('accounts:signup'), {
            'username': 'mismatch', 'email': 'c@example.com',
            'password1': 'StrongPass123', 'password2': 'DifferentPass456',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.client.session.get('_auth_user_id'))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.client.post(reverse('accounts:signup'), {
            'username': 'loginuser', 'email': 'login@example.com',
            'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        self.client.logout()

    def test_login_succeeds(self):
        resp = self.client.post(reverse('accounts:login'), {'username': 'loginuser', 'password': 'StrongPass123'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_unauthenticated_user_cannot_access_protected_page(self):
        resp = self.client.get(reverse('core:home'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    def test_logout_works(self):
        self.client.login(username='loginuser', password='StrongPass123')
        self.client.post(reverse('accounts:logout'))
        resp = self.client.get(reverse('core:home'))
        self.assertEqual(resp.status_code, 302)


class ProfileTests(TestCase):
    def setUp(self):
        self.client.post(reverse('accounts:signup'), {
            'username': 'profuser', 'email': 'prof@example.com',
            'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })

    def test_profile_auto_created_on_signup(self):
        self.assertTrue(Profile.objects.filter(user__username='profuser').exists())

    def test_profile_editing(self):
        resp = self.client.post(reverse('accounts:profile_edit'), {
            'display_name': 'Prof User', 'username': 'profuser', 'bio': 'A short bio',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        profile = Profile.objects.get(user__username='profuser')
        self.assertEqual(profile.display_name, 'Prof User')
        self.assertEqual(profile.bio, 'A short bio')

    def test_username_uniqueness_enforced_on_edit(self):
        self.client.post(reverse('accounts:signup'))  # noop, ensures a second signup path exists below
        self.client.logout()
        self.client.post(reverse('accounts:signup'), {
            'username': 'otheruser', 'email': 'other@example.com',
            'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        resp = self.client.post(reverse('accounts:profile_edit'), {
            'display_name': 'Other', 'username': 'profuser', 'bio': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already taken')

    def test_default_profile_visibility_is_public(self):
        profile = Profile.objects.get(user__username='profuser')
        self.assertEqual(profile.visibility, 'public')
        self.assertFalse(profile.is_private())

    def test_private_profile_blocks_non_follower(self):
        profile = Profile.objects.get(user__username='profuser')
        profile.visibility = 'private'
        profile.save()
        self.client.logout()
        self.client.post(reverse('accounts:signup'), {
            'username': 'stranger', 'email': 'stranger@example.com',
            'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        resp = self.client.get(reverse('accounts:profile', kwargs={'username': 'profuser'}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'This account is private')

    def test_private_profile_visible_to_approved_follower(self):
        profile = Profile.objects.get(user__username='profuser')
        profile.visibility = 'private'
        profile.save()
        prof_user = profile.user
        self.client.logout()
        self.client.post(reverse('accounts:signup'), {
            'username': 'follower1', 'email': 'follower1@example.com',
            'password1': 'StrongPass123', 'password2': 'StrongPass123',
        })
        follower = self.client.session
        from django.contrib.auth import get_user_model
        User = get_user_model()
        follower_user = User.objects.get(username='follower1')
        Follow.objects.create(follower=follower_user, following=prof_user)
        resp = self.client.get(reverse('accounts:profile', kwargs={'username': 'profuser'}))
        self.assertNotContains(resp, 'This account is private')

    def test_own_private_profile_remains_accessible_to_owner(self):
        profile = Profile.objects.get(user__username='profuser')
        profile.visibility = 'private'
        profile.save()
        resp = self.client.get(reverse('accounts:profile', kwargs={'username': 'profuser'}))
        self.assertNotContains(resp, 'This account is private')


class InterestSeedTests(TestCase):
    def test_seed_interests_command_creates_categories(self):
        from django.core.management import call_command
        call_command('seed_interests')
        self.assertEqual(Interest.objects.count(), 12)
