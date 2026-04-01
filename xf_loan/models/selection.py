# Request States
DRAFT = 'draft'

APPROVING = 'approving'
APPROVED = 'approved'

ACCEPTING = 'accepting'
ACCEPTED = 'accepted'

REJECTED = 'rejected'
DISBURSING = 'disbursing'
DISBURSED = 'disbursed'

REQUEST_STATES = [
    (DRAFT, 'Draft'),

    (APPROVING, 'Approving'),
    (APPROVED, 'Approved'),
    (REJECTED, 'Rejected'),

    (ACCEPTING, 'Accepting'),
    (ACCEPTED, 'Accepted'),

    (DISBURSING, 'Disbursing'),
    (DISBURSED, 'Disbursed'),
]

EMPLOYEE_READONLY_STATES = [
    APPROVING, APPROVED, REJECTED, ACCEPTING, ACCEPTED, DISBURSING, DISBURSED,
]
