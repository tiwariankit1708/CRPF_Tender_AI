from agents.criteria_agent import extract_text_from_pdf

def test():
    pdf_path = r"C:\Users\62958\OneDrive\Desktop\CRPF_Tender_AI\storage\tenders\ffa2936a\Price_Break-up_Cloths_Safety.pdf"
    text = extract_text_from_pdf(pdf_path)
    print("EXTRACTED TEXT:")
    print(text)

if __name__ == "__main__":
    test()
