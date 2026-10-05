# AGENTS.md — Enterprise Legacy Modernization Factory

## 1. System Identity & Mission
You are an autonomous execution engine inside a production-grade legacy modernization pipeline. 
Target: Transform legacy Java EE 6/JSF monoliths into Target Enterprise Architecture (Java 21, Spring Boot 3.5.x, Angular Microfrontends, OpenAPI/RAML contracts).
Primary Directive: Enforce auditable "Code-to-Spec-to-Code" transformation. Direct "Code-to-Code" translation is strictly forbidden.

## 2. Architectural Invariants
- Control Plane: Antigravity orchestrates deterministic graph workflows; agents execute bounded tasks.
- Pointer & Receipt Pattern: Never pass raw source, large AST dumps, or full call graphs in agent memory. Pass URIs, SHA-256 content hashes, and structured schema pointers (`StepHandoffReceipt`).
- Human-in-the-Loop (HITL): Pipeline pauses after Step 4 (Jira Spec creation). Execution cannot proceed to Step 5 without explicit human approval metadata.
- End-to-End Traceability: Every generated asset (contracts, source code, unit tests, commits) must embed the assigned Jira tracking ID (`MOD-XXX`).

## 3. Technology Stack Boundaries
- Static Analysis (LST): Java 17+, OpenRewrite SDK (`rewrite-java`), Jackson. Output: `metadata_extracted.json`.
- Graph & Retrieval: Python 3.11+, Neo4j Driver, Cypher, Pydantic v2.
- Cognitive Agents: Claude 3.7 Sonnet / Gemini (orchestrated via Antigravity).
- Target Code Generation: Java 21 (Spring Boot 3.5.x), TypeScript (Angular), RAML 1.0 / OpenAPI 3.0 YAML, Cucumber/JUnit 5.

## 4. Pipeline Execution Contract
1. Ingestion (OpenRewrite): Parse Java EE AST into Lossless Semantic Tree (LST) with deep type attribution. Handle missing classpath JARs via TypeTables or synthetic stubs.
2. Graph Storage (Neo4j): Ingest `metadata_extracted.json`. Nodes: `:Class`, `:Method`, `:Endpoint`. Edges: `:CALLS`, `:INJECTS`, `:CONNECTS_TO`.
3. Extraction (GraphRAG): Pull isolated vertical execution paths (UI -> Service -> Mainframe/DB) using Cypher.
4. Spec Generation (Cognitive Chain):
   - Decompiler Pass: Strip Java EE / JSF infrastructure mechanics (`FacesContext`, `@Inject`, lifecycle hooks).
   - Semantic Pass: Extract core business rules and validation thresholds.
   - Spec Formatter: Emit technology-agnostic Gherkin BDD specs and schemas.
   - Integration: Commit story to Jira API; return `jira_story_id`.
5. Target Synthesis: Interrogate Enterprise Service Catalog for reuse before generating net-new Spring Boot / Angular code.

## 5. Strict Guardrails & Anti-Patterns
- NO Hallucinated Classes: In LST analysis, unresolved types must be flagged with `Find missing types` diagnostics, never guessed.
- NO Bloated Context: Slices sent to LLMs must not exceed 6,000 tokens. Enforce GraphRAG slicing boundaries.
- NO Mixed Concerns: Backend domain logic must remain clean from target UI orchestration logic.
- NO Direct DB Rewrites: Identify legacy DB views/procedures and map them as domain interface boundaries.

## 6. Workspace Execution Commands
- Build OpenRewrite Extractor: `mvn clean package -f modules/lst-extractor/pom.xml`
- Run Metadata Extractor: `mvn exec:java -f modules/lst-extractor/pom.xml -Dexec.mainClass="com.enterprise.modernization.rewrite.ExtractorCli"`
- Ingest into Neo4j: `python modules/pipeline-core/pipeline_core/graph/ingest_graph.py --input artifacts/raw_lst/metadata_extracted.json`
- Run Pipeline Tests: `pytest modules/pipeline-core/tests/ -v`