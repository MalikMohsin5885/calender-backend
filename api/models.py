from django.db import models
from django.conf import settings

class Meeting(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=150)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_meetings'
    )

    def __str__(self):
        return self.title


class MeetingMember(models.Model):
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meeting_participations'
    )

    class Meta:
        unique_together = ('meeting', 'user')

    def __str__(self):
        return f"{self.user.name} → {self.meeting.title}"
