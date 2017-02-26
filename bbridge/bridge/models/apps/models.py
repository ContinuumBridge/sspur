from django.db import models

from django.utils.translation import ugettext, ugettext_lazy as _
from django.conf import settings

from django.utils import timezone

class App(models.Model):

    name = models.CharField(_("name"), max_length = 255)
    description = models.TextField(_("description"), null = True, blank = True)

    class Meta:
        verbose_name = _('app')
        verbose_name_plural = _('apps')
        app_label = 'apps'

