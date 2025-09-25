from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max
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
        can_update_all = request.user.has_permission("meeting.update_all_meetings")
        can_update_own = request.user.has_permission("meeting.update_own_meetings")

        if not (can_update_all or (can_update_own and instance.created_by == request.user)):
            return Response(
                {"detail": "You do not have permission to update this meeting."},
                status=status.HTTP_403_FORBIDDEN
            )

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

        # deactivate old
        MeetingParticipant.objects.filter(meeting=instance, is_active=True).update(is_active=False)

        max_version = MeetingParticipant.objects.filter(meeting=instance).aggregate(Max("version"))["version__max"] or 0
        new_version = max_version + 1

        participants = []

        if to_id:
            to_user = get_object_or_404(User, id=to_id)
            participants.append(MeetingParticipant(
                meeting=instance,
                user=to_user,
                is_to=True,
                version=new_version,
                is_active=True,
                updated_by=request.user
            ))

        cc_users = [u for u in users if u.id in cc_ids]
        for user in cc_users:
            participants.append(MeetingParticipant(
                meeting=instance,
                user=user,
                is_to=False,
                version=new_version,
                is_active=True,
                updated_by=request.user
            ))

        MeetingParticipant.objects.bulk_create(participants)

        # --- Update Google Calendar ---
        if instance.google_event_id:
            access_token = request.user.google_access_token
            if not access_token:
                return Response({"detail": "User not linked to Google Calendar."}, status=400)

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

            if resp.status_code == 401:
                access_token = request.user.get_valid_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                resp = requests.patch(
                    f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{instance.google_event_id}",
                    headers=headers,
                    json=event_payload,
                )

            if resp.status_code not in (200, 201):
                return Response({"detail": "Failed to update Google Calendar event."}, status=400)

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

    def post(self, request, pk):  # ✅ use POST since remarks are new entries
        try:
            meeting = Meeting.objects.get(pk=pk)
        except Meeting.DoesNotExist:
            return Response({"detail": "Meeting not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = MeetingRemarkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(meeting=meeting, user=request.user)  # ✅ bind meeting & user
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
