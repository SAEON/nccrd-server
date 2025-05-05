from typing import List, Optional,Union
from fastapi import APIRouter, Depends, HTTPException,UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from nccrd.api.models import SubmissionModel,SubmissionCreate,SubmissionUpdate,SubmissionResponse,MitigationResponse,AdaptationResponse
from uuid import UUID
from nccrd.db import get_db
from nccrd.db.models import Submission,Adaptaion,Mitigation
from openpyxl import load_workbook
from io import BytesIO
from datetime import datetime
import traceback

router = APIRouter()


@router.get(
    '/all_submissions',
    response_model=Union[SubmissionModel, List[SubmissionModel]],
    summary='List all submissions or a specific submissions by its ID'
)
async def get_submissions(
        submission_id: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Return all submissions. Optionally, if a `submission_id` query parameter is provided,
    filter the results to that specific submission.

    Example:
      GET /all_submissions?submission_id=123
    """
    if submission_id:
        # Assuming submission_id corresponds to the string field, or you may need to cast if it's not a string.
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        return [submission]
    else:
        submissions = db.query(Submission).all()
        print(submissions)
        return submissions


@router.post("/create_submission")
def create_submission(submission: SubmissionCreate, db: Session = Depends(get_db)):
    # Create a new Submission instance.
    # Notice that you do not need to provide an id;
    # the UUID is auto-generated per your model default.
    db_submission = Submission(
        title=submission.title,
        intervention_measurement=submission.intervention_measurement,
        description=submission.description,
        implementation_status=submission.implementation_status,
        implementation_organization=submission.implementation_organization,
        implementation_partners_other=submission.implementation_partners_other,
        start_date=submission.start_date,
        end_date=submission.end_date,
        link=submission.link,
        funding_organization=submission.funding_organization,
        funding_type=submission.funding_type,
        funding_amount=submission.funding_amount,
        estimated_budget_cost=submission.estimated_budget_cost,
        geo_location=submission.geo_location,
        project_manager_name=submission.project_manager_name,
        project_manager_organization=submission.project_manager_organization,
        project_manager_position=submission.project_manager_position,
        project_manager_email=submission.project_manager_email,
        project_manager_phone=submission.project_manager_phone,
        project_manager_mobile=submission.project_manager_mobile,
        submission_status=submission.submission_status,
        submission_comments=submission.submission_comments,
        issubmitted=submission.issubmitted,
        research=submission.research,
        createdby=submission.createdby,
        createdate=submission.createdate,
        updatedate=submission.updatedate,
        updatedby=submission.updatedby,
        deletedby=submission.deletedby,
        deletedate=submission.deletedate,
        deleted=submission.deleted,
    )
    try:
        db.add(db_submission)
        db.commit()
        db.refresh(db_submission)  # Loads the generated UUID and _id values
        return db_submission
    except Exception as e:
        db.rollback()
        # Log the full traceback for deeper debugging:
        error_details = traceback.format_exc()
        print("Error creating submission:", error_details)
        raise HTTPException(
            status_code=400,
            detail=f"Submission creation failed. Error details: {str(e)}"
        )

# Endpoint to get a list of all submissions.
@router.get("/fetch_all", response_model=List[SubmissionModel])
def read_submissions(db: Session = Depends(get_db)):
    submissions = db.query(Submission).all()
    return submissions

# Endpoint to get a single submission by its UUID.
@router.get("/fetch/{submission_uuid}", response_model=SubmissionModel)
def read_submission(submission_uuid: UUID, db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_uuid).first()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission

@router.patch("/update/{submission_uuid}")
def update_submission(
    submission_uuid: UUID, update_data: SubmissionUpdate, db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(Submission.id == submission_uuid).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    update_dict = update_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(submission, key, value)

    db.commit()
    db.refresh(submission)
    return submission


@router.delete("/delete/{submission_uuid}")
def soft_delete_submission(submission_uuid: UUID, db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_uuid).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Instead of deleting the record, mark it as deleted
    submission.deleted = True
    submission.deletedate = datetime.utcnow()
    db.commit()
    db.refresh(submission)
    return {"detail": "Submission marked as deleted."}


#######New Submission

@router.post("/new_submission", summary="Create a new submission and related records.")
def create_submission(submission: SubmissionCreate, db: Session = Depends(get_db)):
    # Create the Submission record.
    db_submission = Submission(
        title=submission.title,
        intervention_measurement=submission.intervention_measurement,
        description=submission.description,
        implementation_status=submission.implementation_status,
        implementation_organization=submission.implementation_organization,
        implementation_partners_other=submission.implementation_partners_other,
        start_date=submission.start_date,
        end_date=submission.end_date,
        link=submission.link,
        funding_organization=submission.funding_organization,
        funding_type=submission.funding_type,
        funding_amount=submission.funding_amount,
        estimated_budget_cost=submission.estimated_budget_cost,
        geo_location=submission.geo_location,
        project_manager_name=submission.project_manager_name,
        project_manager_organization=submission.project_manager_organization,
        project_manager_position=submission.project_manager_position,
        project_manager_email=submission.project_manager_email,
        project_manager_phone=submission.project_manager_phone,
        project_manager_mobile=submission.project_manager_mobile,
        submission_status=submission.submission_status,
        submission_comments=submission.submission_comments,
        issubmitted=submission.issubmitted,
        research=submission.research,
        createdby=submission.createdby,
        createdate=submission.createdate,
        updatedate=submission.updatedate,
        updatedby=submission.updatedby,
        deletedby=submission.deletedby,
        deletedate=submission.deletedate,
        deleted=submission.deleted,
    )
    db.add(db_submission)
    db.commit()
    db.refresh(db_submission)  # Now we have a valid submission UUID

    im_value = submission.intervention_measurement.strip().lower()

    # Create Mitigation record if needed.
    if im_value in ("mitigation", "cross cutting"):
        if not submission.mitigation_data:
            raise HTTPException(
                status_code=400,
                detail="Mitigation data must be provided for 'Mitigation' or 'Cross Cutting' interventions."
            )
        mitigation_record = Mitigation(
            submission_id=db_submission.id,
            sector=submission.mitigation_data.sector,
            subsector=submission.mitigation_data.subsector,
            secondary=submission.mitigation_data.secondary,
            project_type=submission.mitigation_data.project_type,
            project_subtype=submission.mitigation_data.project_subtype,
            mitigation_program=submission.mitigation_data.mitigation_program,
            national_policy=submission.mitigation_data.national_policy,
            provincial_municipal=submission.mitigation_data.provincial_municipal,
            primary_intended_outcome=submission.mitigation_data.primary_intended_outcome,
            progress_calculator=submission.mitigation_data.progress_calculator,
            enviromental_co_benefit=submission.mitigation_data.enviromental_co_benefit,
            enviromental_co_benefit_description=submission.mitigation_data.enviromental_co_benefit_description,
            social_co_benefit=submission.mitigation_data.social_co_benefit,
            social_co_benefit_description=submission.mitigation_data.social_co_benefit_description,
            economic_co_benefit=submission.mitigation_data.economic_co_benefit,
            economic_co_benefit_description=submission.mitigation_data.economic_co_benefit_description,
            carbon_credit=submission.mitigation_data.carbon_credit,
            cdm_voluntary=submission.mitigation_data.cdm_voluntary,
            cdm_executive_board_status=submission.mitigation_data.cdm_executive_board_status,
            cdm_methodology=submission.mitigation_data.cdm_methodology,
            organization_issuing_credits=submission.mitigation_data.organization_issuing_credits,
            voluntary_methodology=submission.mitigation_data.voluntary_methodology,
            cdm_project_number=submission.mitigation_data.cdm_project_number
        )
        db.add(mitigation_record)

    # Create Adaptation record if needed.
    if im_value in ("adaptation", "cross cutting"):
        if not submission.adaptation_data:
            raise HTTPException(
                status_code=400,
                detail="Adaptation data must be provided for 'Adaptation' or 'Cross Cutting' interventions."
            )
        adaptation_record = Adaptaion(
            submission_id=db_submission.id,
            sector=submission.adaptation_data.sector,
            national_policy=submission.adaptation_data.national_policy,
            intervention_goal=submission.adaptation_data.intervention_goal,
            provincial_municipal=submission.adaptation_data.provincial_municipal,
            hazard=submission.adaptation_data.hazard,
            progress_calculator=submission.adaptation_data.progress_calculator,
            climate_impact=submission.adaptation_data.climate_impact,
            address_climate_impact=submission.adaptation_data.address_climate_impact,
            impact_response=submission.adaptation_data.impact_response,
        )
        db.add(adaptation_record)

    db.commit()
    return {
        "detail": "Submission and related records created successfully.",
        "submission_id": str(db_submission.id)
    }


@router.patch("/update_new_submission/{submission_uuid}")
def update_submission(
        submission_uuid: UUID,
        update_data: SubmissionUpdate,
        db: Session = Depends(get_db)
):
    # Retrieve the submission. If not found, return an error.
    submission = db.query(Submission).filter(Submission.id == submission_uuid).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Prepare the update dictionary for the submission after excluding unset fields.
    data = update_data.dict(exclude_unset=True)

    # Extract nested update payloads (if any) and remove them from the main update dictionary.
    mitigation_update = data.pop("mitigation_data", None)
    adaptation_update = data.pop("adaptation_data", None)

    # Determine the new intervention type.
    # If the update payload provides a new intervention_measurement, use that; otherwise, keep the old type.
    new_intervention = (
        data.get("intervention_measurement", submission.intervention_measurement)
        .strip()
        .lower()
    )

    # Update the primary submission fields.
    for key, value in data.items():
        setattr(submission, key, value)

    # --- Handling Related Records Based on the New Intervention Type ---
    #
    # Option 1: new intervention is "mitigation" (only mitigation should exist)
    if new_intervention == "mitigation":
        # Remove adaptation record if it exists.
        adaptation = db.query(Adaptaion).filter(Adaptaion.submission_id == submission.id).first()
        if adaptation:
            db.delete(adaptation)

        # Process mitigation record.
        mitigation = db.query(Mitigation).filter(Mitigation.submission_id == submission.id).first()
        if mitigation_update is not None:
            if mitigation:
                # Update the existing mitigation.
                for key, value in mitigation_update.items():
                    setattr(mitigation, key, value)
            else:
                # Create a new mitigation record.
                new_mitigation = Mitigation(
                    submission_id=submission.id,
                    **mitigation_update
                )
                db.add(new_mitigation)
        else:
            # If no mitigation update payload is given, but an existing mitigation record does not exist,
            # you might want to ensure one exists (or simply do nothing).
            pass

    # Option 2: new intervention is "adaptation" (only adaptation should exist)
    elif new_intervention == "adaptation":
        # Remove mitigation record if it exists.
        mitigation = db.query(Mitigation).filter(Mitigation.submission_id == submission.id).first()
        if mitigation:
            db.delete(mitigation)

        # Process adaptation update.
        adaptation = db.query(Adaptaion).filter(Adaptaion.submission_id == submission.id).first()
        if adaptation_update is not None:
            if adaptation:
                for key, value in adaptation_update.items():
                    setattr(adaptation, key, value)
            else:
                new_adaptation = Adaptaion(
                    submission_id=submission.id,
                    **adaptation_update
                )
                db.add(new_adaptation)
        else:
            pass

    # Option 3: new intervention is "cross cutting" (both records should exist)
    elif new_intervention == "cross cutting":
        # Process mitigation data if provided.
        if mitigation_update is not None:
            mitigation = db.query(Mitigation).filter(Mitigation.submission_id == submission.id).first()
            if mitigation:
                for key, value in mitigation_update.items():
                    setattr(mitigation, key, value)
            else:
                new_mitigation = Mitigation(
                    submission_id=submission.id,
                    **mitigation_update
                )
                db.add(new_mitigation)
        # Process adaptation data if provided.
        if adaptation_update is not None:
            adaptation = db.query(Adaptaion).filter(Adaptaion.submission_id == submission.id).first()
            if adaptation:
                for key, value in adaptation_update.items():
                    setattr(adaptation, key, value)
            else:
                new_adaptation = Adaptaion(
                    submission_id=submission.id,
                    **adaptation_update
                )
                db.add(new_adaptation)
    else:
        # If the intervention type does not match any expected values, you can choose to ignore the nested updates
        # or raise an error.
        raise HTTPException(status_code=400, detail="Invalid intervention_measurement type provided.")

    # Commit all changes to the database.
    db.commit()
    db.refresh(submission)
    return submission

@router.get("/read_submission/{submission_uuid}", response_model=SubmissionResponse)
def read_submission(submission_uuid: UUID, db: Session = Depends(get_db)):
    # 1. Retrieve the submission using the auto-generated UUID.
    submission = db.query(Submission).filter(Submission.id == submission_uuid).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # 2. Retrieve related records.
    mitigation = db.query(Mitigation).filter(Mitigation.submission_id == submission.id).first()
    adaptation = db.query(Adaptaion).filter(Adaptaion.submission_id == submission.id).first()

    # 3. Determine based on intervention_measurement which related data to attach.
    # Normalize the intervention_measurement value.
    im_value = submission.intervention_measurement.strip().lower() if submission.intervention_measurement else ""

    if im_value == "cross cutting":
        # Both records are applicable.
        submission.mitigation = mitigation
        submission.adaptation = adaptation
    elif im_value == "adaptation":
        # Only adaptation data should be provided.
        submission.mitigation = None
        submission.adaptation = adaptation
    elif im_value == "mitigation":
        # Only mitigation data should be provided.
        submission.mitigation = mitigation
        submission.adaptation = None
    else:
        # If intervention_measurement is set to an unexpected value,
        # default to not adding any nested records.
        submission.mitigation = None
        submission.adaptation = None

    # 4. Return the submission with the nested related records.
    return submission

@router.post("/upload-xlsx/")
async def upload_xlsm(file: UploadFile = File(...),db: Session = Depends(get_db)):
    try:
        contents = await file.read()  # Read file as bytes
        wb = load_workbook(BytesIO(contents), keep_vba=True)  # Load workbook with macros

        sheet = wb['General project details']
        submission_data = {}
        for row in sheet.iter_rows(values_only=True):
            title = row[0]
            field_value = next((value for value in row[1:] if value is not None), None)
            if field_value is not None:
                # Mapping the data

                if title == 'Title':
                    submission_data['title'] = field_value
                elif title == 'Indicate the type of measure':
                    submission_data['intervention_measurement'] = field_value
                elif title == 'Description':
                    submission_data['description'] = field_value
                elif title == 'Implementation status':
                    submission_data['implementation_status'] = field_value
                elif title == 'Implementing organization':
                    submission_data['implementation_organization'] = field_value
                elif title == 'Other implementing partners':
                    submission_data['implementation_partners_other'] = field_value
                elif title == 'Start year':
                    submission_data['start_date'] = field_value
                elif title == 'End year':
                    submission_data['end_date'] = field_value
                elif title == 'Link to project website':
                    submission_data['link'] = field_value
                elif title == 'Funding organization':
                    submission_data['funding_organization'] = field_value
                elif title == 'Type of funding':
                    submission_data['funding_type'] = field_value
                    # elif title == 'Type of funding (other)':
                    #     submission_data['funding_type_other'] = field_value
                elif title == 'Actual budget':
                    submission_data['funding_amount'] = float(field_value)
                elif title == 'Estimated budget range':
                    submission_data['estimated_budget_cost'] = field_value
                elif title == 'Name':
                    submission_data['project_manager_name'] = field_value
                elif title == 'Company/organization':
                    submission_data['project_manager_organization'] = field_value
                elif title == 'Position':
                    submission_data['project_manager_position'] = field_value
                elif title == 'Email address':
                    submission_data['project_manager_email'] = field_value
                elif title == 'Mobile number':
                    submission_data['project_manager_mobile'] = field_value
                # Continue for other relevant fields...

                # Optionally, add geo_location data if provided
        submission_data['geo_location'] = {
            "type": "Point",
            "coordinates": [30.374, -27.936]  # You can replace this with actual coordinates if available
        }
        print("submission data:",submission_data)
            # Convert extracted data into SubmissionCreate model
        submission_create = SubmissionCreate(**submission_data)
        print(submission_create)
        # Call the create_submission function
        data = create_submission(submission_create, db)
        return  {"Submission Created":data}

    except Exception as e:
        return {"error": str(e)}