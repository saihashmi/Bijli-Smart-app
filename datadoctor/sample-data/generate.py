"""Generates the five synthetic sample datasets. Every value is made up by this script (fixed seeds).

They are deliberately messy in known, countable ways so the product can be demonstrated and tested.
Run from datadoctor/:  backend/.venv/bin/python sample-data/generate.py
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from openpyxl import Workbook

OUT = Path(__file__).parent


def sales() -> None:
    """Retail orders: text amounts, ambiguous dates, label variants, exact duplicates, missing amounts."""
    r = random.Random(11)
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Order ID", "Order Date", "Region", "Channel", "Product", "Units", "Unit Price", "Amount", "Paid"])
    regions = ["Punjab", "Sindh", "KPK", "Balochistan", "Islamabad"]
    products = {"Solar Panel": 18500, "Inverter": 12000, "Battery": 7800, "Wiring Kit": 950, "Meter": 3200}
    rows = []
    for i in range(600):
        day = dt.date(2025, 1, 1) + dt.timedelta(days=r.randrange(540))
        product = r.choice(list(products))
        units = r.randint(1, 24)
        amount: object = units * products[product]
        region: object = r.choices(regions, weights=[38, 27, 15, 8, 12])[0]
        date: object = day
        if i % 97 == 0:
            amount = None
        elif i % 41 == 0:
            amount = f"Rs {amount:,}"
        if i % 67 == 0:
            region = str(region).lower()
        if i % 113 == 0:
            region = f" {region}"
        if i % 89 == 0:
            date = "03/04/2025"
        rows.append([f"ORD-{10000 + i}", date, region, r.choices(["Online", "Dealer", "Retail"], weights=[3, 5, 2])[0], product, units, products[product], amount, r.choices(["Yes", "No"], weights=[8, 2])[0]])
    rows += [list(rows[5]), list(rows[50]), list(rows[500])]  # three exact duplicates
    for row in rows:
        ws.append(row)
    wb.save(OUT / "sales_orders.xlsx")


def clinic() -> None:
    """Clinic visits (entirely fictional people): personal-data columns, impossible dates, outliers, blanks."""
    r = random.Random(22)
    wb = Workbook()
    ws = wb.active
    ws.title = "Visits"
    ws.append(["Visit ID", "Visit Date", "Patient Name", "Phone", "Email", "Department", "Age", "Bill Amount", "Insurance"])
    first = ["Ayesha", "Bilal", "Hina", "Usman", "Sana", "Imran", "Nadia", "Kamran", "Zara", "Farhan"]
    last = ["Sample", "Example", "Testcase", "Placeholder", "Demo"]
    depts = ["Cardiology", "Orthopedics", "Pediatrics", "General Medicine", "Dermatology", "ENT"]
    for i in range(450):
        name = f"{r.choice(first)} {r.choice(last)}"
        day = dt.date(2026, 1, 1) + dt.timedelta(days=r.randrange(240))
        age: object = r.randint(1, 90)
        bill: object = round(r.gammavariate(2.0, 2500), 2)
        date: object = day
        if i % 150 == 7:
            bill = 950000.0  # outlier
        if i % 61 == 0:
            age = None
        if i % 73 == 0:
            date = "31/02/2026"
        if i % 53 == 0:
            bill = "N/A"
        ws.append([f"V-{5000 + i}", date, name, f"0300-555{i:04d}", f"person{i}@example.com", r.choice(depts), age, bill, r.choice(["Yes", "No", "yes", "NO", None])])
    wb.save(OUT / "clinic_visits.xlsx")


def hr() -> None:
    """Employees (fictional), CSV with semicolons: numbers as text, repeated IDs, inconsistent capitalisation."""
    r = random.Random(33)
    depts = ["Finance", "Operations", "Sales", "IT", "HR"]
    with open(OUT / "hr_employees.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Employee ID", "Department", "Job Level", "Join Date", "Monthly Salary", "Leave Days", "Status"])
        for i in range(380):
            dept = r.choice(depts)
            if i % 29 == 0:
                dept = dept.upper()
            salary = r.randrange(45000, 320000, 500)
            text = f"{salary:,}" if i % 7 == 0 else str(salary)
            join = dt.date(2015, 1, 1) + dt.timedelta(days=r.randrange(4000))
            emp = f"E{1000 + (i if i % 95 else i - 1)}"  # a few repeated IDs
            w.writerow([emp, dept, r.choice(["L1", "L2", "L3", "L4"]), join.isoformat(), text, r.choice(["", "0", "3", "7", "12", "21"]), r.choice(["Active", "Active", "Active", "On leave", "Resigned"])])


def inventory() -> None:
    """Stock list with a title row above the header, an empty column and a second sheet."""
    r = random.Random(44)
    wb = Workbook()
    ws = wb.active
    ws.title = "Stock"
    ws.append(["Warehouse stock list (synthetic sample)"])
    ws.append([])
    ws.append(["SKU", "Item", "Category", "", "On Hand", "Reorder Level", "Unit Cost", "Last Counted"])
    cats = ["Electrical", "Plumbing", "Tools", "Safety", "Paint"]
    for i in range(320):
        on_hand: object = r.randint(0, 900)
        if i % 47 == 0:
            on_hand = -r.randint(1, 20)  # negative stock: a data problem to notice
        counted = dt.date(2026, 6, 1) + dt.timedelta(days=r.randrange(120))
        ws.append([f"SKU-{20000 + i}", f"Item {i + 1}", r.choice(cats), None, on_hand, r.choice([10, 25, 50, 100]), round(r.uniform(35, 9500), 2), counted])
    notes = wb.create_sheet("Notes")
    notes.append(["Note"])
    notes.append(["Counts are synthetic and for demonstration only."])
    wb.save(OUT / "inventory_stock.xlsx")


def survey() -> None:
    """Survey answers, CSV: categories only (no measures to total), blanks and whitespace."""
    r = random.Random(55)
    with open(OUT / "survey_responses.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Response ID", "Submitted", "City", "Age Group", "Satisfaction", "Would Recommend", "Comment"])
        cities = ["Lahore", "Karachi", "Islamabad", "Peshawar", "Quetta", "Multan"]
        for i in range(500):
            city = r.choice(cities)
            if i % 37 == 0:
                city = city + "  "
            if i % 83 == 0:
                city = ""
            day = dt.date(2026, 3, 1) + dt.timedelta(days=r.randrange(45))
            w.writerow([f"R{i + 1:04d}", day.strftime("%d/%m/%Y"), city, r.choice(["18-24", "25-34", "35-44", "45-54", "55+"]), r.choice(["Very satisfied", "Satisfied", "Neutral", "Dissatisfied", ""]), r.choice(["Yes", "No", "Maybe"]), r.choice(["", "", "Good service", "Too slow", "=1+1 not a formula, just text"])])


if __name__ == "__main__":
    for make in (sales, clinic, hr, inventory, survey):
        make()
        print("wrote", make.__name__)
