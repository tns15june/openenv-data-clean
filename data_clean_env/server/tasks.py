"""Hardcoded task definitions with datasets and issue registries."""

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class Issue:
    issue_id: str
    row: int
    column: str
    issue_type: str
    description: str
    # Extra params for validation (e.g. canonical_set, low/high range)
    validation_params: Dict[str, Any] = field(default_factory=dict)
    # For duplicate_row issues, store the original row data
    original_row_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDefinition:
    task_id: str
    difficulty: str
    description: str
    columns: List[str]
    data: List[Dict[str, Any]]
    issues: List[Issue]
    max_steps: int
    column_descriptions: Dict[str, str]


# ---------------------------------------------------------------------------
# EASY: Customer Contacts
# ---------------------------------------------------------------------------
_EASY_DATA = [
    {"name": "John Smith", "email": "john.smith@gmail.com", "phone": "555-012-3401", "city": "New York", "signup_date": "2024-01-15"},
    {"name": "Jane Doe", "email": "jane.doe@outlook.com", "phone": "555-012-3402", "city": "Los Angeles", "signup_date": "2024-02-20"},
    {"name": "Bob Johnson", "email": "bob.j@company.com", "phone": "555-012-3403", "city": "Chicago", "signup_date": "2024-03-10"},
    {"name": "Alice Brown", "email": "alice.brown[at]mail.com", "phone": "555-012-3404", "city": "Houston", "signup_date": "2024-04-05"},  # E1: invalid email
    {"name": "Charlie Wilson", "email": "charlie@example.com", "phone": "555-012-3405", "city": "Phoenix", "signup_date": "2024-05-12"},
    {"name": "Diana Davis", "email": "diana@example.com", "phone": "555-012-3406", "city": "", "signup_date": "2024-06-18"},  # E3: empty city
    {"name": "Eve Martinez", "email": "eve@example.com", "phone": "555-012-3407", "city": "Philadelphia", "signup_date": "2024-07-22"},
    {"name": "Frank Taylor", "email": "frank@example.com", "phone": "55A-0B2-34C8", "city": "San Antonio", "signup_date": "2024-08-30"},  # E2: phone has letters
    {"name": "Grace Lee", "email": "grace@example.com", "phone": "555-012-3409", "city": "San Diego", "signup_date": "2024-09-14"},
    {"name": "Hank Moore", "email": "hank@@domain.com", "phone": "555-012-3410", "city": "Dallas", "signup_date": "2024-10-01"},  # E5: double @@
    {"name": "Ivy Clark", "email": "ivy@example.com", "phone": "555-012-3411", "city": "San Jose", "signup_date": "2024-11-18"},
    {"name": "Jack White", "email": "jack@example.com", "phone": "555-012-3412", "city": "Austin", "signup_date": "03/25/2024"},  # E4: wrong date format
    {"name": "Karen Lewis", "email": "karen@example.com", "phone": "555-012-3413", "city": "Jacksonville", "signup_date": "2025-01-03"},
    {"name": "Leo Walker", "email": "leo@example.com", "phone": "555-012-3414", "city": "Columbus", "signup_date": "2025-02-14"},
    {"name": "John Smith", "email": "john.smith@gmail.com", "phone": "555-012-3401", "city": "New York", "signup_date": "2024-01-15"},  # E6: exact duplicate of row 0
]

_EASY_ISSUES = [
    Issue("E1", 3, "email", "invalid_email", "Email uses '[at]' instead of '@'"),
    Issue("E2", 7, "phone", "invalid_phone", "Phone number contains letters"),
    Issue("E3", 5, "city", "missing_value", "City is empty"),
    Issue("E4", 11, "signup_date", "wrong_date_format", "Date is MM/DD/YYYY instead of YYYY-MM-DD"),
    Issue("E5", 9, "email", "invalid_email", "Email has double @@ symbol"),
    Issue(
        "E6", 14, "", "duplicate_row", "Exact duplicate of row 0",
        original_row_data={"name": "John Smith", "email": "john.smith@gmail.com", "phone": "555-012-3401", "city": "New York", "signup_date": "2024-01-15"},
    ),
]

EASY_TASK = TaskDefinition(
    task_id="customer_contacts",
    difficulty="easy",
    description=(
        "You are cleaning a customer contact list for a CRM import. "
        "The data should have valid emails (user@domain.tld), phone numbers "
        "(digits and dashes only, 10+ digits), non-empty cities, dates in "
        "YYYY-MM-DD format, and no duplicate rows. Find and fix all data "
        "quality issues."
    ),
    columns=["name", "email", "phone", "city", "signup_date"],
    data=_EASY_DATA,
    issues=_EASY_ISSUES,
    max_steps=15,
    column_descriptions={
        "name": "Customer full name",
        "email": "Email address (must be user@domain.tld)",
        "phone": "Phone number (digits and dashes, 10+ digits)",
        "city": "City of residence (must not be empty)",
        "signup_date": "Signup date (must be YYYY-MM-DD format)",
    },
)


# ---------------------------------------------------------------------------
# MEDIUM: Sales Records
# ---------------------------------------------------------------------------
_MEDIUM_DATA = [
    {"order_id": "ORD-1001", "customer_name": "Acme Corp", "product": "Widget A", "quantity": 10, "unit_price": 29.99, "order_date": "2024-01-15", "region": "Northeast"},
    {"order_id": "ORD-1002", "customer_name": "Beta Inc", "product": "Widget B", "quantity": 5, "unit_price": 49.99, "order_date": "2024-01-22", "region": "Southeast"},
    {"order_id": "ORD-1003", "customer_name": "Gamma LLC", "product": "Gadget X", "quantity": 20, "unit_price": 15.00, "order_date": "2024-02-03", "region": "Midwest"},
    {"order_id": "ORD-1004", "customer_name": "Delta Co", "product": "Widget A", "quantity": 8, "unit_price": 29.99, "order_date": "2024-02-10", "region": "north-east"},  # M6: inconsistent region
    {"order_id": "ORD-1005", "customer_name": "Epsilon Ltd", "product": "Gadget Y", "quantity": 3, "unit_price": 89.50, "order_date": "Jan 15, 2024", "region": "West"},  # M1: wrong date format
    {"order_id": "ORD-1006", "customer_name": "Zeta Group", "product": "Widget C", "quantity": 12, "unit_price": 35.00, "order_date": "2024-03-01", "region": "Northwest"},
    {"order_id": "", "customer_name": "Eta Partners", "product": "Gadget X", "quantity": 7, "unit_price": 15.00, "order_date": "2024-03-12", "region": "Southeast"},  # M10: missing order_id
    {"order_id": "ORD-1008", "customer_name": "Theta Corp", "product": "Widget B", "quantity": 15, "unit_price": 49.99, "order_date": "2024-03-20", "region": "Midwest"},
    {"order_id": "ORD-1009", "customer_name": "Iota Inc", "product": "Gadget Z", "quantity": -5, "unit_price": 120.00, "order_date": "2024-04-02", "region": "Northeast"},  # M3: negative quantity
    {"order_id": "ORD-1010", "customer_name": "Kappa LLC", "product": "Widget A", "quantity": 25, "unit_price": 29.99, "order_date": "2024-04-15", "region": "West"},
    {"order_id": "ORD-1011", "customer_name": "Lambda Co", "product": "Gadget Y", "quantity": 6, "unit_price": 89.50, "order_date": "2024-04-28", "region": "Southeast"},
    {"order_id": "ORD-1012", "customer_name": "Mu Ltd", "product": "Widget C", "quantity": 30, "unit_price": 35.00, "order_date": "2024-05-05", "region": "Northeast"},
    {"order_id": "ORD-1013", "customer_name": "Nu Group", "product": "Gadget X", "quantity": 4, "unit_price": 15.00, "order_date": "2024/05/18", "region": "Midwest"},  # M2: slash date format
    {"order_id": "ORD-1014", "customer_name": "Xi Partners", "product": "Widget B", "quantity": 9, "unit_price": 49.99, "order_date": "2024-06-01", "region": "Northwest"},
    {"order_id": "ORD-1015", "customer_name": "Omicron Corp", "product": "Gadget Z", "quantity": 2, "unit_price": 29999.99, "order_date": "2024-06-15", "region": "West"},  # M5: price outlier
    {"order_id": "ORD-1016", "customer_name": "Pi Inc", "product": "Widget A", "quantity": 18, "unit_price": 29.99, "order_date": "2024-06-28", "region": "Northeast"},
    {"order_id": "ORD-1017", "customer_name": "Rho LLC", "product": "Gadget Y", "quantity": 11, "unit_price": 89.50, "order_date": "2024-07-10", "region": "Southeast"},
    {"order_id": "ORD-1018", "customer_name": "  Sigma  Co  ", "product": "Widget C", "quantity": 7, "unit_price": 35.00, "order_date": "2024-07-22", "region": "Midwest"},  # M11: excess whitespace
    {"order_id": "ORD-1019", "customer_name": "Tau Group", "product": "Gadget X", "quantity": 14, "unit_price": 15.00, "order_date": "2024-08-05", "region": "Northwest"},
    {"order_id": "ORD-1020", "customer_name": "Upsilon Ltd", "product": "Widget B", "quantity": -12, "unit_price": 49.99, "order_date": "2024-08-18", "region": "Northeast"},  # M4: negative quantity
    {"order_id": "ORD-1021", "customer_name": "Phi Corp", "product": "Gadget Z", "quantity": 8, "unit_price": -15.50, "order_date": "2024-09-01", "region": "West"},  # M12: negative price
    {"order_id": "ORD-1022", "customer_name": "Chi Inc", "product": "Widget A", "quantity": 22, "unit_price": 29.99, "order_date": "2024-09-15", "region": "Southeast"},
    {"order_id": "ORD-1023", "customer_name": "Psi LLC", "product": "Gadget Y", "quantity": 3, "unit_price": 89.50, "order_date": "2024-09-28", "region": "WEST"},  # M7: inconsistent case
    {"order_id": "ORD-1024", "customer_name": "Omega Co", "product": "Widget C", "quantity": 16, "unit_price": 35.00, "order_date": "2024-10-10", "region": "Midwest"},
    {"order_id": "ORD-1025", "customer_name": "Alpha2 Group", "product": "Gadget X", "quantity": 9, "unit_price": 15.00, "order_date": "2024-10-22", "region": "Northwest"},
    {"order_id": "ORD-1011", "customer_name": "Lambda Co", "product": "Gadget Y", "quantity": 6, "unit_price": 89.50, "order_date": "2024-04-28", "region": "Southeast"},  # M9: duplicate of row 10
    {"order_id": "ORD-1027", "customer_name": "Beta2 Inc", "product": "Widget B", "quantity": 13, "unit_price": 49.99, "order_date": "2024-11-15", "region": "Northeast"},
    {"order_id": "ORD-1028", "customer_name": "Gamma2 LLC", "product": "Gadget Z", "quantity": 5, "unit_price": 120.00, "order_date": "2024-11-28", "region": "South East"},  # M8: inconsistent region
    {"order_id": "ORD-1029", "customer_name": "Delta2 Co", "product": "Widget A", "quantity": 20, "unit_price": 29.99, "order_date": "2024-12-10", "region": "West"},
    {"order_id": "ORD-1030", "customer_name": "Epsilon2 Ltd", "product": "Gadget Y", "quantity": 7, "unit_price": 89.50, "order_date": "2024-12-22", "region": "Midwest"},
]

_VALID_REGIONS: Set[str] = {"Northeast", "Southeast", "Midwest", "West", "Northwest"}

_MEDIUM_ISSUES = [
    Issue("M1", 4, "order_date", "wrong_date_format", "Date is 'Jan 15, 2024' instead of YYYY-MM-DD"),
    Issue("M2", 12, "order_date", "wrong_date_format", "Date uses slashes '2024/05/18' instead of YYYY-MM-DD"),
    Issue("M3", 8, "quantity", "negative_number", "Quantity is negative (-5)"),
    Issue("M4", 19, "quantity", "negative_number", "Quantity is negative (-12)"),
    Issue("M5", 14, "unit_price", "outlier", "Price 29999.99 is ~1000x normal range",
          validation_params={"low": 1.0, "high": 500.0}),
    Issue("M6", 3, "region", "inconsistent_format", "Region 'north-east' should match canonical form",
          validation_params={"canonical_set": _VALID_REGIONS}),
    Issue("M7", 22, "region", "inconsistent_format", "Region 'WEST' should match canonical form",
          validation_params={"canonical_set": _VALID_REGIONS}),
    Issue("M8", 27, "region", "inconsistent_format", "Region 'South East' should match canonical form",
          validation_params={"canonical_set": _VALID_REGIONS}),
    Issue(
        "M9", 25, "", "duplicate_row", "Exact duplicate of row 10 (same order_id, customer, product)",
        original_row_data={"order_id": "ORD-1011", "customer_name": "Lambda Co", "product": "Gadget Y", "quantity": 6, "unit_price": 89.50, "order_date": "2024-04-28", "region": "Southeast"},
    ),
    Issue("M10", 6, "order_id", "missing_value", "Order ID is empty"),
    Issue("M11", 17, "customer_name", "excess_whitespace", "Customer name has excess whitespace"),
    Issue("M12", 20, "unit_price", "negative_number", "Price is negative (-15.50)"),
]

MEDIUM_TASK = TaskDefinition(
    task_id="sales_records",
    difficulty="medium",
    description=(
        "You are cleaning sales transaction records for a quarterly report. "
        "Requirements: order_id must be non-empty (format ORD-XXXX), dates must "
        "be YYYY-MM-DD, quantities and prices must be positive numbers, prices "
        "should be in a reasonable range ($1-$500), regions must be one of: "
        "Northeast, Southeast, Midwest, West, Northwest. Names should have no "
        "excess whitespace. No duplicate orders."
    ),
    columns=["order_id", "customer_name", "product", "quantity", "unit_price", "order_date", "region"],
    data=_MEDIUM_DATA,
    issues=_MEDIUM_ISSUES,
    max_steps=25,
    column_descriptions={
        "order_id": "Unique order identifier (format: ORD-XXXX, must not be empty)",
        "customer_name": "Customer/company name (no excess whitespace)",
        "product": "Product name",
        "quantity": "Order quantity (must be positive)",
        "unit_price": "Price per unit in USD (must be positive, reasonable range $1-$500)",
        "order_date": "Order date (must be YYYY-MM-DD)",
        "region": "Sales region (must be: Northeast, Southeast, Midwest, West, or Northwest)",
    },
)


# ---------------------------------------------------------------------------
# HARD: Employee Records
# ---------------------------------------------------------------------------
_HARD_DATA = [
    {"emp_id": "EMP-001", "name": "Sarah Chen", "email": "sarah.chen@company.com", "department": "Engineering", "hire_date": "2020-03-15", "termination_date": "", "salary": 95000, "manager_id": "EMP-010", "performance_score": 8.5},
    {"emp_id": "EMP-002", "name": "James Wilson", "email": "james.w@company.com", "department": "Marketing", "hire_date": "2019-07-01", "termination_date": "", "salary": 78000, "manager_id": "EMP-010", "performance_score": 7.2},
    {"emp_id": "EMP-003", "name": "Maria Garcia", "email": "maria.g@company.com", "department": "Engineering", "hire_date": "2021-01-10", "termination_date": "", "salary": 15000000, "manager_id": "EMP-001", "performance_score": 9.1},  # H5: salary outlier (15M)
    {"emp_id": "EMP-004", "name": "David Kim", "email": "david.kim@company.com", "department": "Sales", "hire_date": "2020-09-20", "termination_date": "", "salary": 72000, "manager_id": "EMP-010", "performance_score": 6.8},
    {"emp_id": "EMP-005", "name": "Emily Patel", "email": "emily.p@company.com", "department": "HR", "hire_date": "2018-04-05", "termination_date": "", "salary": 82000, "manager_id": "EMP-010", "performance_score": 8.0},
    {"emp_id": "EMP-006", "name": "Michael Brown", "email": "michael.b@company.com", "department": "Engineering", "hire_date": "2022-06-15", "termination_date": "", "salary": 88000, "manager_id": "EMP-099", "performance_score": 7.5},  # H1: manager doesn't exist
    {"emp_id": "EMP-007", "name": "  Robert   Williams  ", "email": "robert.w@company.com", "department": "Finance", "hire_date": "2019-11-01", "termination_date": "", "salary": 91000, "manager_id": "EMP-010", "performance_score": 8.3},  # H17: excess whitespace in name
    {"emp_id": "EMP-008", "name": "Lisa Anderson", "email": "lisa.a@company.com", "department": "Sales", "hire_date": "2024-03-15", "termination_date": "2023-01-10", "salary": 68000, "manager_id": "EMP-004", "performance_score": 5.5},  # H3: termination before hire
    {"emp_id": "EMP-009", "name": "Kevin Taylor", "email": "kevin.t@company.com", "department": "Engineering", "hire_date": "2021-08-20", "termination_date": "", "salary": 93000, "manager_id": "EMP-001", "performance_score": 11.5},  # H9: score > 10
    {"emp_id": "EMP-010", "name": "Jennifer Martinez", "email": "jennifer.m@company.com", "department": "Operations", "hire_date": "2017-01-15", "termination_date": "", "salary": 120000, "manager_id": "", "performance_score": 9.0},
    {"emp_id": "EMP-011", "name": "Alice Jones", "email": "alice.jones@", "department": "Marketing", "hire_date": "2022-02-01", "termination_date": "", "salary": 75000, "manager_id": "EMP-002", "performance_score": 7.8},  # H7: incomplete email
    {"emp_id": "EMP-012", "name": "Thomas Lee", "email": "thomas.l@company.com", "department": "Engineering", "hire_date": "2020-10-10", "termination_date": "", "salary": 97000, "manager_id": "EMP-001", "performance_score": 8.7},
    {"emp_id": "EMP-013", "name": "Rachel Green", "email": "rachel.g@company.com", "department": "Engg", "hire_date": "2023-04-15", "termination_date": "", "salary": 85000, "manager_id": "EMP-001", "performance_score": 7.0},  # H11: department abbreviation
    {"emp_id": "EMP-014", "name": "Daniel White", "email": "daniel.w@company.com", "department": "Finance", "hire_date": "2021-05-20", "termination_date": "", "salary": 89000, "manager_id": "EMP-007", "performance_score": 8.1},
    {"emp_id": "EMP-015", "name": "Sophie Clark", "email": "sophie.c@company.com", "department": "HR", "hire_date": "2023-06-01", "termination_date": "2023-05-15", "salary": 71000, "manager_id": "EMP-005", "performance_score": 6.0},  # H4: termination before hire
    {"emp_id": "EMP-016", "name": "Chris Johnson", "email": "chris.j@company.com", "department": "Sales", "hire_date": "2020-12-01", "termination_date": "", "salary": 76000, "manager_id": "EMP-004", "performance_score": 7.3},
    {"emp_id": "EMP-003", "name": "Maria R. Garcia", "email": "maria.g@company.com", "department": "Engineering", "hire_date": "2021-01-10", "termination_date": "", "salary": 15000000, "manager_id": "EMP-001", "performance_score": 9.1},  # H14: semantic dup of row 2 (same emp_id, slightly different name)
    {"emp_id": "EMP-017", "name": "Amanda Davis", "email": "amanda.d@company.com", "department": "Marketing", "hire_date": "2022-09-15", "termination_date": "", "salary": 73000, "manager_id": "EMP-002", "performance_score": 7.6},
    {"emp_id": "EMP-018", "name": "Ryan Thomas", "email": "ryan.t@company.com", "department": "Engineering", "hire_date": "2023-01-20", "termination_date": "", "salary": 90000, "manager_id": "EMP-088", "performance_score": 8.0},  # H2: manager doesn't exist
    {"emp_id": "EMP-019", "name": "Nicole Brown", "email": "nicole.b@company.com", "department": "Finance", "hire_date": "2021-03-01", "termination_date": "", "salary": 87000, "manager_id": "EMP-007", "performance_score": 8.4},
    {"emp_id": "EMP-020", "name": "Jason Miller", "email": "jason.m@company.com", "department": "Operations", "hire_date": "2024-11-15", "termination_date": "2024-06-30", "salary": 79000, "manager_id": "EMP-010", "performance_score": 6.5},  # H16: termination before hire
    {"emp_id": "EMP-021", "name": "Laura Wilson", "email": "laura.w@company.com", "department": "Sales", "hire_date": "2022-11-01", "termination_date": "", "salary": 74000, "manager_id": "EMP-004", "performance_score": 7.1},
    {"emp_id": "EMP-022", "name": "Mark Thompson", "email": "mark.t@company.com", "department": "Engineering", "hire_date": "2019-05-15", "termination_date": "", "salary": 500, "manager_id": "EMP-001", "performance_score": 8.9},  # H6: salary too low (missing zeros)
    {"emp_id": "EMP-023", "name": "Patricia Moore", "email": "patricia.m@company.com", "department": "HR", "hire_date": "2023-08-01", "termination_date": "", "salary": 70000, "manager_id": "EMP-005", "performance_score": 6.2},
    {"emp_id": "EMP-024", "name": "Steven Harris", "email": "steven.h@company.com", "department": "Marketing", "hire_date": "2021-12-10", "termination_date": "", "salary": 77000, "manager_id": "EMP-002", "performance_score": 7.9},
    {"emp_id": "EMP-025", "name": "Angela Martin", "email": "angela.m@company.com", "department": "Finance", "hire_date": "2020-02-20", "termination_date": "", "salary": 92000, "manager_id": "EMP-007", "performance_score": -2.0},  # H10: negative score
    {"emp_id": "EMP-026", "name": "Brian Lewis", "email": "brian.l@company.com", "department": "Operations", "hire_date": "2022-04-01", "termination_date": "", "salary": 81000, "manager_id": "EMP-010", "performance_score": 7.4},
    {"emp_id": "EMP-027", "name": "Michelle Walker", "email": "michelle.w@company.com", "department": "Sales", "hire_date": "2023-10-15", "termination_date": "", "salary": 69000, "manager_id": "EMP-004", "performance_score": 6.7},
    {"emp_id": "EMP-028", "name": "Paul Robinson", "email": "paul.r@company.com", "department": "marketing", "hire_date": "2021-06-20", "termination_date": "", "salary": 76000, "manager_id": "EMP-002", "performance_score": 7.7},  # H12: lowercase department
    {"emp_id": "EMP-029", "name": "Sandra Hall", "email": "sandra.h@company.com", "department": "Engineering", "hire_date": "2020-08-10", "termination_date": "", "salary": 94000, "manager_id": "EMP-001", "performance_score": 8.6},
    {"emp_id": "EMP-030", "name": "Bob Smith", "email": "bob smith@company.com", "department": "Finance", "hire_date": "2022-12-01", "termination_date": "", "salary": 86000, "manager_id": "EMP-007", "performance_score": 7.0},  # H8: space in email
    {"emp_id": "EMP-031", "name": "Diana Scott", "email": "diana.s@company.com", "department": "HR", "hire_date": "2023-03-15", "termination_date": "", "salary": 72000, "manager_id": "EMP-005", "performance_score": 6.9},
    {"emp_id": "EMP-032", "name": "George Adams", "email": "george.a@company.com", "department": "Operations", "hire_date": "2021-09-01", "termination_date": "", "salary": 83000, "manager_id": "EMP-010", "performance_score": 7.8},
    {"emp_id": "EMP-033", "name": "Kevin Taylor", "email": "kevin.t@company.com", "department": "Engineering", "hire_date": "2021-08-20", "termination_date": "", "salary": 93000, "manager_id": "EMP-001", "performance_score": 8.8},  # H15: semantic dup of row 8 (same name+email, diff score)
    {"emp_id": "EMP-034", "name": "Helen King", "email": "helen.k@company.com", "department": "Sales", "hire_date": "2022-07-10", "termination_date": "", "salary": 71000, "manager_id": "EMP-004", "performance_score": 7.2},
    {"emp_id": "EMP-035", "name": "Richard Wright", "email": "richard.w@company.com", "department": "Human Resources", "hire_date": "2020-11-20", "termination_date": "", "salary": 80000, "manager_id": "EMP-005", "performance_score": 8.0},  # H13: non-canonical dept
    {"emp_id": "EMP-036", "name": "Nancy Lopez", "email": "nancy.l@company.com", "department": "Engineering", "hire_date": "2023-05-01", "termination_date": "", "salary": 87000, "manager_id": "EMP-001", "performance_score": 7.3},
    {"emp_id": "EMP-037", "name": "Carl Hill", "email": "carl.h@company.com", "department": "Marketing", "hire_date": "2021-02-15", "termination_date": "", "salary": 74000, "manager_id": "EMP-002", "performance_score": 7.5},
    {"emp_id": "EMP-038", "name": "Betty Young", "email": "betty.y@company.com", "department": "Finance", "hire_date": "2025-13-01", "termination_date": "", "salary": 88000, "manager_id": "EMP-007", "performance_score": 8.2},  # H18: invalid date (month 13)
    {"emp_id": "EMP-039", "name": "Frank Allen", "email": "frank.a@company.com", "department": "Operations", "hire_date": "2022-01-20", "termination_date": "", "salary": 82000, "manager_id": "EMP-010", "performance_score": 7.6},
]

_VALID_DEPARTMENTS: Set[str] = {"Engineering", "Marketing", "Sales", "HR", "Finance", "Operations"}

# Collect all valid emp_ids (excluding known duplicate rows 16 and 33)
_VALID_EMP_IDS: Set[str] = {
    row["emp_id"]
    for i, row in enumerate(_HARD_DATA)
    if i not in (16, 33)  # exclude duplicate rows
}

_HARD_ISSUES = [
    Issue("H1", 5, "manager_id", "referential_integrity", "Manager EMP-099 does not exist in employee list",
          validation_params={"valid_ids": _VALID_EMP_IDS}),
    Issue("H2", 18, "manager_id", "referential_integrity", "Manager EMP-088 does not exist in employee list",
          validation_params={"valid_ids": _VALID_EMP_IDS}),
    Issue("H3", 7, "termination_date", "temporal_inconsistency", "Termination date 2023-01-10 is before hire date 2024-03-15"),
    Issue("H4", 14, "termination_date", "temporal_inconsistency", "Termination date 2023-05-15 is before hire date 2023-06-01"),
    Issue("H5", 2, "salary", "outlier", "Salary 15,000,000 is unreasonably high (expected $20K-$500K)",
          validation_params={"low": 20000, "high": 500000}),
    Issue("H6", 22, "salary", "outlier", "Salary 500 is unreasonably low (expected $20K-$500K)",
          validation_params={"low": 20000, "high": 500000}),
    Issue("H7", 10, "email", "invalid_email", "Email 'alice.jones@' is missing domain"),
    Issue("H8", 30, "email", "invalid_email", "Email 'bob smith@company.com' contains a space"),
    Issue("H9", 8, "performance_score", "score_out_of_range", "Score 11.5 exceeds the 0-10 scale",
          validation_params={"low": 0.0, "high": 10.0}),
    Issue("H10", 25, "performance_score", "score_out_of_range", "Score -2.0 is negative (scale is 0-10)",
          validation_params={"low": 0.0, "high": 10.0}),
    Issue("H11", 12, "department", "inconsistent_format", "Department 'Engg' should match canonical name",
          validation_params={"canonical_set": _VALID_DEPARTMENTS}),
    Issue("H12", 28, "department", "inconsistent_format", "Department 'marketing' has incorrect casing",
          validation_params={"canonical_set": _VALID_DEPARTMENTS}),
    Issue("H13", 35, "department", "inconsistent_format", "Department 'Human Resources' should be canonical 'HR'",
          validation_params={"canonical_set": _VALID_DEPARTMENTS}),
    Issue(
        "H14", 16, "", "duplicate_row", "Semantic duplicate of row 2 (same emp_id EMP-003, slightly different name)",
        original_row_data={"emp_id": "EMP-003", "name": "Maria R. Garcia", "email": "maria.g@company.com", "department": "Engineering", "hire_date": "2021-01-10", "termination_date": "", "salary": 15000000, "manager_id": "EMP-001", "performance_score": 9.1},
    ),
    Issue(
        "H15", 33, "", "duplicate_row", "Semantic duplicate of row 8 (same name and email as Kevin Taylor)",
        original_row_data={"emp_id": "EMP-033", "name": "Kevin Taylor", "email": "kevin.t@company.com", "department": "Engineering", "hire_date": "2021-08-20", "termination_date": "", "salary": 93000, "manager_id": "EMP-001", "performance_score": 8.8},
    ),
    Issue("H16", 20, "termination_date", "temporal_inconsistency",
          "Termination date 2024-06-30 is before hire date 2024-11-15"),
    Issue("H17", 6, "name", "excess_whitespace", "Name '  Robert   Williams  ' has excess whitespace"),
    Issue("H18", 38, "hire_date", "invalid_date", "Date '2025-13-01' has invalid month 13"),
]

HARD_TASK = TaskDefinition(
    task_id="employee_records",
    difficulty="hard",
    description=(
        "You are cleaning employee records for an HR system migration. Requirements: "
        "emp_id must be unique, emails must be valid (user@domain.tld, no spaces), "
        "departments must be one of: Engineering, Marketing, Sales, HR, Finance, Operations. "
        "Dates must be valid YYYY-MM-DD. Termination dates must be after hire dates. "
        "Salaries must be in range $20,000-$500,000. Performance scores must be 0.0-10.0. "
        "Manager IDs must reference existing employees. Names must have no excess whitespace. "
        "Remove duplicate employee entries."
    ),
    columns=["emp_id", "name", "email", "department", "hire_date", "termination_date", "salary", "manager_id", "performance_score"],
    data=_HARD_DATA,
    issues=_HARD_ISSUES,
    max_steps=35,
    column_descriptions={
        "emp_id": "Unique employee ID (format: EMP-XXX)",
        "name": "Full name (no excess whitespace)",
        "email": "Email (valid user@domain.tld, no spaces)",
        "department": "Department (must be: Engineering, Marketing, Sales, HR, Finance, or Operations)",
        "hire_date": "Hire date (valid YYYY-MM-DD)",
        "termination_date": "Termination date (empty if active, must be after hire_date if set)",
        "salary": "Annual salary USD (range: $20,000-$500,000)",
        "manager_id": "Manager's emp_id (must reference existing employee, empty for top-level)",
        "performance_score": "Performance score (0.0 to 10.0)",
    },
)


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------
ALL_TASKS: Dict[str, TaskDefinition] = {
    "customer_contacts": EASY_TASK,
    "sales_records": MEDIUM_TASK,
    "employee_records": HARD_TASK,
}


def get_task(task_id: str) -> TaskDefinition:
    """Get a deep copy of a task definition."""
    if task_id not in ALL_TASKS:
        raise ValueError(
            f"Unknown task_id '{task_id}'. Available: {list(ALL_TASKS.keys())}"
        )
    return copy.deepcopy(ALL_TASKS[task_id])
