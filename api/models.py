from django.db import models
from django.conf import settings

class Meeting(models.Model):
    MEETING_TYPE_CHOICES = [
        ('w2', 'W2'),
        ('contract', 'Contract'),
    ]
    # Meeting status choices
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]
    
    title = models.CharField(max_length=150)
    description = models.TextField()
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    google_event_id = models.CharField(max_length=255, blank=True, null=True)
    google_meet_link = models.URLField(blank=True, null=True)


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

    jd_link = models.URLField(blank=True, null=True, help_text="Link to job description or job board")
    resume_link = models.URLField(blank=True, null=True, help_text="Link to resume or document")
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
    meeting = models.ForeignKey('Meeting',on_delete=models.CASCADE,related_name='remarks')
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='remarks_added')
    remark = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Remark by {self.user.name} on {self.meeting.title}"
