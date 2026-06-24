# #this agent will scan the tender pdf and will tell is the details needed by the government such as
# #that the comapmny appplying has need to have a turnover this much m all pf the foloowing 
# #details and we will return it into a json file

# #the things that we will do
# #1) we will take a hugging face model so that the tokens will be unlimited
# #2) we will take everything from the pdf and covert to into a promt
# #3) fromn the prommt we will input it into  the model and fetch the json file


# from langchain_huggingface import ChatHuggingFace,HuggingFaceEndpoint
# from dotenv import load_dotenv
# from langchain_core.prompts import PromptTemplate
# from langchain_core.output_parsers import JsonOutputParser


# load_dotenv()

# llm=HuggingFaceEndpoint(
#     repo_id="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
#     task="task-generator"
# )
# parser=JsonOutputParser()


# model=ChatHuggingFace(llm=llm)

# templete=PromptTemplate(
#     templete='Give me the name, city and state of the company that is  fictional \n {format_instruction}',
#     input_variable=[],
#     partial_variable={'format_instruction':parser.get_format_instructions()}
# )

# promt=templete.format()
# print(promt)

# result=model.invoke(promt)

# final_resul=parser.parse(result.content)
# print(final_resul)  



# # this is to read pdf

# import pdfplumber

# def read_pdf_plumber(file_path):
#     text_content = ""
#     with pdfplumber.open(file_path) as pdf:
#         for page in pdf.pages:
#             # extract_text tries to preserve the visual layout
#             text_content += page.extract_text() + "\n"
            
#     return text_content

# pdf_string = read_pdf_plumber("your_file.pdf")
# print(pdf_string)

import pdfplumber
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_tender_text(pdf_path: str) -> str:
    """
    Reads a PDF using pdfplumber and extracts text into a single string.
    Preserves spatial layout to maintain column and table structures.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    full_text_parts = []

    try:
        # Open the PDF using pdfplumber
        with pdfplumber.open(path) as pdf:
            logger.info(f"Successfully opened {path.name} with {len(pdf.pages)} pages.")
            
            for i, page in enumerate(pdf.pages, 1):
                # layout=True attempts to preserve the visual arrangement of text, 
                # which is crucial for reading tables and multi-column tender documents.
                page_text = page.extract_text(layout=True)
                
                if page_text:
                    full_text_parts.append(f"--- PAGE {i} ---\n{page_text}")
                else:
                    logger.warning(f"No text found on page {i}.")

        full_text = "\n\n".join(full_text_parts)
        logger.info(f"Extraction complete. Total characters: {len(full_text)}")
        return full_text

    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise RuntimeError(f"PDF extraction failed: {e}") from e

# ==========================================
# Example Usage:
# ==========================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # User inputs the PDF
    sample_pdf = "sample_tender.pdf" 
    
    # Store the entire document in a single variable
    tender_document_string = extract_tender_text(C:\Users\62958\OneDrive\Desktop\CRPF_Tender_AI\Online Application Receipt.pdf)
    
    # You can now pass 'tender_document_string' to your Hugging Face model
    print(tender_document_string[:500])