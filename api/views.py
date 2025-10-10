from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max, Q
from .models import Meeting, MeetingParticipant
from .serializers import MeetingSerializer
from accounts.permissions import IsChief
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from accounts.models import Department, User, Role
from accounts.serializers import DepartmentSimpleSerializer, UserSimpleSerializer, UserListUpdateSerializer
from .serializers import MeetingRemarkSerializer
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from datetime import datetime
import requests
from django.conf import settings
from rest_framework.permissions import AllowAny
from django.db import connection



User = get_user_model()

class MeetingListCreateView(generics.ListCreateAPIView):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        date_param = self.request.query_params.get('date')
        queryset = Meeting.objects.all()

        if date_param:
            try:
                date = parse_date(date_param)
                if date:
                    queryset = queryset.filter(date=date)
            except ValueError:
                pass

        if user.has_permission("meeting.view_all_meetings"):
            return queryset
        elif user.has_permission("meeting.view_own_meetings"):
            return queryset.filter(created_by=user)
        elif user.has_permission("meeting.view_assigned_meetings"):
            return queryset.filter(participants__user=user, participants__is_active=True)

        return Meeting.objects.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"detail": "Meeting created successfully."}, status=status.HTTP_201_CREATED)

class MeetingUpdateView(generics.RetrieveUpdateAPIView):
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # --- Permission check ---
        # Allow anyone to update only the `status` field. For any other changes, require normal permissions.
        data = request.data or {}
        only_status_update = set(data.keys()) <= {"status"}

        can_update_all = request.user.has_permission("meeting.update_all_meetings")
        can_update_own = request.user.has_permission("meeting.update_own_meetings")

        if not only_status_update:
            if not (can_update_all or (can_update_own and instance.created_by == request.user)):
                return Response(
                    {"detail": "You do not have permission to update this meeting."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # If this request is only updating the meeting status, skip participant handling
        if only_status_update:
            return super().update(request, *args, **kwargs)

        # --- Handle participants ---
        data = request.data
        to_id = data.get("to_id")
        cc_ids = data.get("cc_ids", [])

        if not isinstance(cc_ids, list):
            return Response({"detail": "cc_ids must be a list."}, status=400)

        all_ids = list(set([to_id] + cc_ids)) if to_id else cc_ids
        users = User.objects.filter(id__in=all_ids)
        found_ids = {u.id for u in users}
        missing_ids = set(all_ids) - found_ids

        if missing_ids:
            return Response({"detail": f"User(s) {missing_ids} not found."}, status=400)

        # Permission: only users who can assign participants can modify participants
        if (to_id or cc_ids) and not request.user.has_permission("meeting.assign_participants"):
            return Response({"detail": "You do not have permission to assign participants."}, status=403)

        # Get current active participants for comparison
        current_participants = {
            p.user_id: p for p in MeetingParticipant.objects.filter(meeting=instance, is_active=True)
        }
        current_to_user = next((p.user_id for p in current_participants.values() if p.is_to), None)
        current_cc_users = {p.user_id for p in current_participants.values() if not p.is_to}

        # Determine which participants need to be changed
        new_cc_users = set(cc_ids)
        removed_cc_users = current_cc_users - new_cc_users
        added_cc_users = new_cc_users - current_cc_users

        # Check for time conflict only if to_user has changed
        if to_id and to_id != current_to_user:
            to_user = get_object_or_404(User, id=to_id)
            if not to_user.google_linked:
                return Response({"detail": "Requested assignee has not linked Google Calendar."}, status=400)
            # check conflict: any active 'to' meeting for this user overlapping the updated meeting time
            conflict_exists = Meeting.objects.filter(
                participants__user=to_user,
                date=instance.date,
                participants__is_to=True,
                participants__is_active=True
            ).exclude(id=instance.id).filter(  # Exclude current meeting from conflict check
                # overlap if start < existing_end and end > existing_start
                Q(start_time__lt=instance.end_time) & Q(end_time__gt=instance.start_time)
            ).exists()

            if conflict_exists:
                return Response({"detail": "Requested assignee has a scheduling conflict for this time slot."}, status=400)

        # Get max version and increment for new records only
        max_version = MeetingParticipant.objects.filter(meeting=instance).aggregate(Max("version"))["version__max"] or 0
        new_version = max_version + 1

        # First, handle the participants being replaced
        # These keep their current version but become inactive
        to_deactivate_ids = removed_cc_users
        if to_id != current_to_user and current_to_user:
            to_deactivate_ids.add(current_to_user)

        if to_deactivate_ids:
            MeetingParticipant.objects.filter(
                meeting=instance,
                user_id__in=to_deactivate_ids,
                is_active=True
            ).update(is_active=False)

        # For continuing participants, we'll update their version while keeping them active
        continuing_participant_ids = new_cc_users & current_cc_users
        if to_id and to_id == current_to_user:
            continuing_participant_ids.add(to_id)

        if continuing_participant_ids:
            MeetingParticipant.objects.filter(
                meeting=instance,
                user_id__in=continuing_participant_ids,
                is_active=True
            ).update(version=new_version)

        # Create new records for new participants with the new version
        new_participants = []

        # Add new TO participant if changed
        if to_id and to_id != current_to_user:
            to_user = get_object_or_404(User, id=to_id)
            new_participants.append(MeetingParticipant(
                meeting=instance,
                user=to_user,
                is_to=True,
                version=new_version,  # New participant gets new version
                is_active=True,
                updated_by=request.user
            ))

        # Add new CC participants
        cc_users = [u for u in users if u.id in added_cc_users]
        for user in cc_users:
            new_participants.append(MeetingParticipant(
                meeting=instance,
                user=user,
                is_to=False,
                version=new_version,  # New participants get new version
                is_active=True,
                updated_by=request.user
            ))

        # Bulk create new participants
        if new_participants:
            MeetingParticipant.objects.bulk_create(new_participants)
        # --- Update Google Calendar ---
        if instance.google_event_id:
            print("event_id-------------------",instance.google_event_id)
            owner = instance.created_by
            access_token = owner.get_valid_access_token()
            print("access_token-------------------",access_token)
            if not access_token:
                return Response({"detail": "Google account not linked or token refresh failed."}, status=400)

            attendees = [{"email": p.user.email} for p in instance.participants.filter(is_active=True)]
            attendees.append({"email": "lead.alpha@alphabridgeconsulting.com"})  # always include this

            event_payload = {
                "summary": data.get("title", instance.title),
                "description": data.get("description", instance.description),
                "start": {
                    "dateTime": datetime.combine(instance.date, instance.start_time).isoformat(),
                    "timeZone": "Asia/Karachi",
                },
                "end": {
                    "dateTime": datetime.combine(instance.date, instance.end_time).isoformat(),
                    "timeZone": "Asia/Karachi",
                },
                "attendees": attendees,
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            resp = requests.patch(
                f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{instance.google_event_id}",
                headers=headers,
                json=event_payload,
            )

            # if still unauthorized, try forcing refresh once
            if resp.status_code == 401:
                owner = instance.created_by
                access_token = owner.get_valid_access_token()
                if not access_token:
                    return Response({"detail": "Google token expired and refresh failed."}, status=400)

                headers["Authorization"] = f"Bearer {access_token}"
                resp = requests.patch(
                    f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{instance.google_event_id}",
                    headers=headers,
                    json=event_payload,
                )

            if resp.status_code not in (200, 201):
                return Response(
                    {
                        "detail": "Failed to update Google Calendar event.",
                        "status_code": resp.status_code,
                        "error": resp.json(),
                    },
                    status=400
                )

            google_event = resp.json()
            instance.google_meet_link = google_event.get("hangoutLink")
            instance.save()

        return super().update(request, *args, **kwargs)



class DepartmentAndUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        departments = Department.objects.all().only('id', 'name')
        department_data = DepartmentSimpleSerializer(departments, many=True).data

        all_users = User.objects.filter(google_linked=True).only('id', 'name', 'email')
        all_users_data = UserSimpleSerializer(all_users, many=True).data

        return Response({
            "departments": department_data,
            "all_users": all_users_data
        })
        
        
class UserListCreateUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsChief]

    def get(self, request):
        users = User.objects.exclude(id=request.user.id)
        serializer = UserListUpdateSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserListUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "User updated successfully.", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MeetingRemarksUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):  
        try:
            meeting = Meeting.objects.get(pk=pk)
        except Meeting.DoesNotExist:
            return Response({"detail": "Meeting not found."}, status=status.HTTP_404_NOT_FOUND)

        # If the user already has a remark for this meeting, update it instead of creating a new one
        existing_remark = meeting.remarks.filter(user=request.user).first()
        if existing_remark:
            serializer = MeetingRemarkSerializer(existing_remark, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # No existing remark -> create a new one
        serializer = MeetingRemarkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(meeting=meeting, user=request.user)  
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HealthCheckView(APIView):
    """Lightweight health check: checks DB connectivity and returns service info."""
    permission_classes = [AllowAny]

    def get(self, request):
        # Basic DB check
        db_ok = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            db_ok = True
        except Exception as e:
            db_ok = False

        data = {
            "status": "ok" if db_ok else "error",
            "database": "ok" if db_ok else "error",
            "debug": settings.DEBUG,
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
        status_code = 200 if db_ok else 500
        return Response(data, status=status_code)
