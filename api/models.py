from django.db import models
from django.conf import settings


from django.db import models
from django.conf import settings

class Meeting(models.Model):
    title = models.CharField(max_length=150)
    description = models.TextField()
    date = models.DateField()  # <-- new field
    start_time = models.TimeField()  # <-- changed
    end_time = models.TimeField()    # <-- changed
    meeting_type = models.CharField(max_length=50)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_meetings'
    )
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        related_name='meetings'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class MeetingParticipant(models.Model):
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meeting_participations'
    )
    is_to = models.BooleanField(default=True)
    version = models.IntegerField()
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_meeting_participants'
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name} → {self.meeting.title} (v{self.version})"



class MeetingRemark(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    remarks = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)