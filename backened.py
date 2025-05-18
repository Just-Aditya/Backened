from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import qrcode

# Load API keys
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize FastAPI
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all domains for testing
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define Request Models
class QueryRequest(BaseModel):
    university_name: str
    query: str

class LeaveRequest(BaseModel):
    university_name: str
    employee_id: str
    leave_type: str

class CertificateRequest(BaseModel):
    university_name: str
    user_id: str
    certificate_type: str

# Define Functions
def check_leave_balance(employee_id, leave_type, university_name):
    return True  # Assume balance exists

def generate_certificate(user_id, certificate_type, university_name):
    folder_path = "certificates"
    os.makedirs(folder_path, exist_ok=True)  # Ensure folder exists
    file_path = os.path.join(folder_path, f"{user_id}_{certificate_type}.pdf")

    # Create a QR code for verification
    qr = qrcode.make(f"Certificate ID: {user_id}-{certificate_type}")
    qr_path = os.path.join(folder_path, f"qr_{user_id}_{certificate_type}.png")
    qr.save(qr_path)

    # Create PDF
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    # Add border
    c.setStrokeColor(colors.gold)
    c.setLineWidth(3)
    c.rect(0.5*inch, 0.5*inch, width - inch, height - inch, stroke=True, fill=False)

    # University Name
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.darkblue)
    c.drawCentredString(width/2, height - 2*inch, university_name.upper())

    # Certificate Title
    title = f"CERTIFICATE OF {certificate_type.upper()}"
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.darkred)
    c.drawCentredString(width/2, height - 3*inch, title)

    # Student Details
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 4*inch, f"This is to certify that Student ID: {user_id}")
    c.drawCentredString(width/2, height - 5*inch, f"has successfully completed the {certificate_type} at {university_name}.")

    # Date
    date_str = datetime.now().strftime("%d %B, %Y")
    c.drawCentredString(width/2, height - 6*inch, f"Awarded on: {date_str}")

    # QR Code
    c.drawImage(qr_path, width - 2*inch, 1*inch, width=1.5*inch, height=1.5*inch)

    # Save PDF
    c.save()

    os.remove(qr_path)  # Remove temp QR image after use
    return f"/download_certificate/{user_id}_{certificate_type}.pdf"

def handle_query(query, university_name):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    url = "https://api.groq.com/openai/v1/chat/completions"
    data = {
        "model": "llama3-70b-8192",
        "messages":  [
            {"role": "system", "content": f"You are an AI assistant for {university_name}.\n\n"
                                              "Here are some important details about {university_name}:\n"
                                              "- If asked about history, provide general university facts (like founding year, key achievements, etc.).\n"
                                              "- If asked about policies, answer strictly based on known university policies.\n"
                                              "-If asked about anything about university and if the genuine answer is available then answer it\n"
                                              "- Backlog exams are held every semester in December and May.\n"
                                              "- Students are allowed a maximum of 10 casual leaves per semester.\n"
                                              "- Certificates can only be issued for academic achievements and must be requested via the student portal.\n"
                                              "- If the answer is unknown, say 'I am not sure but you can check the official university website.'"},
            {"role": "user", "content": query}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "No valid response.")
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Exception occurred: {str(e)}"

@app.get("/download_certificate/{filename}")
def download_certificate(filename: str):
    file_path = os.path.join("certificates", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/pdf', filename=filename)
    raise HTTPException(status_code=404, detail="Certificate not found")

# FastAPI Routes
@app.post("/query")
def query_agent(request: QueryRequest):
    response = handle_query(request.query, request.university_name)
    return {"response": response}

@app.post("/leave")
def leave_request(request: LeaveRequest):
    if check_leave_balance(request.employee_id, request.leave_type, request.university_name):
        return {"status": "approved", "message": f"Your leave is approved at {request.university_name}."}
    else:
        return {"status": "denied", "message": f"Insufficient leave balance at {request.university_name}."}

@app.post("/certificate")
def certificate_request(request: CertificateRequest):
    file_path = generate_certificate(request.user_id, request.certificate_type, request.university_name)
    full_url = f"http://127.0.0.1:8000{file_path}"  # Generate full URL
    return {
        "status": "success",
        "message": f"Certificate generated for {request.university_name}.",
        "file": full_url
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
