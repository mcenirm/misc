from csv import DictReader
from sys import argv, exit, stderr

import dataset
from icecream import ic


def safe(key):
    s = str(key).lower()
    if s.endswith(")"):
        i = s.rfind("(")
        if i >= 0:
            s = s[i + 1 : -1]
    else:
        i1 = s.find("(")
        if i1 >= 0:
            i2 = s.find(")", i1)
            if i2 >= 0:
                s = s[:i1] + s[(i2 + 1) :]
    s = s.replace("/", " or ")
    s = s.replace(".", "")
    s = s.replace(" ", "_")
    if not s.isidentifier():
        raise ValueError(f"bad safe key: {s}")
    return s


ALL_KEYS = [
    "Country/Region",
    "Store Name",
    "Order Date/Book Date",
    "Dell Order Number",
    "Purchase Order Number",
    "Agreement ID",
    "Customer Number",
    "DPID/IRN",
    "Base sku",
    "Service Tag Quantity",
    "Service Tag",
    "Invoice Date(Bill)",
    "Invoice Number",
    "Fixed Delivery Date(FDD) for APJ",
    "Must Arrive by Date(MABD)",
    "Estimated Delivery Date(EDD)",
    "Estimated Ship Date(ESD)",
    "Revised Delivery Date(RDD)",
    "Revised Ship Date(RSD)",
    "Actual Ship Date",
    "Actual Delivery Date",
    "Track Your Order",
    "Status",
    "Sub/Secondary Status",
    "Outbound SCAC Code",
    "Carrier Name",
    "Airway Bill Number",
    "Packing Slip",
    "Billing Customer Name",
    "Bill To Contact",
    "Ship To Customer",
    "Ship To Contact",
    "Ship to Address",
    "Ship to City",
    "Ship to Postal Code",
    "Ship to State",
    "Ship To Country/Region",
    "Customer Ship to Region",
    "Sold To Customer",
    "Sold to name",
    "Sold to Address",
    "No. of Boxes",
    "Order Quantity",
    "Product Description",
    "Product Quantity",
    "Quote Number",
    "Credit Order Number",
    "Credit Note Number",
    "Local Order Type",
    "Part Shortage",
    "Package Details",
    "End User",
    "End User Address",
]


SAFE_KEYS = {_: safe(_) for _ in ALL_KEYS}

KEEP_KEYS = [
    # "Country/Region",
    # "Store Name",
    "Order Date/Book Date",
    "Dell Order Number",
    "Purchase Order Number",
    # "Agreement ID",
    # "Customer Number",
    # "DPID/IRN",
    # "Base sku",
    "Service Tag Quantity",
    "Service Tag",
    "Invoice Date(Bill)",
    "Invoice Number",
    # "Fixed Delivery Date(FDD) for APJ",
    # "Must Arrive by Date(MABD)",
    "Estimated Delivery Date(EDD)",
    "Estimated Ship Date(ESD)",
    "Revised Delivery Date(RDD)",
    "Revised Ship Date(RSD)",
    "Actual Ship Date",
    "Actual Delivery Date",
    "Track Your Order",
    "Status",
    "Sub/Secondary Status",
    # "Outbound SCAC Code",
    # "Carrier Name",
    # "Airway Bill Number",
    # "Packing Slip",
    # "Billing Customer Name",
    # "Bill To Contact",
    # "Ship To Customer",
    "Ship To Contact",
    # "Ship to Address",
    # "Ship to City",
    # "Ship to Postal Code",
    # "Ship to State",
    # "Ship To Country/Region",
    # "Customer Ship to Region",
    # "Sold To Customer",
    # "Sold to name",
    # "Sold to Address",
    "No. of Boxes",
    "Order Quantity",
    "Product Description",
    "Product Quantity",
    # "Quote Number",
    # "Credit Order Number",
    # "Credit Note Number",
    # "Local Order Type",
    "Part Shortage",
    # "Package Details",
    # "End User",
    # "End User Address",
]


if __name__ == "__main__":
    if len(argv) != 2:
        print(f"Usage: {__file__} ORDERS_AS_CSV_FILE", file=stderr)
        exit(2)

    infname = argv[1]
    infile = open(infname)
    with infile:
        reader = DictReader(infile)
        original_rows = list(reader)
    ic(original_rows[0])
    # ponumbers = {_["Purchase Order Number"] for _ in original_rows}

    # ic(original_rows[0].keys())

    db = dataset.connect("sqlite:///:memory:")
    orders = db["order"]
    for orow in original_rows:
        nrow = {k: orow[k] for k in KEEP_KEYS}
        srow = {safe(k): nrow[k] for k in nrow.keys()}
        orders.insert(srow)

    ic(len(orders))
    # ic(orders.columns)
    # ic(str(orders.table.select(orders.table.c.purchase_order_number)))
