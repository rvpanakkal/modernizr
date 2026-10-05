import pytest
import uuid
from datetime import datetime, timezone
from pipeline_core.schemas.handoff import (
    ArtifactPointer,
    ArtifactType,
    ClassRecord,
    ExecutionStatus,
    FieldRecord,
    InvocationRecord,
    LSTExportPayload,
    MethodRecord,
    StepHandoffReceipt,
)


# =============================================================================
# ArtifactPointer Tests
# =============================================================================

class TestArtifactPointer:

    def test_sha256_generation_from_string(self):
        content = "sample gherkin feature spec content"
        pointer = ArtifactPointer.create_from_content(
            content=content,
            uri="artifacts/generated_specs/MOD-101.feature",
            artifact_type=ArtifactType.BDD_GHERKIN,
        )
        assert len(pointer.sha256_hash) == 64
        assert pointer.uri == "artifacts/generated_specs/MOD-101.feature"
        assert pointer.size_bytes == len(content.encode("utf-8"))
        assert pointer.artifact_type == ArtifactType.BDD_GHERKIN

    def test_sha256_generation_from_bytes(self):
        content = b"\x00\x01\x02binary content"
        pointer = ArtifactPointer.create_from_content(
            content=content,
            uri="artifacts/raw_lst/test.bin",
            artifact_type=ArtifactType.RAW_LST_JSON,
        )
        assert len(pointer.sha256_hash) == 64
        assert pointer.size_bytes == len(content)

    def test_sha256_is_deterministic(self):
        content = "deterministic content"
        p1 = ArtifactPointer.create_from_content(content, "uri1", ArtifactType.RAW_LST_JSON)
        p2 = ArtifactPointer.create_from_content(content, "uri2", ArtifactType.RAW_LST_JSON)
        assert p1.sha256_hash == p2.sha256_hash


# =============================================================================
# StepHandoffReceipt HITL Enforcement Tests
# =============================================================================

class TestStepHandoffReceipt:

    @pytest.fixture
    def sample_pointer(self):
        return ArtifactPointer.create_from_content(
            "test content", "artifacts/raw_lst/test.json", ArtifactType.RAW_LST_JSON
        )

    def test_step4_paused_without_hitl_approval_is_valid(self, sample_pointer):
        receipt = StepHandoffReceipt(
            receipt_id    = str(uuid.uuid4()),
            step_number   = 4,
            step_name     = "Spec Generation",
            jira_story_id = "MOD-101",
            input_pointers = [sample_pointer],
            status        = ExecutionStatus.PAUSED_HITL,
            hitl_approved = False,
        )
        assert receipt.step_number == 4
        assert receipt.hitl_approved is False
        assert receipt.status == ExecutionStatus.PAUSED_HITL

    def test_step5_without_hitl_approved_raises_value_error(self, sample_pointer):
        with pytest.raises(ValueError, match="Execution of Step 5"):
            StepHandoffReceipt(
                receipt_id    = str(uuid.uuid4()),
                step_number   = 5,
                step_name     = "Target Synthesis",
                jira_story_id = "MOD-101",
                input_pointers = [sample_pointer],
                status        = ExecutionStatus.COMPLETED,
                hitl_approved = False,
            )

    def test_step5_with_hitl_approved_true_is_valid(self, sample_pointer):
        receipt = StepHandoffReceipt(
            receipt_id        = str(uuid.uuid4()),
            step_number       = 5,
            step_name         = "Target Synthesis",
            jira_story_id     = "MOD-101",
            input_pointers    = [sample_pointer],
            status            = ExecutionStatus.COMPLETED,
            hitl_approved     = True,
            approved_by       = "lead_architect@enterprise.com",
            approval_timestamp = datetime.now(timezone.utc),
        )
        assert receipt.hitl_approved is True
        assert receipt.approved_by == "lead_architect@enterprise.com"

    def test_jira_story_id_pattern_enforced(self, sample_pointer):
        with pytest.raises(Exception):
            StepHandoffReceipt(
                receipt_id    = str(uuid.uuid4()),
                step_number   = 1,
                step_name     = "Test",
                jira_story_id = "INVALID-ID",  # must match ^MOD-\d+$
                status        = ExecutionStatus.COMPLETED,
            )

    def test_receipt_metrics_field(self, sample_pointer):
        receipt = StepHandoffReceipt(
            receipt_id    = str(uuid.uuid4()),
            step_number   = 2,
            step_name     = "Neo4j Ingestion",
            jira_story_id = "MOD-001",
            status        = ExecutionStatus.COMPLETED,
            metrics       = {"classes": 4, "methods": 12, "injects_edges": 5},
        )
        assert receipt.metrics["classes"] == 4
        assert receipt.metrics["injects_edges"] == 5


# =============================================================================
# LST Export Payload Schema Tests
# =============================================================================

class TestLSTExportPayload:

    def test_parse_camelcase_json(self):
        """Pydantic models must accept camelCase aliases from Java Jackson output."""
        raw = {
            "schemaVersion":   "1.0.0",
            "extractedAt":     "2026-10-01T12:00:00Z",
            "sourceDirectory": "/src/legacy",
            "classes": [
                {
                    "fqn":         "com.legacy.banking.web.TransferManagedBean",
                    "simpleName":  "TransferManagedBean",
                    "kind":        "CLASS",
                    "annotations": ["ManagedBean", "SessionScoped"],
                    "fields": [
                        {
                            "name":       "transferService",
                            "type":       "TransferProcessingService",
                            "typeFqn":    "com.legacy.banking.service.TransferProcessingService",
                            "annotation": "EJB",
                        }
                    ],
                    "methods": [
                        {
                            "name":             "execute",
                            "returnType":       "java.lang.String",
                            "parameterTypes":   [],
                            "annotations":      [],
                            "signature":        "com.legacy.banking.web.TransferManagedBean.execute()",
                            "thrownExceptions": ["IllegalArgumentException"],
                            "branchCount":      2,
                            "bodySource":       "return transferService.processTransfer(...);",
                        }
                    ],
                    "invocations": [
                        {
                            "callerClassFqn":   "com.legacy.banking.web.TransferManagedBean",
                            "callerMethodName": "execute",
                            "targetClassFqn":   "com.legacy.banking.service.TransferProcessingService",
                            "targetMethodName": "processTransfer",
                            "returnType":       "java.lang.String",
                            "argumentTypes":    ["java.lang.String", "java.lang.String", "java.math.BigDecimal"],
                        }
                    ],
                }
            ],
        }

        payload = LSTExportPayload.model_validate(raw)
        assert payload.schema_version   == "1.0.0"
        assert payload.source_directory == "/src/legacy"
        assert len(payload.classes)     == 1

        cls = payload.classes[0]
        assert cls.fqn         == "com.legacy.banking.web.TransferManagedBean"
        assert cls.simple_name == "TransferManagedBean"
        assert "ManagedBean" in cls.annotations
        assert len(cls.fields)      == 1
        assert len(cls.methods)     == 1
        assert len(cls.invocations) == 1

        meth = cls.methods[0]
        assert meth.name == "execute"
        assert meth.thrown_exceptions == ["IllegalArgumentException"]
        assert meth.branch_count == 2
        assert meth.body_source == "return transferService.processTransfer(...);"

        field = cls.fields[0]
        assert field.name       == "transferService"
        assert field.annotation == "EJB"
        assert field.type_fqn   == "com.legacy.banking.service.TransferProcessingService"

        inv = cls.invocations[0]
        assert inv.caller_class_fqn   == "com.legacy.banking.web.TransferManagedBean"
        assert inv.target_class_fqn   == "com.legacy.banking.service.TransferProcessingService"
        assert inv.target_method_name == "processTransfer"
        assert "java.math.BigDecimal" in inv.argument_types

    def test_empty_payload_is_valid(self):
        payload = LSTExportPayload.model_validate({
            "schemaVersion":   "1.0.0",
            "extractedAt":     "2026-10-01T12:00:00Z",
            "sourceDirectory": "/tmp/empty",
            "classes":         [],
        })
        assert len(payload.classes) == 0

    def test_invocation_without_type_fqn_is_valid(self):
        raw_class = {
            "fqn":        "com.example.Foo",
            "simpleName": "Foo",
            "kind":       "CLASS",
            "fields": [
                {
                    "name":       "bar",
                    "type":       "BarService",
                    "annotation": "Inject",
                    # typeFqn intentionally absent — graceful degradation test
                }
            ],
        }
        payload = LSTExportPayload.model_validate({
            "schemaVersion":   "1.0.0",
            "extractedAt":     "2026-10-01T12:00:00Z",
            "sourceDirectory": "/src",
            "classes":         [raw_class],
        })
        assert payload.classes[0].fields[0].type_fqn is None
