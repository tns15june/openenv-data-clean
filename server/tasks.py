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
# Expert task — Financial Transactions
# ---------------------------------------------------------------------------
_VALID_CATEGORIES: Set[str] = {"Payment", "Refund", "Transfer", "Fee", "Deposit", "Withdrawal"}
_VALID_CURRENCIES: Set[str] = {"USD", "EUR", "GBP", "JPY", "CAD"}
_VALID_STATUSES: Set[str] = {"pending", "approved", "rejected", "flagged"}

_EXPERT_DATA: List[Dict[str, Any]] = [
    {"txn_id": "TXN-1001", "account_id": "ACC-201", "counterparty": "Acme Corp", "amount": 1500.00, "currency": "USD", "txn_date": "2025-01-15", "category": "Payment", "description": "Invoice #4521 payment", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1002", "account_id": "ACC-202", "counterparty": "Global Trade Ltd", "amount": -2300.50, "currency": "EUR", "txn_date": "2025-01-16", "category": "Payment", "description": "Quarterly subscription", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1003", "account_id": "ACC-203", "counterparty": "Smith & Jones", "amount": 750.00, "currency": "USD", "txn_date": "2025-01-18", "category": "Refund", "description": "Overcharge correction", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1004", "account_id": "ACC-204", "counterparty": "TechStart Inc", "amount": 4200.00, "currency": "usd", "txn_date": "2025-01-20", "category": "Payment", "description": "Software license renewal", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1005", "account_id": "ACC-205", "counterparty": "DataFlow Systems", "amount": 890.00, "currency": "USD", "txn_date": "01/22/2025", "category": "Payment", "description": "Cloud hosting Jan 2025", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1006", "account_id": "ACC-206", "counterparty": "  Mercury Partners  ", "amount": 3100.00, "currency": "USD", "txn_date": "2025-01-23", "category": "Transfer", "description": "Intercompany transfer Q1", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1007", "account_id": "ACC-207", "counterparty": "Zenith Solutions", "amount": 5600.00, "currency": "GBP", "txn_date": "2025-01-25", "category": "Payment", "description": "Consulting fees Jan", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1008", "account_id": "ACC-208", "counterparty": "Alpha Industries", "amount": 1200.00, "currency": "USD", "txn_date": "2025-01-27", "category": "Pymnt", "description": "Office supplies order", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "", "account_id": "ACC-209", "counterparty": "Beta Services", "amount": 980.00, "currency": "USD", "txn_date": "2025-01-28", "category": "Payment", "description": "Maintenance contract", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1010", "account_id": "ACC-210", "counterparty": "Omega Group", "amount": 15000.00, "currency": "EUR", "txn_date": "2025-01-30", "category": "Payment", "description": "Annual license fee", "status": "approved", "reviewer_id": ""},
    {"txn_id": "TXN-1011", "account_id": "ACC-211", "counterparty": "Delta Corp", "amount": 2450.00, "currency": "USD", "txn_date": "2025-02-01", "category": "Payment", "description": "Marketing materials", "status": "pending", "reviewer_id": ""},
    {"txn_id": "TXN-1012", "account_id": "ACC-212", "counterparty": "Pinnacle Tech", "amount": 670.00, "currency": "JPY", "txn_date": "2025-02-03", "category": "Fee", "description": "Processing fee Q1", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1013", "account_id": "ACC-213", "counterparty": "Summit Holdings", "amount": 99999.99, "currency": "USD", "txn_date": "2025-02-05", "category": "Payment", "description": "Large equipment purchase", "status": "flagged", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1014", "account_id": "ACC-214", "counterparty": "Crest Financial", "amount": 3400.00, "currency": "CAD", "txn_date": "2025-02-07", "category": "Transfer", "description": "Cross-border wire", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1015", "account_id": "ACC-215", "counterparty": "Nova Analytics", "amount": 1850.00, "currency": "USD", "txn_date": "2025-02-10", "category": "Payment", "description": "Data analytics subscription", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1016", "account_id": "ACC-216", "counterparty": "Echo Ventures", "amount": 4700.00, "currency": "Dollars", "txn_date": "2025-02-12", "category": "Payment", "description": "Investment advisory fee", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1017", "account_id": "ACC-217", "counterparty": "Vortex Labs", "amount": 560.00, "currency": "USD", "txn_date": "2025-13-14", "category": "Fee", "description": "Lab testing fee", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1018", "account_id": "ACC-218", "counterparty": "Horizon Media", "amount": 2100.00, "currency": "USD", "txn_date": "2025-02-16", "category": "Payment", "description": "Ad campaign Feb", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1019", "account_id": "ACC-219", "counterparty": "Titan Logistics", "amount": -450.00, "currency": "EUR", "txn_date": "2025-02-18", "category": "Refund", "description": "Shipping overcharge refund", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1020", "account_id": "ACC-220", "counterparty": "Quantum Research", "amount": 8200.00, "currency": "USD", "txn_date": "2025-02-20", "category": "Payment", "description": "R&D collaboration Q1", "status": "rejected", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1021", "account_id": "ACC-221", "counterparty": "Flux Energy", "amount": 1350.00, "currency": "USD", "txn_date": "2025-02-22", "category": "Payment", "description": "Utility bill Feb", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1022", "account_id": "ACC-222", "counterparty": "Apex Consulting", "amount": 6300.00, "currency": "GBP", "txn_date": "2025-02-24", "category": "Payment", "description": "Strategy consulting", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1023", "account_id": "ACC-223", "counterparty": "Nexus Partners", "amount": 2750.00, "currency": "USD", "txn_date": "2025-02-26", "category": "Transfer", "description": "Partner distribution Q1", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1024", "account_id": "ACC-224", "counterparty": "Stellar Dynamics", "amount": 1100.00, "currency": "USD", "txn_date": "2025-02-28", "category": "Payment", "description": "Equipment maintenance", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1025", "account_id": "ACC-225", "counterparty": "Cobalt Security", "amount": 4500.00, "currency": "EUR", "txn_date": "2025-03-02", "category": "Payment", "description": "Security audit Q1", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1026", "account_id": "ACC-226", "counterparty": "Prism Analytics", "amount": 1750.00, "currency": "USD", "txn_date": "2025-03-04", "category": "Payment", "description": "BI dashboard license", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1027", "account_id": "ACC-201", "counterparty": "Acme Corp", "amount": 1500.00, "currency": "USD", "txn_date": "2025-01-15", "category": "Payment", "description": "Invoice #4521 payment", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1028", "account_id": "ACC-228", "counterparty": "Iron  Bridge  Capital", "amount": 9200.00, "currency": "USD", "txn_date": "2025-03-08", "category": "Deposit", "description": "Capital injection", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1029", "account_id": "ACC-229", "counterparty": "Pulse Health", "amount": 3800.00, "currency": "USD", "txn_date": "2025-03-10", "category": "Payment", "description": "Employee wellness program", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1030", "account_id": "ACC-230", "counterparty": "Atlas Freight", "amount": 2200.00, "currency": "US$", "txn_date": "2025-03-12", "category": "Payment", "description": "Freight charges March", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1031", "account_id": "ACC-231", "counterparty": "Vertex Design", "amount": 1600.00, "currency": "USD", "txn_date": "2025-03-14", "category": "Payment", "description": "UI/UX redesign phase 1", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1032", "account_id": "ACC-232", "counterparty": "Nimbus Cloud", "amount": 5100.00, "currency": "USD", "txn_date": "2025-03-16", "category": "Payment", "description": "Cloud infra March", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1033", "account_id": "ACC-233", "counterparty": "Helix Bio", "amount": 7400.00, "currency": "EUR", "txn_date": "2025-03-18", "category": "Payment", "description": "Lab supplies Q1", "status": "flagged", "reviewer_id": ""},
    {"txn_id": "TXN-1034", "account_id": "ACC-234", "counterparty": "Onyx Legal", "amount": 3950.00, "currency": "USD", "txn_date": "2025-03-20", "category": "Fee", "description": "Legal retainer March", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1035", "account_id": "ACC-235", "counterparty": "Zephyr Travel", "amount": 2800.00, "currency": "USD", "txn_date": "2025-03-22", "category": "Payment", "description": "Corporate travel Q1", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1036", "account_id": "ACC-236", "counterparty": "Ruby Software", "amount": 4100.00, "currency": "USD", "txn_date": "2025-03-24", "category": "Payment", "description": "SaaS licenses March", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1037", "account_id": "ACC-237", "counterparty": "Cascade Investments", "amount": 12500.00, "currency": "GBP", "txn_date": "2025-03-26", "category": "Withdrawal", "description": "Dividend distribution", "status": "approved", "reviewer_id": "REV-02"},
    {"txn_id": "TXN-1038", "account_id": "ACC-238", "counterparty": "Lunar Tech", "amount": 890.00, "currency": "USD", "txn_date": "2025-03-28", "category": "Fee", "description": "API usage fee March", "status": "approved", "reviewer_id": "REV-01"},
    {"txn_id": "TXN-1039", "account_id": "ACC-239", "counterparty": "Sapphire HR", "amount": 5500.00, "currency": "USD", "txn_date": "2025-03-30", "category": "Payment", "description": "Recruitment services Q1", "status": "approved", "reviewer_id": "REV-03"},
    {"txn_id": "TXN-1040", "account_id": "ACC-240", "counterparty": "Ember Creative", "amount": 3200.00, "currency": "USD", "txn_date": "2025-04-01", "category": "Payment", "description": "Brand refresh project", "status": "approved", "reviewer_id": "REV-02"},
]

_VALID_REVIEWER_IDS: Set[str] = {"REV-01", "REV-02", "REV-03"}

_EXPERT_ISSUES: List[Issue] = [
    # Negative amounts
    Issue("X1", 1, "amount", "negative_number", "Negative payment amount", {}),
    Issue("X2", 18, "amount", "negative_number", "Negative refund amount (refunds should be positive)", {}),
    # Currency format issues
    Issue("X3", 3, "currency", "inconsistent_format", "Lowercase currency code", {"canonical_set": _VALID_CURRENCIES}),
    Issue("X4", 15, "currency", "inconsistent_format", "Non-standard currency format 'Dollars'", {"canonical_set": _VALID_CURRENCIES}),
    Issue("X5", 29, "currency", "inconsistent_format", "Non-standard currency format 'US$'", {"canonical_set": _VALID_CURRENCIES}),
    # Wrong date formats
    Issue("X6", 4, "txn_date", "wrong_date_format", "Date in MM/DD/YYYY format", {}),
    Issue("X7", 16, "txn_date", "invalid_date", "Invalid date (month 13)", {}),
    # Missing values
    Issue("X8", 8, "txn_id", "missing_value", "Empty transaction ID", {}),
    Issue("X9", 9, "reviewer_id", "cross_column_violation", "Approved status but missing reviewer_id", {}),
    # Inconsistent category
    Issue("X10", 7, "category", "inconsistent_format", "Abbreviated category 'Pymnt' instead of 'Payment'", {"canonical_set": _VALID_CATEGORIES}),
    # Excess whitespace
    Issue("X11", 5, "counterparty", "excess_whitespace", "Leading/trailing whitespace in counterparty", {}),
    Issue("X12", 27, "counterparty", "excess_whitespace", "Double spaces in counterparty name", {}),
    # Duplicate row
    Issue("X13", 26, "txn_id", "duplicate_row", "Exact duplicate of row 0 (TXN-1001)",
          original_row_data={"txn_id": "TXN-1027", "account_id": "ACC-201", "counterparty": "Acme Corp", "amount": 1500.00, "currency": "USD", "txn_date": "2025-01-15", "category": "Payment", "description": "Invoice #4521 payment", "status": "approved", "reviewer_id": "REV-01"}),
    # Cross-column: flagged but no reviewer
    Issue("X14", 32, "reviewer_id", "cross_column_violation", "Flagged status but missing reviewer_id", {}),
    # Outlier amount
    Issue("X15", 12, "amount", "outlier", "Unusually large amount (possible error)", {"low": 0.01, "high": 50000.0}),
]

EXPERT_TASK = TaskDefinition(
    task_id="financial_transactions",
    difficulty="expert",
    description=(
        "You are auditing a financial transactions ledger for compliance review. "
        "The data should have valid transaction IDs, positive amounts, ISO currency codes "
        "(USD, EUR, GBP, JPY, CAD), dates in YYYY-MM-DD format, valid categories "
        "(Payment, Refund, Transfer, Fee, Deposit, Withdrawal), and no duplicate entries. "
        "Approved and flagged transactions must have a reviewer_id. "
        "Fix all data quality issues to pass the audit."
    ),
    columns=["txn_id", "account_id", "counterparty", "amount", "currency", "txn_date", "category", "description", "status", "reviewer_id"],
    data=_EXPERT_DATA,
    issues=_EXPERT_ISSUES,
    max_steps=45,
    column_descriptions={
        "txn_id": "Transaction ID (format: TXN-XXXX, must not be empty)",
        "account_id": "Account ID (format: ACC-XXX)",
        "counterparty": "Counterparty name (no excess whitespace)",
        "amount": "Transaction amount (must be positive)",
        "currency": "ISO currency code (must be: USD, EUR, GBP, JPY, or CAD)",
        "txn_date": "Transaction date (must be valid YYYY-MM-DD)",
        "category": "Transaction category (must be: Payment, Refund, Transfer, Fee, Deposit, or Withdrawal)",
        "description": "Transaction description",
        "status": "Status (pending, approved, rejected, flagged)",
        "reviewer_id": "Reviewer ID (required for approved/flagged transactions)",
    },
)


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------
ALL_TASKS: Dict[str, TaskDefinition] = {
    "customer_contacts": EASY_TASK,
    "sales_records": MEDIUM_TASK,
    "employee_records": HARD_TASK,
    "financial_transactions": EXPERT_TASK,
}


def get_task(task_id: str) -> TaskDefinition:
    """Get a deep copy of a task definition."""
    if task_id not in ALL_TASKS:
        raise ValueError(
            f"Unknown task_id '{task_id}'. Available: {list(ALL_TASKS.keys())}"
        )
    return copy.deepcopy(ALL_TASKS[task_id])
