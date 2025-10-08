from datetime import datetime, timedelta
import requests
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Max
from django.db import transaction
import pytz
from dotenv import load_dotenv

from .models import Meeting, MeetingParticipant, MeetingRemark
from .meeting_assignment import assign_to_user  # <-- our util

load_dotenv(override=True)

User = get_user_model()


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

class MeetingParticipantSerializer(serializers.ModelSerializer):
    user = MemberSerializer()

    class Meta:
        model = MeetingParticipant
        fields = ['user', 'is_to', 'version', 'updated_by']
        
class MeetingRemarkSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = MeetingRemark
        fields = ["id", "meeting", "user", "remark", "created_at"]
        read_only_fields = ["id", "meeting", "user", "created_at"]

class MeetingSerializer(serializers.ModelSerializer):
    # Accept raw meeting_type from frontend (e.g. 'C2C', 'W2') and convert in validate()
    meeting_type = serializers.CharField()
    to_participant = serializers.SerializerMethodField()
    other_participants = serializers.SerializerMethodField()

    created_by = serializers.CharField(source="created_by.name", read_only=True)

    to_id = serializers.IntegerField(write_only=True, required=False)
    cc_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    
    
    remarks = MeetingRemarkSerializer(many=True, read_only=True)  # ✅ nested remarks

    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'description', 'date', 'start_time', 'end_time',
            'meeting_type', 'department', 'created_by', 'created_at', 'status',
            'to_participant', 'other_participants',
            'remarks', 'jd_link', 'resume_link',
            'to_id', 'cc_ids',
        ]
    def validate_remarks(self, value):
        # Normalize empty string to empty list
        if value in ["", None]:
            return []
        return value
    
    def validate(self, data):
        """
        Validate that end_time is after start_time and convert meeting_type
        """
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time.'
                })
        
        # Convert meeting_type from frontend format to enum format
        meeting_type = data.get('meeting_type')
        if meeting_type:
            meeting_type_upper = meeting_type.upper()
            if meeting_type_upper == 'W2':
                data['meeting_type'] = 'w2'
            elif meeting_type_upper in ['C2C', '10.99']:
                data['meeting_type'] = 'contract'
            else:
                raise serializers.ValidationError({
                    'meeting_type': 'Invalid meeting type. Allowed values: W2, C2C, 10.99'
                })

        # Normalize status input (accept various casings)
        status_val = data.get('status')
        if status_val:
            status_lower = status_val.lower()
            allowed = {c[0] for c in Meeting.STATUS_CHOICES}
            if status_lower not in allowed:
                raise serializers.ValidationError({
                    'status': f'Invalid status. Allowed: {sorted(list(allowed))}'
                })
            data['status'] = status_lower
        
        return data
    
    def get_to_participant(self, obj):
        to_part = obj.participants.filter(is_to=True, is_active=True).first()
        if to_part:
            return MeetingParticipantSerializer(to_part).data
        return None

    def get_other_participants(self, obj):
        others = obj.participants.filter(is_to=False, is_active=True)
        return MeetingParticipantSerializer(others, many=True).data


    def create(self, validated_data):
        request = self.context['request']
        to_id = validated_data.pop('to_id', None)
        cc_ids = validated_data.pop('cc_ids', [])

        # Permission: only users who can assign participants can provide to_id/cc_ids
        if (to_id) and not request.user.has_permission("meeting.assign_participants"):
            raise serializers.ValidationError({"detail": "You do not have permission to assign participants."})

        validated_data['created_by'] = request.user

        # Always add created_by's supervisor to CC (if exists and not self)
        if request.user.supervisor and request.user.supervisor.id != request.user.id:
            cc_ids.append(request.user.supervisor.id)

        all_ids = set(filter(None, [to_id] + cc_ids))
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})
        
        # Auto-assign "to" user if not provided
        if not to_id:
            to_user = assign_to_user(validated_data)
            if not to_user:
                raise serializers.ValidationError({
                    "detail": "No eligible user found for Auto assignment."
                })
            to_id = to_user.id

            # Add to_user's supervisor to CC if exists
            if to_user.supervisor and to_user.supervisor.id != to_user.id:
                cc_ids.append(to_user.supervisor.id)

        # # ====== Time conflict check for "to" user ======
        # meeting_date = validated_data['date']
        # start_time = validated_data['start_time']
        # end_time = validated_data['end_time']

        # existing_meetings = Meeting.objects.filter(
        #     participants__user_id=to_id,
        #     participants__is_to=True,
        #     participants__is_active=True,
        #     date=meeting_date
        # )
        
        # Validate users exist
        all_ids = set(filter(None, [to_id] + cc_ids))
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = all_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError({"detail": f"User(s) {missing_ids} not found."})



        # ===== Create Meeting =====
        # Perform DB writes only if Google Calendar event creation succeeds
        with transaction.atomic():
            meeting = Meeting.objects.create(**validated_data)

            max_version = MeetingParticipant.objects.filter(meeting=meeting).aggregate(max=Max('version'))['max'] or 0
            new_version = max_version + 1

            to_user = User.objects.get(id=to_id)
            # ensure the assigned user has linked Google account
            if not to_user.google_linked:
                raise serializers.ValidationError({"detail": "Selected assignee does not have Google Calendar linked."})
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
                "fileAccessLevel": "anyone"
                # "mimeType": "application/pdf"  # Adjust based on your link type
            })

        # Add resume link as attachment if it exists
        if meeting.resume_link:
            event_payload["attachments"].append({
                "fileUrl": meeting.resume_link,
                "title": "Resume",
                "fileAccessLevel": "anyone"
                # "mimeType": "application/pdf"  # Adjust based on your link type
            })
        print(f"\n\n{event_payload}\n\n")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1&supportsAttachments=true",
            headers=headers,
            json=event_payload,
        )
        print(f"\n\nGOOGLE API RESPONSE => {resp}\n\n")
        print(f"\n\nGOOGLE API RESPONSE HEADERS => {dict(resp.headers)}\n\n")

        if resp.status_code == 401:  # expired/invalid token
            user = request.user

            access_token = user.get_valid_access_token()
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



class MeetingRemarkSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = MeetingRemark
        fields = ["id", "meeting", "user", "remark", "created_at"]
        read_only_fields = ["id", "meeting", "user", "created_at"]
