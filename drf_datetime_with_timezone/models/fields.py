from django.db import models
from datetime import datetime, timedelta, timezone
import pytz

_offset_field_name = lambda name: "%s_offset" % name
_utc_field_name = lambda name: "%s_utc" % name


class DateTimeFieldWithTZCreator(object):
    def __init__(self, field, parent_field_name=None, hidden_field=False):
        self.hidden_field = hidden_field
        self.field = field
        self.parent_field_name = parent_field_name and parent_field_name or self.field.name
        self.offset_name = _offset_field_name(self.parent_field_name)
        self.utc_name = _utc_field_name(self.parent_field_name)

    def __get__(self, obj, type=None):
        if obj is None:
            raise AttributeError('Can only be accessed via an instance.')

        if self.hidden_field:
            return obj.__dict__[self.field.name]

        dt = obj.__dict__[self.field.name]
        offset = obj.__dict__.get(self.offset_name, None)
        if dt is None:
            return None
        else:
            tz = timezone(timedelta(seconds=offset))
            return dt.replace(tzinfo=tz)

    def __set__(self, obj, value):
        if value is None:
            obj.__dict__[self.offset_name] = None
            obj.__dict__[self.field.name] = None
            obj.__dict__[self.utc_name] = None
            return

        offset_name_called = obj.__dict__.get(f'{self.offset_name}__called', False)
        utc_name_called = obj.__dict__.get(f'{self.utc_name}__called', False)

        if obj.id and not (self.field.name == self.parent_field_name and not any([offset_name_called, utc_name_called])):
            if self.field.name == self.offset_name:
                obj.__dict__[self.offset_name] = value
                obj.__dict__[f'{self.offset_name}__called'] = True
            elif self.field.name == self.utc_name:
                obj.__dict__[self.utc_name] = value.astimezone(pytz.UTC)
                obj.__dict__[f'{self.utc_name}__called'] = True
            else:
                obj.__dict__[self.field.name] = value.replace(tzinfo=None)
        else:
            if self.field.name == self.parent_field_name:
                obj.__dict__[self.offset_name] = value.utcoffset() and value.utcoffset().seconds or 0
                obj.__dict__[self.field.name] = value.replace(tzinfo=None)
                obj.__dict__[self.utc_name] = value.astimezone(pytz.UTC)


class DateTimeFieldWithTZ(models.DateTimeField):
    def contribute_to_class(self, cls, name):
        offset_field_name = _offset_field_name(name)
        utc_field_name = _utc_field_name(name)

        if hasattr(cls, offset_field_name):
            super().contribute_to_class(cls, name)
            return

        offset_field = models.IntegerField(editable=False, null=True, blank=True)
        offset_field.creation_counter = self.creation_counter
        cls.add_to_class(_offset_field_name(name), offset_field)

        utc_field = models.DateTimeField(editable=False, null=True, blank=True, db_index=self.db_index)
        utc_field.creation_counter = self.creation_counter
        cls.add_to_class(utc_field_name, utc_field)

        super().contribute_to_class(cls, name)
        setattr(cls, self.name, DateTimeFieldWithTZCreator(self))
        setattr(cls, offset_field_name, DateTimeFieldWithTZCreator(offset_field, self.name, hidden_field=True))
        setattr(cls, utc_field_name, DateTimeFieldWithTZCreator(utc_field, self.name, hidden_field=True))

    def get_db_prep_save(self, value, connection):
        if isinstance(value, datetime):
            value = value.replace(tzinfo=None)
        return super().get_db_prep_save(value, connection)

    def db_type(self, connection):
        return 'timestamp'
