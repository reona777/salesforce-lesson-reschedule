"""
Salesforce lesson reschedule automation script.
Reads a Google Spreadsheet for pending reschedule requests and applies them to Salesforce.
Rows with an empty status column (column J) are processed; completed rows are skipped.
"""

import argparse
import gspread
from google.oauth2.service_account import Credentials
from simple_salesforce import Salesforce
from datetime import datetime, timedelta
import os
import re

# ========== Configuration ==========
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "YOUR_SPREADSHEET_ID")
SHEET_NAME = os.environ.get("SHEET_NAME", "RescheduleRequests")

SF_USERNAME = os.environ.get("SF_USERNAME")
SF_PASSWORD = os.environ.get("SF_PASSWORD")
SF_TOKEN = os.environ.get("SF_TOKEN")
SF_DOMAIN = os.environ.get("SF_DOMAIN", "your-org.my")

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
# ====================================


def connect_salesforce():
    sf = Salesforce(
        username=SF_USERNAME,
        password=SF_PASSWORD,
        security_token=SF_TOKEN,
        domain=SF_DOMAIN,
    )
    print("Connected to Salesforce.")
    return sf


def connect_spreadsheet():
    creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    print("Connected to Google Spreadsheet.")
    return sheet


def count_subjects(subject_str):
    """Count number of subjects from a delimited string."""
    if not subject_str:
        return 1
    subjects = re.split(r"[・、,\s　]+", subject_str.strip())
    subjects = [s for s in subjects if s]
    return len(subjects)


def parse_datetime(dt_str):
    """Parse a datetime string from the spreadsheet."""
    if not dt_str:
        return None
    formats = [
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None


def find_lesson(sf, teacher_name, student_name, location, start_datetime):
    """
    Search for a Salesforce lesson record by teacher, student, location, and time window.
    Spaces are stripped from names before matching to handle inconsistent formatting.
    """
    search_from = (start_datetime - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    search_to = (start_datetime + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    teacher_key = teacher_name.replace(" ", "").replace("　", "")
    student_key = student_name.replace(" ", "").replace("　", "")

    soql = f"""
        SELECT Id, Name, MANAERP__Start_Date_Time__c, MANAERP__End_Date_Time__c,
               MANAERP__Teacher__c, MANAERP__Subject_Name__c
        FROM MANAERP__Lesson__c
        WHERE MANAERP__Teacher__c LIKE '%{teacher_key}%'
          AND Name LIKE '%{student_key}%'
          AND Name LIKE '%指導枠%'
          AND MANAERP__Location__c = '{location}'
          AND MANAERP__Status__c NOT IN ('Cancelled', 'Completed')
          AND MANAERP__Start_Date_Time__c >= {search_from}
          AND MANAERP__Start_Date_Time__c <= {search_to}
        ORDER BY MANAERP__Start_Date_Time__c ASC
        LIMIT 5
    """
    result = sf.query(soql)
    return result.get("records", [])


def update_lesson(sf, lesson_id, new_start, new_end):
    """Update the start and end time of a Salesforce lesson record."""
    sf.MANAERP__Lesson__c.update(lesson_id, {
        "MANAERP__Start_Date_Time__c": new_start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "MANAERP__End_Date_Time__c": new_end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    })


def main():
    parser = argparse.ArgumentParser(description="Salesforce lesson reschedule automation")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    args = parser.parse_args()
    dry_run = args.dry_run

    if dry_run:
        print("[DRY RUN] No changes will be made.\n")

    sf = connect_salesforce()
    sheet = connect_spreadsheet()

    rows = sheet.get_all_values()
    data_rows = rows[1:]

    # Column indices (0-based)
    # A=0(timestamp), B=1(teacher), C=2(student), D=3(location), E=4(subjects),
    # F=5(reason), G=6(original start), H=7(new start), J=9(status)
    COL_TEACHER = 1
    COL_STUDENT = 2
    COL_LOCATION = 3
    COL_SUBJECT = 4
    COL_BEFORE = 6
    COL_AFTER = 7
    COL_STATUS = 9

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, row in enumerate(data_rows):
        row_num = i + 2

        if len(row) <= COL_STATUS:
            row = row + [""] * (COL_STATUS + 1 - len(row))

        status = row[COL_STATUS].strip()

        if status:
            skip_count += 1
            continue

        teacher = row[COL_TEACHER].strip()
        student = row[COL_STUDENT].strip()
        location = row[COL_LOCATION].strip()
        subject = row[COL_SUBJECT].strip()
        before_str = row[COL_BEFORE].strip()
        after_str = row[COL_AFTER].strip()

        if not teacher or not before_str or not after_str:
            print(f"Row {row_num}: Missing required fields, skipping.")
            skip_count += 1
            continue

        before_dt = parse_datetime(before_str)
        after_dt = parse_datetime(after_str)

        if not before_dt or not after_dt:
            print(f"Row {row_num}: Failed to parse datetime, skipping. (before={before_str}, after={after_str})")
            skip_count += 1
            continue

        num_subjects = count_subjects(subject)
        lesson_duration = timedelta(hours=num_subjects)

        # The spreadsheet stores the test start time.
        # Lesson structure: [tutoring session] → [test]
        # So lesson start = test start - tutoring duration (1 hour per subject)
        new_lesson_start = after_dt - lesson_duration
        new_lesson_end = after_dt

        print(f"\nRow {row_num}: {teacher} / {student} / {subject} ({num_subjects} subject(s))")
        print(f"  Original test start : {before_dt}")
        print(f"  New test start      : {after_dt}")
        print(f"  => New lesson window: {new_lesson_start} - {new_lesson_end}")

        try:
            lessons = find_lesson(sf, teacher, student, location, before_dt)

            if not lessons:
                print(f"  ERROR: No matching Salesforce record found.")
                if not dry_run:
                    sheet.update_cell(row_num, COL_STATUS + 1, "Error: record not found")
                error_count += 1
                continue

            if len(lessons) > 1:
                print(f"  WARNING: {len(lessons)} records matched. Using the first one.")

            lesson = lessons[0]
            lesson_id = lesson["Id"]
            print(f"  Target: {lesson['Name']} ({lesson_id})")

            if dry_run:
                print(f"  [DRY RUN] Would update to: start={new_lesson_start}, end={new_lesson_end}")
            else:
                update_lesson(sf, lesson_id, new_lesson_start, new_lesson_end)
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.update_cell(row_num, COL_STATUS + 1, f"auto-updated {now_str}")
                print(f"  OK: Updated successfully.")
            success_count += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            if not dry_run:
                sheet.update_cell(row_num, COL_STATUS + 1, f"Error: {str(e)[:50]}")
            error_count += 1

    print(f"\n===== Done =====")
    print(f"Success : {success_count}")
    print(f"Skipped : {skip_count}")
    print(f"Errors  : {error_count}")


if __name__ == "__main__":
    main()
