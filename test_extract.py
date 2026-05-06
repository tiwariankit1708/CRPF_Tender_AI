import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

from agents.criteria_agent import extract_criteria

def test():
    pdf_path = r"C:\Users\62958\OneDrive\Desktop\CRPF_Tender_AI\storage\tenders\ffa2936a\Price_Break-up_Cloths_Safety.pdf"
    if os.path.exists(pdf_path):
        print(f"File exists: {pdf_path}")
        result = extract_criteria(pdf_path)
        print("Result:", json.dumps(result, indent=2))
    else:
        print("File not found")

if __name__ == "__main__":
    test()
