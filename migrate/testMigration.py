import xlwings as xw
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from nccrd.db import Base  # Adjust this import if needed
from nccrd.models import Submission, Adaptaion, Mitigation  # Adjust to match your project

# --- Database Setup ---
DATABASE_URL = "postgresql://user:password@localhost:5432/nccrd_db"  # Update credentials
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# --- Excel Setup ---
wb = xw.Book("ccrd-template-2025-04-29T09_57_25.362Z.xlsm")  # Update path if needed
sheet = wb.sheets["Project Info"]  # Change to your actual sheet name

# --- Extract Data from Sheet ---
data = sheet.range("A2").expand("table").value  # assumes headers are in A1
headers = sheet.range("A1").expand("right").value

# --- Process Each Row ---
for row in data:
    row_dict = dict(zip(headers, row))

    try:
        submission = Submission(
            title=row_dict.get("Project Title"),
            intervention_measurement=row_dict.get("Type of Intervention"),
            description=row_dict.get("Description"),
            implementation_status=row_dict.get("Status"),
            implementation_organization=row_dict.get("Implementing Org"),
            implementation_partners_other=row_dict.get("Partners"),
            start_date=datetime.strptime(row_dict["Start Date"], "%Y-%m-%d") if row_dict.get("Start Date") else None,
            end_date=datetime.strptime(row_dict["End Date"], "%Y-%m-%d") if row_dict.get("End Date") else None,
            link=row_dict.get("Website"),
            funding_organization=row_dict.get("Funder"),
            funding_type=row_dict.get("Funding Type"),
            funding_amount=float(row_dict["Funding Amount"]) if row_dict.get("Funding Amount") else None,
            estimated_budget_cost=row_dict.get("Estimated Budget"),
            geo_location={"province": row_dict.get("Province"), "municipality": row_dict.get("Municipality")},
            project_manager_name=row_dict.get("Manager Name"),
            project_manager_organization=row_dict.get("Manager Org"),
            project_manager_position=row_dict.get("Manager Role"),
            project_manager_email=row_dict.get("Manager Email"),
            project_manager_phone=row_dict.get("Manager Phone"),
            project_manager_mobile=row_dict.get("Manager Mobile"),
            submission_status=row_dict.get("Submission Status"),
            submission_comments=row_dict.get("Comments"),
            issubmitted=row_dict.get("Submitted") == "Yes",
            research=row_dict.get("Research Type"),
            createdby=1,  # Replace with current user ID
            createdate=datetime.utcnow(),
        )

        session.add(submission)
        session.flush()  # ensures submission.id is available

        if row_dict.get("Sector Type") == "Adaptation":
            adaptation = Adaptaion(
                submission_id=submission.id,
                sector=row_dict.get("Sector"),
                national_policy=row_dict.get("National Policy"),
                intervention_goal=row_dict.get("Goal"),
                provincial_municipal=row_dict.get("Local Policy"),
                hazard=row_dict.get("Hazard"),
                progress_calculator=row_dict.get("Progress"),
                climate_impact=row_dict.get("Impact"),
                address_climate_impact=row_dict.get("Address Impact"),
                impact_response=row_dict.get("Impact Response"),
            )
            session.add(adaptation)

        elif row_dict.get("Sector Type") == "Mitigation":
            mitigation = Mitigation(
                submission_id=submission.id,
                sector=row_dict.get("Sector"),
                subsector=row_dict.get("Subsector"),
                secondary=row_dict.get("Secondary Sector"),
                project_type=row_dict.get("Project Type"),
                project_subtype=row_dict.get("Subtype"),
                mitigation_program=row_dict.get("Program"),
                national_policy=row_dict.get("National Policy"),
                provincial_municipal=row_dict.get("Local Policy"),
                primary_intended_outcome=row_dict.get("Outcome"),
                progress_calculator=row_dict.get("Progress"),
                enviromental_co_benefit=row_dict.get("Env Co-benefit"),
                enviromental_co_benefit_description=row_dict.get("Env Description"),
                social_co_benefit=row_dict.get("Soc Co-benefit"),
                social_co_benefit_description=row_dict.get("Soc Description"),
                economic_co_benefit=row_dict.get("Econ Co-benefit"),
                economic_co_benefit_description=row_dict.get("Econ Description"),
                carbon_credit=row_dict.get("Carbon Credit") == "Yes",
                cdm_voluntary=row_dict.get("CDM Type"),
                cdm_executive_board_status=row_dict.get("CDM Status"),
                cdm_methodology=row_dict.get("Methodology"),
                organization_issuing_credits=row_dict.get("Issuer"),
                voluntary_methodology=row_dict.get("Vol Methodology"),
                cdm_project_number=row_dict.get("Project Number"),
            )
            session.add(mitigation)

    except Exception as e:
        print(f"Error processing row: {row_dict}")
        print(e)

# --- Finalize ---
session.commit()
session.close()
print("Done importing projects.")
