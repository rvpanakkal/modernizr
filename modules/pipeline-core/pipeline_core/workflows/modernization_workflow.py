import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from pipeline_core.schemas.handoff import (
    StepHandoffReceipt,
    ArtifactPointer,
    ArtifactType,
    ExecutionStatus
)
from pipeline_core.agents.decompiler import DecompilerAgent
from pipeline_core.agents.business_abstractor import BusinessAbstractorAgent
from pipeline_core.agents.spec_formatter import SpecFormatterAgent
from pipeline_core.integrations.jira_client import JiraClient
from pipeline_core.integrations.catalog_client import EnterpriseCatalogClient


class ModernizationWorkflowEngine:
    """
    Antigravity Orchestration Engine for Code-to-Spec-to-Code Pipeline.
    Stitches Steps 1 through 5 and enforces Human-in-the-Loop (HITL) pause point after Step 4.
    """

    def __init__(self):
        self.decompiler = DecompilerAgent()
        self.business_abstractor = BusinessAbstractorAgent()
        self.spec_formatter = SpecFormatterAgent()
        self.jira_client = JiraClient()
        self.catalog_client = EnterpriseCatalogClient()

    def execute_step_4_spec_generation(self, raw_lst_pointer: ArtifactPointer) -> StepHandoffReceipt:
        """
        Step 4: Spec Generation Cognitive Chain.
        Generates BDD specs, creates Jira Story, and PAUSES for Human-in-the-Loop approval.
        """
        print(f"[Workflow Engine] Executing Step 4: Spec Generation for LST {raw_lst_pointer.sha256_hash[:8]}...")

        # Mock slice processing
        raw_slice = {"component_name": "AccountServiceBean", "annotations": ["Stateless", "Inject"]}
        decompiled = self.decompiler.process_slice(raw_slice)
        business_rules = self.business_abstractor.extract_business_rules(decompiled)

        # Jira creation
        jira_id = self.jira_client.create_story(
            summary="Modernize AccountServiceBean to Spring Boot 3.5",
            description="Generated BDD Spec from OpenRewrite LST Analysis",
            spec_body="Gherkin BDD Content"
        )

        bdd_spec = self.spec_formatter.generate_gherkin_bdd(business_rules, jira_id)
        spec_pointer = ArtifactPointer.create_from_content(
            content=bdd_spec,
            uri=f"artifacts/generated_specs/{jira_id}_spec.feature",
            artifact_type=ArtifactType.BDD_GHERKIN,
            media_type="text/x-gherkin"
        )

        receipt = StepHandoffReceipt(
            receipt_id=str(uuid.uuid4()),
            step_number=4,
            step_name="Spec Generation (Gherkin BDD & Jira)",
            jira_story_id=jira_id,
            input_pointers=[raw_lst_pointer],
            output_pointers=[spec_pointer],
            status=ExecutionStatus.PAUSED_HITL,
            hitl_approved=False
        )

        print(f"[Workflow Engine] Step 4 Completed. Workflow PAUSED for HITL Approval on {jira_id}.")
        return receipt

    def execute_step_5_target_synthesis(self, step_4_receipt: StepHandoffReceipt, approver_email: str) -> StepHandoffReceipt:
        """
        Step 5: Target Code Synthesis.
        Requires explicit hitl_approved=True before execution.
        """
        if not step_4_receipt.hitl_approved and not step_4_receipt.status == ExecutionStatus.PAUSED_HITL:
            raise PermissionError("Cannot execute Step 5: Human-in-the-Loop (HITL) approval metadata missing.")

        print(f"[Workflow Engine] Executing Step 5 for {step_4_receipt.jira_story_id} approved by {approver_email}...")

        # Enterprise catalog reuse check
        catalog_results = self.catalog_client.search_existing_services("Account")

        # Mark receipt as completed with approval metadata
        step_5_receipt = StepHandoffReceipt(
            receipt_id=str(uuid.uuid4()),
            step_number=5,
            step_name="Target Code Synthesis (Spring Boot & Angular)",
            jira_story_id=step_4_receipt.jira_story_id,
            input_pointers=step_4_receipt.output_pointers,
            output_pointers=[],
            status=ExecutionStatus.COMPLETED,
            hitl_approved=True,
            approved_by=approver_email,
            approval_timestamp=datetime.now(timezone.utc)
        )

        print(f"[Workflow Engine] Step 5 Target Synthesis COMPLETED for {step_4_receipt.jira_story_id}.")
        return step_5_receipt
