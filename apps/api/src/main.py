from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
import os
from pathlib import Path
from datetime import datetime
import zipfile

from .db import get_db, create_tables
from .models import Lead, AnalysisJob, JobStatus
from .config import settings
from .analyzers.complexity_scorer import ComplexityScorer
from .reports.pdf_generator import PDFReportGenerator

app = FastAPI(title="Depart API", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class LeadCreate(BaseModel):
    email: EmailStr


class JobResponse(BaseModel):
    id: str
    status: str
    complexity_report: Optional[dict] = None
    created_at: str
    completed_at: Optional[str] = None

    class Config:
        from_attributes = True


# Create uploads directory
UPLOADS_DIR = Path("/tmp/depart_uploads")
UPLOADS_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
def startup():
    create_tables()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    email: str = Form(...),
    rate_per_day: int = Form(default=1000),
    db: Session = Depends(get_db),
):
    """
    Upload a zip file of Oracle DDL/PL-SQL and get complexity analysis.
    Email is used to gate access and store results.
    """
    try:
        # Validate file size
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > settings.max_upload_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.max_upload_size} bytes"
            )

        # Get or create lead
        lead = db.query(Lead).filter(Lead.email == email).first()
        if not lead:
            lead = Lead(email=email)
            db.add(lead)
            db.commit()
            db.refresh(lead)

        # Create job record
        job = AnalysisJob(lead_id=lead.id, rate_per_day=rate_per_day, status=JobStatus.PROCESSING)
        db.add(job)
        db.commit()
        db.refresh(job)

        # Save uploaded file
        file_path = UPLOADS_DIR / f"{job.id}.zip"
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Extract and analyze
        try:
            all_content = ""
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.endswith(('.sql', '.pls', '.plsql', '.txt')):
                        try:
                            content = zip_ref.read(file_info).decode('utf-8', errors='ignore')
                            all_content += content + "\n"
                        except Exception:
                            pass

            # Run complexity analysis
            scorer = ComplexityScorer()
            report = scorer.analyze(all_content, rate_per_day)

            # Generate PDF
            pdf_generator = PDFReportGenerator()
            pdf_content = pdf_generator.generate(report)

            # Save PDF
            pdf_path = UPLOADS_DIR / f"{job.id}_report.pdf"
            with open(pdf_path, "wb") as f:
                f.write(pdf_content)

            # Update job with results
            job.complexity_report = {
                "score": report.score,
                "total_lines": report.total_lines,
                "auto_convertible_lines": report.auto_convertible_lines,
                "needs_review_lines": report.needs_review_lines,
                "must_rewrite_lines": report.must_rewrite_lines,
                "construct_counts": report.construct_counts,
                "effort_estimate_days": report.effort_estimate_days,
                "estimated_cost": report.estimated_cost,
                "top_10_constructs": report.top_10_constructs,
            }
            job.pdf_path = str(pdf_path)
            job.status = JobStatus.DONE
            job.completed_at = datetime.utcnow()
            db.commit()

            return {
                "job_id": str(job.id),
                "status": job.status.value,
            }

        except zipfile.BadZipFile:
            job.status = JobStatus.ERROR
            job.error_message = "Invalid zip file"
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid zip file")

    except HTTPException:
        raise
    except Exception as e:
        job.status = JobStatus.ERROR
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job status and report."""
    try:
        job_uuid = uuid.UUID(job_id)
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_uuid).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return {
            "id": str(job.id),
            "status": job.status.value,
            "complexity_report": job.complexity_report,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")


@app.get("/api/v1/report/{job_id}/pdf")
async def get_pdf_report(job_id: str, db: Session = Depends(get_db)):
    """Download PDF report for a completed job."""
    try:
        job_uuid = uuid.UUID(job_id)
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_uuid).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != JobStatus.DONE:
            raise HTTPException(status_code=400, detail="Job not completed")

        if not job.pdf_path or not os.path.exists(job.pdf_path):
            raise HTTPException(status_code=404, detail="PDF report not found")

        return FileResponse(
            job.pdf_path,
            media_type="application/pdf",
            filename=f"depart_analysis_{job_id}.pdf"
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
