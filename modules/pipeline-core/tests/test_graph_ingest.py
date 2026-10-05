import json
from unittest.mock import MagicMock, patch
import pytest
from pipeline_core.graph.queries import GRAPH_RAG_QUERIES
from pipeline_core.graph.ingest_graph import Neo4jGraphIngestor
from pipeline_core.schemas.handoff import LSTExportPayload, ClassRecord, FieldRecord, MethodRecord, InvocationRecord


def test_cypher_queries_defined():
    assert "VERTICAL_SLICE_BY_CLASS" in GRAPH_RAG_QUERIES
    assert "ALL_ENDPOINTS_AND_SERVICES" in GRAPH_RAG_QUERIES
    assert "DEPENDENCY_CALL_GRAPH" in GRAPH_RAG_QUERIES
    assert "MATCH (c:Class" in GRAPH_RAG_QUERIES["VERTICAL_SLICE_BY_CLASS"]


class TestNeo4jGraphIngestorMocked:

    @pytest.fixture
    def sample_payload(self):
        return LSTExportPayload(
            schemaVersion="1.0.0",
            extractedAt="2026-10-03T12:00:00Z",
            sourceDirectory="/test/path",
            classes=[
                ClassRecord(
                    fqn="com.legacy.banking.web.TransferManagedBean",
                    simpleName="TransferManagedBean",
                    kind="CLASS",
                    annotations=["ManagedBean", "SessionScoped"],
                    fields=[
                        FieldRecord(
                            name="transferService",
                            type="TransferProcessingService",
                            typeFqn="com.legacy.banking.service.TransferProcessingService",
                            annotation="EJB"
                        )
                    ],
                    methods=[
                        MethodRecord(
                            name="execute",
                            returnType="java.lang.String",
                            parameterTypes=[],
                            annotations=[],
                            signature="com.legacy.banking.web.TransferManagedBean.execute()"
                        )
                    ],
                    invocations=[
                        InvocationRecord(
                            callerClassFqn="com.legacy.banking.web.TransferManagedBean",
                            callerMethodName="execute",
                            targetClassFqn="com.legacy.banking.service.TransferProcessingService",
                            targetMethodName="processTransfer",
                            returnType="java.lang.String",
                            argumentTypes=["java.lang.String", "java.lang.String", "java.math.BigDecimal"]
                        )
                    ]
                ),
                ClassRecord(
                    fqn="com.legacy.banking.service.TransferProcessingService",
                    simpleName="TransferProcessingService",
                    kind="CLASS",
                    annotations=["Stateless"],
                    fields=[
                        FieldRecord(
                            name="cicsGateway",
                            type="CicsMainframeGateway",
                            typeFqn="com.legacy.banking.gateway.CicsMainframeGateway",
                            annotation="Inject"
                        )
                    ],
                    methods=[
                        MethodRecord(
                            name="processTransfer",
                            returnType="java.lang.String",
                            parameterTypes=["java.lang.String", "java.lang.String", "java.math.BigDecimal"],
                            annotations=["TransactionAttribute"],
                            signature="com.legacy.banking.service.TransferProcessingService.processTransfer(java.lang.String,java.lang.String,java.math.BigDecimal)",
                            thrownExceptions=["IllegalArgumentException", "IllegalStateException"],
                            branchCount=5,
                            bodySource="if (amount <= 0) throw new IllegalArgumentException();"
                        )
                    ],
                    invocations=[
                        InvocationRecord(
                            callerClassFqn="com.legacy.banking.service.TransferProcessingService",
                            callerMethodName="processTransfer",
                            targetClassFqn="com.legacy.banking.gateway.CicsMainframeGateway",
                            targetMethodName="executeTransfer",
                            returnType="java.lang.String",
                            argumentTypes=["java.lang.String", "java.lang.String", "java.math.BigDecimal"]
                        )
                    ]
                )
            ]
        )

    def test_ingest_metrics_and_cypher_calls(self, sample_payload):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        with patch("pipeline_core.graph.ingest_graph.GraphDatabase.driver", return_value=mock_driver):
            ingestor = Neo4jGraphIngestor(uri="bolt://localhost:7687", user="neo4j", password="pwd")
            metrics = ingestor.ingest(sample_payload)

            assert metrics["classes"] == 2
            assert metrics["annotations"] == 3  # ManagedBean, SessionScoped, Stateless
            assert metrics["annotated_with_edges"] == 3
            assert metrics["methods"] == 2
            assert metrics["declares_edges"] == 2
            assert metrics["injects_edges"] == 2
            assert metrics["calls_edges"] == 2

            # Verify that session.run was called for schema DDL and batches
            assert mock_session.run.call_count >= 10
            ingestor.close()
            mock_driver.close.assert_called_once()
