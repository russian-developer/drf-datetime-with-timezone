from rest_framework import serializers
import pytz


class DateTimeFieldWithTZ(serializers.DateTimeField):
    def enforce_timezone(self, value):
        if not value.tzinfo:
            value = pytz.UTC.localize(value, is_dst=None)
        return value
