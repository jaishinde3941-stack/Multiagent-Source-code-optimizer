import PyPDF2

pdf_path = r'e:\SEM 4\CD_Refined\Technical Deliverlables and Documents\Deliverabls\14_Week_Plan.pdf'
output_path = r'e:\SEM 4\CD_Refined\14_week_plan_extracted.txt'

try:
    with open(pdf_path, 'rb') as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        
        with open(output_path, 'w', encoding='utf-8') as output_file:
            output_file.write(f"Total pages: {len(reader.pages)}\n")
            output_file.write("="*80 + "\n\n")
            
            for i, page in enumerate(reader.pages):
                output_file.write(f"\n--- PAGE {i+1} ---\n\n")
                text = page.extract_text()
                output_file.write(text)
                output_file.write("\n\n" + "="*80 + "\n")
        
        print(f"Successfully extracted {len(reader.pages)} pages to {output_path}")
            
except Exception as e:
    print(f"Error: {e}")
