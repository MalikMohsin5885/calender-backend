from datetime import datetime, timedelta
import requests
from rest_framework import serializers
from .models import Meeting, MeetingParticipant
from django.contrib.auth import get_user_model
from django.db.models import Max
import pytz
from dotenv import load_dotenv
import os

load_dotenv(override=True)
# print(f"CLIENT ID => {os.getenv('GOOGLE_OAUTH_CLIENT_ID')}")

User = get_user_model()

# def times_overlap(start1, end1, start2, end2):
#     """Return True if two time ranges overlap."""
#     # return start1 < end2 and start2 < end1
#     return start1 == start2 and end1 == end2

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class MeetingParticipantSerializer(serializers.ModelSerializer):
    user = MemberSerializer()

    class Meta:
        model = MeetingParticipant
        fields = ['user', 'is_to', 'version', 'updated_by']

class MeetingSerializer(serializers.ModelSerializer):
    to_participant = serializers.SerializerMethodField()
    other_participants = serializers.SerializerMethodField()

    created_by = serializers.CharField(source="created_by.name", read_only=True)

    to_id = serializers.IntegerField(write_only=True, required=False)
    cc_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'meeting_type', 'department', 'created_by', 'created_at',
            'to_participant', 'other_participants',
            'remarks', 'jd_link', 'resume_link',
            'to_id', 'cc_ids',
        ]

    def get_to_participant(self, obj):
        to_part = obj.participants.filter(is_to=True, is_active=True).first()
        if to_part:
            return MeetingParticipantSerializer(to_part).data
        return None

    def get_other_participants(self, obj):
        others = obj.participants.filter(is_to=False, is_active=True)
        return MeetingParticipantSerializer(others, many=True).data
    
    # def refresh_google_token(self,user):
    #     """Force refresh the access token using the refresh token."""
    #     data = {
    #         "client_id": os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
    #         "client_secret": os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
    #         "refresh_token": user.google_refresh_token,
    #         "grant_type": "refresh_token",
    #     }
    #     resp = requests.post("https://oauth2.googleapis.com/token", data=data)

    #     if resp.status_code != 200:
    #         raise Exception(f"Google token refresh failed: {resp.text}")

    #     tokens = resp.json()
    #     user.google_access_token = tokens["access_token"]
    #     user.save(update_fields=["google_access_token"])
    #     return user.google_access_token

    def create(self, validated_data):
        request = self.context['request']
        to_id = validated_data.pop('to_id', None)
        cc_ids = validated_data.pop('cc_ids', [])

        validated_data['created_by'] = request.user

        # ✅ Always add created_by's supervisor to CC (if exists and not self)
        if request.user.supervisor and request.user.supervisor.id != request.user.id:
            cc_ids.append(request.user.supervisor.id)

        all_ids = set(filter(None, [to_id] + cc_ids))
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})

        # Auto-assign to_id if not provided
        if not to_id:
            dept_users = User.objects.filter(
                department=validated_data['department'],
                priority__isnull=False,
                role__name="Closer"
            ).exclude(id__in=cc_ids)
            dept_users = dept_users.order_by('priority')

            if not dept_users.exists():
                raise serializers.ValidationError({
                    "detail": "No eligible 'Closer' found in department for auto-assign."
                })

            to_user = dept_users.first()
            to_id = to_user.id

            # ✅ Add to_user's supervisor to CC if exists and not self
            if to_user.supervisor and to_user.supervisor.id != to_user.id:
                cc_ids.append(to_user.supervisor.id)

            all_ids = set(filter(None, [to_id] + cc_ids))
            users = User.objects.filter(id__in=all_ids)
            found_ids = {u.id for u in users}
            missing_ids = all_ids - found_ids
            if missing_ids:
                raise serializers.ValidationError({
                    "detail": f"User(s) {missing_ids} not found after auto-assign."
                })

        # ====== Time conflict check for "to" user ======
        meeting_date = validated_data['date']
        start_time = validated_data['start_time']
        end_time = validated_data['end_time']

        existing_meetings = Meeting.objects.filter(
            participants__user_id=to_id,
            participants__is_to=True,
            participants__is_active=True,
            date=meeting_date
        )



        meeting = Meeting.objects.create(**validated_data)

        max_version = MeetingParticipant.objects.filter(meeting=meeting).aggregate(max=Max('version'))['max'] or 0
        new_version = max_version + 1

        to_user = User.objects.get(id=to_id)
        MeetingParticipant.objects.create(
            meeting=meeting,
            user=to_user,
            is_to=True,
            version=new_version,
            is_active=True,
            updated_by=request.user
        )

        cc_users = [u for u in users if u.id in cc_ids]
        MeetingParticipant.objects.bulk_create([
            MeetingParticipant(
                meeting=meeting,
                user=user,
                is_to=False,
                version=new_version,
                is_active=True,
                updated_by=request.user
            )
            for user in cc_users
        ])

        # Google Calender Integration

        access_token = request.user.google_access_token  
        
        if not access_token:
            raise serializers.ValidationError({"detail": "User is not linked to Google Calendar."})
        print(f"ACCESSS TOKEN 2.0 => {access_token}\n\n")
        # start_datetime = datetime.combine(meeting.date, meeting.start_time)
        # end_datetime = datetime.combine(meeting.date, meeting.end_time)

        # eastern = pytz.timezone("America/New_York")
        # print(f"\n\nSTART TIME => {eastern.localize(start_datetime.isoformat())}\n\n")
        # print(f"\n\nEND TIME => {eastern.localize(end_datetime)}\n\n")

        # start_datetime = eastern.localize(datetime.combine(meeting.date, meeting.start_time))
        # end_datetime = eastern.localize(datetime.combine(meeting.date, meeting.end_time))

        # pst = pytz.timezone("America/Los_Angeles")   # input timezone
        est = pytz.timezone("America/New_York")      # target timezone
        pst = pytz.timezone("Asia/Karachi")   # input timezone

        start_naive = datetime.combine(meeting.date, meeting.start_time)
        end_naive = datetime.combine(meeting.date, meeting.end_time)

        # Step 1: Localize to PST (what the user entered)
        start_est = est.localize(start_naive)
        end_est = est.localize(end_naive)

        # Step 2: Convert to EST
        start_pst = start_est.astimezone(pst)
        end_pst = end_est.astimezone(pst)


        event_payload = {
            "summary": meeting.title,
            # "location": "Google Meet",
            "description": meeting.description or "",
            "start": {
                "dateTime": start_pst.strftime("%Y-%m-%dT%H:%M:%S"),
                # "dateTime": start_est.isoformat(),
                "timeZone": "Asia/Karachi",  # or derive from user/department
            },
            "end": {
                "dateTime": end_pst.strftime("%Y-%m-%dT%H:%M:%S"),
                # "dateTime": end_est.isoformat(),
                "timeZone": "Asia/Karachi",
            },
            "attendees": [{"email": p.user.email} for p in meeting.participants.all()]+[{"email": "lead.alpha@alphabridgeconsulting.com"}],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meeting-{meeting.id}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "attachments" : []
        }
        if meeting.jd_link:
            event_payload["attachments"].append({
                "fileUrl": meeting.jd_link,
                "title": "Job Description",
                # "mimeType": "application/pdf"  # Adjust based on your link type
            })

        # Add resume link as attachment if it exists
        if meeting.resume_link:
            event_payload["attachments"].append({
                "fileUrl": meeting.resume_link,
                "title": "Resume",
                # "mimeType": "application/pdf"  # Adjust based on your link type
            })
        print(f"\n\n{event_payload}\n\n")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1",
            headers=headers,
            json=event_payload,
        )
        print(f"\n\nGOOGLE API RESPONSE => {resp}\n\n")
        print(f"\n\nGOOGLE API RESPONSE HEADERS => {dict(resp.headers)}\n\n")

        if resp.status_code == 401:  # expired/invalid token
            user = request.user

            access_token = self.refresh_google_token(user)
            print(f"\nREFRESHED NEW ACCESS TOKEN => {access_token}\n\n")
            headers["Authorization"] = f"Bearer {access_token}"
            resp = requests.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1",  
                headers=headers,
                json=event_payload,
            )


        if resp.status_code not in (200, 201):
            print("Google API error:", resp.text)
            raise serializers.ValidationError({"detail": "Failed to create Google Calendar event."})

        google_event = resp.json()
        print(f"\n\nFULL GOOGLE EVENT RESPONSE => {google_event}\n\n")
        meeting.google_event_id = google_event["id"]
        meeting.google_meet_link = google_event.get("hangoutLink")  # store the Meet link
        print(f"\n\nMEETING LINK => {meeting.google_meet_link}\n\n ")
        meeting.save()
        return meeting




class MeetingRemarksSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ["remarks"]  # Only remarks field is editable