"""
Lists of constants that can be used in the edX proctoring
"""

from django.conf import settings


DEFAULT_SOFTWARE_SECURE_REVIEW_POLICY = (
    settings.PROCTORING_SETTINGS['DEFAULT_REVIEW_POLICY'] if
    'DEFAULT_REVIEW_POLICY' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'DEFAULT_REVIEW_POLICY', 'Closed Book')
)

REQUIRE_FAILURE_SECOND_REVIEWS = (
    settings.PROCTORING_SETTINGS['REQUIRE_FAILURE_SECOND_REVIEWS'] if
    'REQUIRE_FAILURE_SECOND_REVIEWS' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'REQUIRE_FAILURE_SECOND_REVIEWS', True)
)
