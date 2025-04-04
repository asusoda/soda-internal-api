# Points Module

The points module manages the Distinguished Members program's point system, handling point transactions, balances, and leaderboards.

## Structure

```
points/
├── api.py           # Points API endpoints
└── models.py        # Points-related models
```

## Features

### Point Management
- Point awarding and deduction
- Transaction history
- Balance tracking
- Point validation
- Automated point rules

### Leaderboard
- Real-time rankings
- Category-based leaderboards
- Historical rankings
- Achievement tracking
- Progress monitoring

### Reporting
- Point summaries
- Transaction reports
- User statistics
- Activity tracking
- Export capabilities

## API Endpoints

### Point Transactions
- `POST /points/award`
  - Awards points to a user
  - Validates point amount
  - Records transaction
  - Updates leaderboard

- `POST /points/deduct`
  - Deducts points from a user
  - Validates deduction
  - Records transaction
  - Updates balance

- `GET /points/balance`
  - Returns user's point balance
  - Shows transaction history
  - Displays achievements

### Leaderboard
- `GET /points/leaderboard`
  - Returns current rankings
  - Supports filtering
  - Shows progress
  - Includes statistics

- `GET /points/history`
  - Returns transaction history
  - Supports filtering
  - Includes metadata
  - Export capabilities

## Models

### PointTransaction
- Transaction ID
- User ID
- Point amount
- Transaction type
- Timestamp
- Description
- Validator ID

### PointBalance
- User ID
- Current balance
- Total earned
- Total spent
- Last updated
- Achievement level

### PointRule
- Rule ID
- Point amount
- Conditions
- Expiration
- Category
- Description

## Configuration

Required environment variables:
- `POINTS_DATABASE_URL`: Database connection URL
- `POINTS_MIN_AWARD`: Minimum point award
- `POINTS_MAX_AWARD`: Maximum point award
- `POINTS_CATEGORIES`: Point categories

## Usage Example

```python
from modules.points.api import award_points, get_balance

# Award points to a user
await award_points(user_id="123", amount=10, reason="Event participation")

# Get user's point balance
balance = await get_balance(user_id="123")
print(f"Current balance: {balance}")
```

## Error Handling

The module handles various point-related errors:
- Invalid point amounts
- Insufficient balance
- Duplicate transactions
- Validation errors
- Database errors

## Security Considerations

1. **Transaction Security**
   - Point validation
   - User verification
   - Transaction logging
   - Audit trail

2. **Data Integrity**
   - Atomic transactions
   - Balance verification
   - History tracking
   - Backup systems

3. **Access Control**
   - Role-based permissions
   - Transaction limits
   - Approval workflows
   - Audit logging

## Dependencies

- `SQLAlchemy`: Database ORM
- `pandas`: Data analysis
- `python-dateutil`: Date handling
- `pytz`: Timezone support 