import os
import shutil
import pdfplumber
import pandas as pd
import matplotlib.pyplot as plt
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)


# ------------------------
# CLASSIFICATION FUNCTIONS
# ------------------------

def classify_debit(text):
    if not isinstance(text, str):
        return "Uncategorized"
    text = text.lower()
    if "transfer" in text or "nip" in text:
        return "Transfer"
    elif "pos" in text or "purchase" in text:
        return "POS Purchase"
    elif "atm" in text or "withdraw" in text:
        return "Withdrawal"
    elif "levy" in text or "charge" in text:
        return "Charges"
    else:
        return "Uncategorized"


def classify_credit(text):
    if not isinstance(text, str):
        return "Uncategorized"
    text = text.lower()
    if "salary" in text:
        return "Salary"
    elif "transfer" in text or "nip" in text:
        return "Transfer"
    elif "refund" in text:
        return "Refund"
    else:
        return "Uncategorized"


# ------------------------
# HOME PAGE
# ------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ------------------------
# UPLOAD & PROCESS
# ------------------------

@app.post("/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    transactions = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table[1:]:  # skip header
                    if len(row) >= 8:
                        transactions.append(row)

    df = pd.DataFrame(transactions, columns=[
        "trans_date", "value_date", "reference",
        "debit", "credit", "balance",
        "branch", "remarks"
    ])

    # Clean numeric columns
    for col in ["debit", "credit", "balance"]:
        df[col] = df[col].str.replace(",", "", regex=True)
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Convert date
    df["trans_date"] = pd.to_datetime(df["trans_date"], errors="coerce")

    # --------- ANALYTICS ---------

    total_debit = df["debit"].sum()
    total_credit = df["credit"].sum()

    # Debit vs Credit Chart
    plt.figure()
    plt.bar(["Debit", "Credit"], [total_debit, total_credit])
    plt.title("Debit vs Credit")
    plt.savefig("static/debit_vs_credit.png")
    plt.close()

    # Debit grouping
    debit_df = df[df["debit"] > 0].copy()
    debit_df["category"] = debit_df["remarks"].apply(classify_debit)
    debit_group = debit_df.groupby("category")["debit"].sum()

    plt.figure()
    debit_group.plot(kind="bar")
    plt.title("Debit Categories")
    plt.ylabel("Amount")
    plt.tight_layout()
    plt.savefig("static/debit_group.png")
    plt.close()

    # Credit grouping
    credit_df = df[df["credit"] > 0].copy()
    credit_df["category"] = credit_df["remarks"].apply(classify_credit)
    credit_group = credit_df.groupby("category")["credit"].sum()

    plt.figure()
    credit_group.plot(kind="bar")
    plt.title("Credit Categories")
    plt.ylabel("Amount")
    plt.tight_layout()
    plt.savefig("static/credit_group.png")
    plt.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "processed": True
    })
