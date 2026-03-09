"""
POI Lifecycle State Machine — single source of truth for status transitions.

States: Draft, Reviewed, Archived, Rejected
Overlay: flagged (boolean, independent of status)
"""

# Valid transitions: from_status → {allowed_targets}
VALID_TRANSITIONS = {
    'Draft':    {'Reviewed', 'Archived', 'Rejected'},
    'Reviewed': {'Draft', 'Archived', 'Rejected'},
    'Archived': {'Draft'},
    'Rejected': set(),  # Terminal — no transitions out
    '':         {'Reviewed', 'Archived', 'Rejected', 'Draft'},  # Unset/empty treated like Draft
}

# ── Field metadata: single source of truth for field rules ──
# Each field has: major (triggers auto-revert), section, required_for_approval
FIELD_META = {
    # IDENTITY
    'Name_EN':        {'major': True,  'section': 'identity', 'required': True},
    'Name_AR':        {'major': True,  'section': 'identity'},
    'Legal_Name':     {'major': True,  'section': 'identity'},
    'Category':       {'major': True,  'section': 'identity', 'required': True},
    'Subcategory':    {'major': True,  'section': 'identity'},
    'Category_Level_3': {'major': True, 'section': 'identity'},
    'Company_Status': {'major': True,  'section': 'identity'},
    # LOCATION
    'Latitude':       {'major': True,  'section': 'location', 'required': True},
    'Longitude':      {'major': True,  'section': 'location', 'required': True},
    'Building_Number': {'major': True, 'section': 'location'},
    'Floor_Number':   {'major': True,  'section': 'location'},
    'Entrance_Location': {'major': True, 'section': 'location'},
    'District_EN':    {'major': True,  'section': 'location'},
    'District_AR':    {'major': True,  'section': 'location'},
    # CONTACT
    'Phone_Number':   {'major': True,  'section': 'contact'},
    'Email':          {'major': True,  'section': 'contact'},
    'Website':        {'major': True,  'section': 'contact'},
    'Social_Media':   {'major': True,  'section': 'contact'},
    'Language':       {'major': True,  'section': 'contact'},
    'Cuisine':        {'major': True,  'section': 'contact'},
    'Payment_Methods': {'major': True, 'section': 'contact'},
    'Commercial_License': {'major': True, 'section': 'contact'},
    'Menu_Barcode_URL': {'major': True, 'section': 'contact'},
    # WORKING HOURS
    'Working_Days':   {'major': True,  'section': 'hours'},
    'Working_Hours':  {'major': True,  'section': 'hours'},
    'Break_Time':     {'major': True,  'section': 'hours'},
    'Holidays':       {'major': True,  'section': 'hours'},
    # MEDIA
    'Exterior_Photo_URL':  {'major': True, 'section': 'media'},
    'Interior_Photo_URL':  {'major': True, 'section': 'media'},
    'Menu_Photo_URL':      {'major': True, 'section': 'media'},
    'Video_URL':           {'major': True, 'section': 'media'},
    'Additional_Photo_URLs': {'major': True, 'section': 'media'},
    'License_Photo_URL':   {'major': True, 'section': 'media'},
    # AMENITIES & SERVICES
    'Amenities':      {'major': True,  'section': 'amenities'},
    'Menu':           {'major': True,  'section': 'amenities'},
    'Drive_Thru':     {'major': True,  'section': 'amenities'},
    'Dine_In':        {'major': True,  'section': 'amenities'},
    'Only_Delivery':  {'major': True,  'section': 'amenities'},
    'Reservation':    {'major': True,  'section': 'amenities'},
    'Require_Ticket': {'major': True,  'section': 'amenities'},
    'Order_from_Car': {'major': True,  'section': 'amenities'},
    'Pickup_Point':   {'major': True,  'section': 'amenities'},
    'WiFi':           {'major': True,  'section': 'amenities'},
    'Music':          {'major': True,  'section': 'amenities'},
    'Valet_Parking':  {'major': True,  'section': 'amenities'},
    'Has_Parking_Lot': {'major': True, 'section': 'amenities'},
    'Wheelchair_Accessible': {'major': True, 'section': 'amenities'},
    'Family_Seating': {'major': True,  'section': 'amenities'},
    'Waiting_Area':   {'major': True,  'section': 'amenities'},
    'Private_Dining': {'major': True,  'section': 'amenities'},
    'Smoking_Area':   {'major': True,  'section': 'amenities'},
    'Children_Area':  {'major': True,  'section': 'amenities'},
    'Shisha':         {'major': True,  'section': 'amenities'},
    'Live_Sports':    {'major': True,  'section': 'amenities'},
    'Is_Landmark':    {'major': True,  'section': 'amenities'},
    'Is_Trending':    {'major': True,  'section': 'amenities'},
    'Large_Groups':   {'major': True,  'section': 'amenities'},
    'Women_Prayer_Room': {'major': True, 'section': 'amenities'},
    'Iftar_Tent':     {'major': True,  'section': 'amenities'},
    'Iftar_Menu':     {'major': True,  'section': 'amenities'},
    'Open_Suhoor':    {'major': True,  'section': 'amenities'},
    'Free_Entry':     {'major': True,  'section': 'amenities'},
    # QA & REVIEW — these are minor (don't trigger revert)
    'Review_Flag':    {'major': False, 'section': 'review'},
    'Review_Notes':   {'major': False, 'section': 'review'},
    'Review_Status':  {'major': False, 'section': 'review'},
    'QA_Score':       {'major': False, 'section': 'review'},
    'Confidence':     {'major': False, 'section': 'review'},
    'Source':         {'major': False, 'section': 'review'},
}

# Derived sets from metadata (backward compatible)
MAJOR_FIELDS = {f for f, meta in FIELD_META.items() if meta.get('major')}
REQUIRED_FOR_APPROVAL = {f for f, meta in FIELD_META.items() if meta.get('required')}


def can_transition(from_status, to_status):
    """Check if a status transition is allowed."""
    from_status = (from_status or '').strip()
    to_status = (to_status or '').strip()
    allowed = VALID_TRANSITIONS.get(from_status, VALID_TRANSITIONS.get('', set()))
    return to_status in allowed


def validate_transition(from_status, to_status):
    """Validate a transition. Returns (ok, error_message)."""
    from_status = (from_status or '').strip()
    to_status = (to_status or '').strip()
    if not to_status:
        return True, None
    if not can_transition(from_status, to_status):
        if from_status == 'Rejected':
            return False, 'Rejected is a terminal state — cannot change status'
        return False, f'Invalid transition: {from_status or "Draft"} → {to_status}'
    return True, None


def get_approval_blockers(poi, validation_errors=None):
    """Return list of reasons why this POI cannot be approved.
    Empty list = can be approved.
    """
    blockers = []
    status = (poi.get('Review_Status') or '').strip()

    # Terminal state check
    if status == 'Rejected':
        blockers.append('POI is rejected (terminal state)')
    if status == 'Archived':
        blockers.append('POI is archived — restore to Draft first')

    # Required fields
    for field in REQUIRED_FOR_APPROVAL:
        val = (poi.get(field) or '').strip()
        if not val or val == 'UNAVAILABLE':
            blockers.append(f'Missing required field: {field}')

    # Coordinate validation
    try:
        lat = float(poi.get('Latitude') or 0)
        lon = float(poi.get('Longitude') or 0)
        if lat == 0 and lon == 0:
            blockers.append('Coordinates are 0,0 (invalid)')
    except (ValueError, TypeError):
        blockers.append('Invalid coordinates')

    # Unresolved flags block approval
    if poi.get('flagged'):
        flag_reason = (poi.get('flag_reason') or poi.get('Review_Flag') or 'unspecified')
        blockers.append(f'Unresolved flag: {flag_reason} — resolve or unflag before approving')

    # BLOCKER-level validation errors
    if validation_errors:
        blocker_count = sum(1 for e in validation_errors if e.get('severity') == 'BLOCKER')
        if blocker_count:
            blockers.append(f'{blocker_count} BLOCKER validation error(s)')

    return blockers


def should_auto_revert(old_status, changed_fields, old_data=None, new_data=None):
    """Check if a field edit should auto-revert Reviewed→Draft.
    Returns True if revert needed.
    """
    if (old_status or '').strip() != 'Reviewed':
        return False
    if not old_data or not new_data:
        return any(f in MAJOR_FIELDS for f in changed_fields)
    # Only revert if the value actually changed
    return any(
        f in MAJOR_FIELDS and str(new_data.get(f, '') or '') != str(old_data.get(f, '') or '')
        for f in changed_fields
    )
