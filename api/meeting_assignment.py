import calendar
from datetime import datetime, date, timedelta
from django.db.models import Q
from django.utils.timezone import now
from accounts.models import User, MeetingEligibility
from .models import Meeting, MeetingParticipant


def assign_to_user(meeting_data):
    """
    Auto-assign 'to' user for a meeting when to_id is not provided.
    meeting_data must include: department, meeting_type, date, start_time, end_time
    """
    department = meeting_data["department"]
    meeting_type = meeting_data["meeting_type"].lower()
    meeting_date = meeting_data["date"]
    start_time = meeting_data["start_time"]
    end_time = meeting_data["end_time"]

    # Step 1: filter users by eligible department
    eligibilities = MeetingEligibility.objects.filter(
        departments__contains=[department.id],
        priority__isnull=False
    )

    if meeting_type == "w2":
        eligibilities = eligibilities.filter(can_take_w2=True)
    elif meeting_type == "contract":
        eligibilities = eligibilities.filter(can_take_contract=True)

    if not eligibilities.exists():
        return None  # no eligible user found

    # Step 2: get highest priority value
    highest_priority = eligibilities.order_by("-priority").first().priority
    top_eligibilities = eligibilities.filter(priority=highest_priority)

    # Step 3: if more than one with same priority → apply formula
    if top_eligibilities.count() > 1:
        # Week start (Monday) and week end (Sunday)
        week_start = meeting_date - timedelta(days=meeting_date.weekday())
        week_end = week_start + timedelta(days=6)

        scored_users = []
        for elig in top_eligibilities:
            user = elig.user
            # count meetings for this user in current week
            meeting_count = Meeting.objects.filter(
                participants__user=user,
                date__gte=week_start,
                date__lte=week_end
            ).count()
            score = meeting_count * elig.priority
            scored_users.append((user, score))

        # pick user with lowest score
        scored_users.sort(key=lambda x: x[1])
        candidate_user = scored_users[0][0]
    else:
        candidate_user = top_eligibilities.first().user

    # Step 4: check time conflict
    has_conflict = Meeting.objects.filter(
        participants__user=candidate_user,
        date=meeting_date,
        participants__is_to=True,
        participants__is_active=True
    ).filter(
        Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
    ).exists()

    if has_conflict:
        remaining = [elig.user for elig in top_eligibilities if elig.user != candidate_user]
        for user in remaining:
            conflict = Meeting.objects.filter(
                participants__user=user,
                date=meeting_date,
                participants__is_to=True,
                participants__is_active=True
            ).filter(
                Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
            ).exists()
            if not conflict:
                return user
        return None
    return candidate_user
