from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from nccrd.api.models import SubmissionModel, SubmissionCreate, SubmissionUpdate, SubmissionResponse, \
    MitigationResponse, AdaptationResponse
from uuid import UUID

from nccrd.const import NCCRDScope
from nccrd.db import get_db
from nccrd.db.models import Submission, Adaptaion, Mitigation
from openpyxl import load_workbook
from io import BytesIO
from datetime import datetime
import traceback

from nccrd.api.lib.auth import Authorize

router = APIRouter()


@router.get(
    '/list_submission',
    response_model=Union[SubmissionModel, List[SubmissionModel]],
    summary='List all submissions or a specific submissions by its ID'
)
async def get_submissions_list(
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


@router.get("/read_submission/{submission_uuid}",
            response_model=SubmissionResponse,
            dependencies=[Depends(Authorize(NCCRDScope.PROJECT_READ))],
            )
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

    print("Value:", im_value)
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
        submission_status='Pending',
        # submission_comments=submission.submission_comments,
        issubmitted=True,
        platfrom=submission.platfrom,
        research=submission.research,
        createdby='1',
        createdate=datetime.utcnow(),
        # updatedate=submission.updatedate,
        # updatedby=submission.updatedby,
        # deletedby=submission.deletedby,
        # deletedate=submission.deletedate,
        # deleted=submission.deleted,
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


@router.post("/create_submission_upload-xlsx/")
async def create_submission_upload_xlsm(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
        print("submission data:", submission_data)
        # Convert extracted data into SubmissionCreate model
        submission_create = SubmissionCreate(**submission_data)
        print(submission_create)
        # Call the create_submission function
        data = create_submission(submission_create, db)
        return {"Submission Created": data}

    except Exception as e:
        return {"error": str(e)}


@router.post("/create_submission_upload-test-xlsx/")
async def create_submission_upload_test_xlsx(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        contents = await file.read()
        wb = load_workbook(BytesIO(contents), keep_vba=True, read_only=True, data_only=True)

        # === Step 1: General Project Details ===
        sheet = wb['General project details']
        submission_data = {}
        for row in sheet.iter_rows(values_only=True):
            title = row[0]
            value = next((v for v in row[1:] if v is not None), None)
            if value is not None and title:
                title = str(title).strip()
                if title == 'Title':
                    submission_data['title'] = value
                elif title == 'Indicate the type of measure':
                    val = value.lower()
                    if "mitigation" in val:
                        submission_data['intervention_measurement'] = "Mitigation"
                    elif "adaptation" in val:
                        submission_data['intervention_measurement'] = "Adaptation"
                    elif "cross" in val:
                        submission_data['intervention_measurement'] = "Cross Cutting"
                elif title == 'Description':
                    submission_data['description'] = value
                elif title == 'Implementation status':
                    submission_data['implementation_status'] = value
                elif title == 'Implementing organization':
                    submission_data['implementation_organization'] = value
                elif title == 'Other implementing partners':
                    submission_data['implementation_partners_other'] = value
                elif title == 'Start year':
                    submission_data['start_date'] = value
                elif title == 'End year':
                    submission_data['end_date'] = value
                elif title == 'Link to project website':
                    submission_data['link'] = value
                elif title == 'Funding organization':
                    submission_data['funding_organization'] = value
                elif title == 'Type of funding':
                    submission_data['funding_type'] = value
                elif title == 'Actual budget':
                    submission_data['funding_amount'] = float(value)
                elif title == 'Estimated budget range':
                    submission_data['estimated_budget_cost'] = value
                elif title == 'Name':
                    submission_data['project_manager_name'] = value
                elif title == 'Company/organization':
                    submission_data['project_manager_organization'] = value
                elif title == 'Position':
                    submission_data['project_manager_position'] = value
                elif title == 'Email address':
                    submission_data['project_manager_email'] = value
                elif title == 'Mobile number':
                    submission_data['project_manager_mobile'] = value

        submission_data['geo_location'] = {
            "type": "Point",
            "coordinates": [30.374, -27.936]  # Replace with real values if needed
        }

        im_type = submission_data.get("intervention_measurement", "").lower()

        # === Step 2: Adaptation ===
        if im_type in ("adaptation", "cross cutting"):
            adap_sheet = wb["Adaptation details"]
            adaptation_fields = {}
            for row in adap_sheet.iter_rows(values_only=True):
                label = str(row[0]).strip() if row[0] else None
                value = next((v for v in row[1:] if v is not None), None)
                if label and value:
                    if label == "Adaptation sector":
                        adaptation_fields["sector"] = value
                    elif label == "National policy":
                        adaptation_fields["national_policy"] = value
                    elif label == "Overall adaptation intervention goal":
                        adaptation_fields["intervention_goal"] = value
                    elif label == "Provincial / municipal policy / framework":
                        adaptation_fields["provincial_municipal"] = value
                    elif label == "Hazard":
                        adaptation_fields["hazard"] = value
                    elif label == "Progress calculator / explanation":
                        adaptation_fields["progress_calculator"] = value
                    elif label == "Observed and projected climate change impacts":
                        adaptation_fields["climate_impact"] = value
                    elif label == "How the intervention addresses the climate impact":
                        adaptation_fields["address_climate_impact"] = value
                    elif label == "Adaptation impact response":
                        adaptation_fields["impact_response"] = value

            if "sector" not in adaptation_fields:
                raise HTTPException(status_code=400, detail="Adaptation sector is required.")
            submission_data["adaptation_data"] = AdaptationResponse(**adaptation_fields)

        # === Step 3: Mitigation ===
        if im_type in ("mitigation", "cross cutting"):
            mit_sheet = wb["Mitigation details"]
            mitigation_fields = {}
            for row in mit_sheet.iter_rows(values_only=True):
                label = str(row[0]).strip() if row[0] else None
                value = next((v for v in row[1:] if v is not None), None)
                if label and value is not None:
                    if label == "Mitigation sector":
                        mitigation_fields["sector"] = value
                    elif label == "Subsector":
                        mitigation_fields["subsector"] = value
                    elif label == "Secondary sector":
                        mitigation_fields["secondary"] = value
                    elif label == "Project type":
                        mitigation_fields["project_type"] = value
                    elif label == "Project subtype":
                        mitigation_fields["project_subtype"] = value
                    elif label == "Mitigation programme":
                        mitigation_fields["mitigation_program"] = value
                    elif label == "National policy":
                        mitigation_fields["national_policy"] = value
                    elif label == "Provincial / municipal policy / framework":
                        mitigation_fields["provincial_municipal"] = value
                    elif label == "Primary intended mitigation outcome":
                        mitigation_fields["primary_intended_outcome"] = value
                    elif label == "Progress calculator / explanation":
                        mitigation_fields["progress_calculator"] = value
                    elif label == "Environmental co-benefit":
                        mitigation_fields["enviromental_co_benefit"] = value
                    elif label == "Environmental co-benefit description":
                        mitigation_fields["enviromental_co_benefit_description"] = value
                    elif label == "Social co-benefit":
                        mitigation_fields["social_co_benefit"] = value
                    elif label == "Social co-benefit description":
                        mitigation_fields["social_co_benefit_description"] = value
                    elif label == "Economic co-benefit":
                        mitigation_fields["economic_co_benefit"] = value
                    elif label == "Economic co-benefit description":
                        mitigation_fields["economic_co_benefit_description"] = value
                    elif label == "Are carbon credits issued?":
                        mitigation_fields["carbon_credit"] = value in ["Yes", "yes", "TRUE", True]
                    elif label == "CDM / Voluntary":
                        mitigation_fields["cdm_voluntary"] = value
                    elif label == "CDM Executive Board status":
                        mitigation_fields["cdm_executive_board_status"] = value
                    elif label == "CDM methodology":
                        mitigation_fields["cdm_methodology"] = value
                    elif label == "Organisation issuing carbon credits":
                        mitigation_fields["organization_issuing_credits"] = value
                    elif label == "Voluntary methodology":
                        mitigation_fields["voluntary_methodology"] = value
                    elif label == "CDM project number":
                        mitigation_fields["cdm_project_number"] = value

            if "sector" not in mitigation_fields:
                raise HTTPException(status_code=400, detail="Mitigation sector is required.")
            submission_data["mitigation_data"] = MitigationResponse(**mitigation_fields)

        # === Step 4: Submit to DB ===
        submission_create = SubmissionCreate(**submission_data)
        data = create_submission(submission_create, db)
        return {"Submission Created": data}

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
