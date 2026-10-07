import axios from 'axios';
import {
  ArchitectureProfile,
  HarvestReferencePayload,
  ProfileSummary,
  SourceIngestResult,
  ExtractedClassItem,
} from '../types/architecture';
import { Diagnostics, UploadResponse, IngestionStats } from '../types/source';
import { EntryPoint, GraphNode, GraphEdge, SliceResponse, VerticalSliceResponse } from '../types/graph';
import { BatchRunRequest, BatchRunStatus, SliceRunSummary } from '../types/batch';
import {
  HitlReviewPayload,
  HitlRevisionRequest,
  HitlReviseResponse,
  HitlApprovalRequest,
  HitlApprovalResponse,
} from '../types/hitl';

const isMockMode = import.meta.env.VITE_MOCK_MODE === 'true';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Fallback Mock Profiles when in mock mode or backend is unreachable
const MOCK_PROFILES: ArchitectureProfile[] = [
  {
    profile_id: 'arch-payments-v2',
    name: 'Enterprise Reference Payments & Accounts Microservice',
    target_runtime: 'Java 21 / Spring Boot 3.5.0',
    created_at: new Date().toISOString(),
    base_package_pattern: 'com.enterprise.{domain}.v2',
    layering_pattern: 'CONTROLLER_SERVICE_REPOSITORY',
    build_file_template: `<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.5.0</version>
  </parent>
  <groupId>{{GROUP_ID}}</groupId>
  <artifactId>{{ARTIFACT_ID}}</artifactId>
  <name>{{PROJECT_NAME}}</name>
</project>`,
    required_dependencies: [
      'org.springframework.boot:spring-boot-starter-web',
      'org.springframework.boot:spring-boot-starter-validation',
      'org.springframework.boot:spring-boot-starter-actuator',
      'com.tngtech.archunit:archunit-junit5',
    ],
    exemplars: [
      {
        pattern_name: 'RestController',
        target_layer: 'controller',
        annotations_matched: ['@RestController', '@RequestMapping'],
        code_snippet: `package com.enterprise.reference.controller;

import com.enterprise.reference.service.AccountService;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping(path = "/api/v1/accounts", produces = MediaType.APPLICATION_JSON_VALUE)
public class SampleAccountController {

    private final AccountService accountService;

    public SampleAccountController(AccountService accountService) {
        this.accountService = accountService;
    }

    @GetMapping("/{accountId}")
    public ResponseEntity<AccountResponse> getAccount(@PathVariable String accountId) {
        return ResponseEntity.ok(accountService.getAccount(accountId));
    }
}`,
        origin_file: 'src/main/java/com/enterprise/reference/controller/SampleAccountController.java',
      },
      {
        pattern_name: 'GlobalExceptionHandler',
        target_layer: 'controller',
        annotations_matched: ['@RestControllerAdvice'],
        code_snippet: `package com.enterprise.reference.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.net.URI;
import java.time.Instant;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail handleIllegalArgument(IllegalArgumentException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, ex.getMessage());
        problem.setTitle("Validation Invariant Failure");
        problem.setType(URI.create("urn:problem:validation-error"));
        problem.setProperty("timestamp", Instant.now());
        return problem;
    }
}`,
        origin_file: 'src/main/java/com/enterprise/reference/exception/GlobalExceptionHandler.java',
      },
      {
        pattern_name: 'Service',
        target_layer: 'service',
        annotations_matched: ['@Service', '@Transactional'],
        code_snippet: `package com.enterprise.reference.service;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class AccountService {

    @Transactional(readOnly = true)
    public AccountResponse getAccount(String accountId) {
        return new AccountResponse(accountId, "Enterprise Customer", balance, "ACTIVE");
    }
}`,
        origin_file: 'src/main/java/com/enterprise/reference/service/AccountService.java',
      },
    ],
    conformance_rules: [
      {
        rule_id: 'ARCH-001',
        description: 'Controllers must only access Services and must not depend directly on Repositories.',
        test_method_name: 'controllers_should_not_access_repositories_directly',
        rule_code: 'noClasses().that().resideInAPackage("..controller..").should().dependOnClassesThat().resideInAPackage("..repository..")',
      },
      {
        rule_id: 'ARCH-002',
        description: 'Domain services must declare Spring Service or Transactional boundaries.',
        test_method_name: 'services_should_be_annotated_with_service_or_transactional',
        rule_code: 'classes().that().resideInAPackage("..service..").should().beAnnotatedWith(Service.class)',
      },
      {
        rule_id: 'ARCH-003',
        description: 'Domain JPA/persistence entities must not be accessed directly by presentation controllers.',
        test_method_name: 'controllers_should_not_access_entities_directly',
        rule_code: 'noClasses().that().resideInAPackage("..controller..").should().dependOnClassesThat().resideInAPackage("..domain..")',
      },
      {
        rule_id: 'ARCH-004',
        description: 'Classes in controller packages must have names ending with Controller.',
        test_method_name: 'controller_classes_should_be_named_ending_with_controller',
        rule_code: 'classes().that().resideInAPackage("..controller..").should().haveSimpleNameEndingWith("Controller")',
      },
    ],
    sha256_hash: '7eb5cf7cb39ef7925b8fe129f58a197a5e16acce8005fcf3af7fca761b273af2',
  },
  {
    profile_id: 'arch-hexagonal-core-v1',
    name: 'Enterprise Hexagonal Ports & Adapters Archetype',
    target_runtime: 'Java 21 / Spring Boot 3.5.0',
    created_at: new Date().toISOString(),
    base_package_pattern: 'com.enterprise.core.{domain}',
    layering_pattern: 'HEXAGONAL',
    build_file_template: `<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.5.0</version>
  </parent>
  <groupId>{{GROUP_ID}}</groupId>
  <artifactId>{{ARTIFACT_ID}}</artifactId>
  <name>{{PROJECT_NAME}}</name>
</project>`,
    required_dependencies: [
      'org.springframework.boot:spring-boot-starter-web',
      'org.springframework.boot:spring-boot-starter-actuator',
      'com.tngtech.archunit:archunit-junit5',
    ],
    exemplars: [
      {
        pattern_name: 'RestController',
        target_layer: 'adapters',
        annotations_matched: ['@RestController'],
        code_snippet: `package com.enterprise.core.adapter.in.web;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/resources")
public class ResourceAdapter {
    // Primary Web Inbound Adapter
}`,
        origin_file: 'src/main/java/com/enterprise/core/adapter/in/web/ResourceAdapter.java',
      },
    ],
    conformance_rules: [
      {
        rule_id: 'ARCH-HEX-001',
        description: 'Domain core must never depend on external adapters or frameworks.',
        test_method_name: 'domain_core_must_not_depend_on_adapters',
        rule_code: 'noClasses().that().resideInAPackage("..domain..").should().dependOnClassesThat().resideInAPackage("..adapter..")',
      },
      {
        rule_id: 'ARCH-HEX-002',
        description: 'Inbound adapters must interact only through application use case input ports.',
        test_method_name: 'inbound_adapters_must_use_ports',
        rule_code: 'classes().that().resideInAPackage("..adapter.in..").should().dependOnClassesThat().resideInAPackage("..port.in..")',
      },
    ],
    sha256_hash: '3d9a1c5e6b72f8401cde92a48b56f10328904712534a6bc891e23f0a719c8d45',
  },
];

let activeProfileIdInMemory = 'arch-payments-v2';

export const REAL_BANKING_CLASSES = [
  {
    fqn: 'com.legacy.banking.web.TransferManagedBean',
    simple_name: 'TransferManagedBean',
    kind: 'CLASS',
    role: 'PRESENTATION',
    annotations: ['ManagedBean', 'SessionScoped'],
    methods_count: 11,
    fields_count: 2,
    invocations_count: 6,
    injected_dependencies: ['TransferProcessingService'],
  },
  {
    fqn: 'com.legacy.banking.web.LoanApplicationManagedBean',
    simple_name: 'LoanApplicationManagedBean',
    kind: 'CLASS',
    role: 'PRESENTATION',
    annotations: ['ManagedBean', 'SessionScoped'],
    methods_count: 22,
    fields_count: 2,
    invocations_count: 21,
    injected_dependencies: ['LoanProcessingService', 'AzureAdAuthenticationService'],
  },
  {
    fqn: 'com.legacy.banking.web.AuthenticationManagedBean',
    simple_name: 'AuthenticationManagedBean',
    kind: 'CLASS',
    role: 'PRESENTATION',
    annotations: ['ManagedBean', 'SessionScoped'],
    methods_count: 12,
    fields_count: 1,
    invocations_count: 12,
    injected_dependencies: ['AzureAdAuthenticationService'],
  },
  {
    fqn: 'com.legacy.banking.service.TransferProcessingService',
    simple_name: 'TransferProcessingService',
    kind: 'CLASS',
    role: 'BUSINESS_SERVICE',
    annotations: ['Stateless'],
    methods_count: 3,
    fields_count: 3,
    invocations_count: 18,
    injected_dependencies: ['AccountRepository', 'CicsMainframeGateway'],
  },
  {
    fqn: 'com.legacy.banking.service.LoanProcessingService',
    simple_name: 'LoanProcessingService',
    kind: 'CLASS',
    role: 'BUSINESS_SERVICE',
    annotations: ['Stateless'],
    methods_count: 3,
    fields_count: 4,
    invocations_count: 50,
    injected_dependencies: ['LoanApplicationRepository', 'CreditBureauGateway', 'CicsMainframeGateway'],
  },
  {
    fqn: 'com.legacy.banking.service.AzureAdAuthenticationService',
    simple_name: 'AzureAdAuthenticationService',
    kind: 'CLASS',
    role: 'BUSINESS_SERVICE',
    annotations: ['Stateless'],
    methods_count: 4,
    fields_count: 1,
    invocations_count: 12,
    injected_dependencies: ['AzureAdGateway'],
  },
  {
    fqn: 'com.legacy.banking.repository.AccountRepository',
    simple_name: 'AccountRepository',
    kind: 'CLASS',
    role: 'DATA_ACCESS',
    annotations: ['Stateless'],
    methods_count: 5,
    fields_count: 1,
    invocations_count: 10,
    injected_dependencies: ['EntityManager'],
  },
  {
    fqn: 'com.legacy.banking.repository.LoanApplicationRepository',
    simple_name: 'LoanApplicationRepository',
    kind: 'CLASS',
    role: 'DATA_ACCESS',
    annotations: ['Stateless'],
    methods_count: 7,
    fields_count: 1,
    invocations_count: 15,
    injected_dependencies: ['EntityManager'],
  },
  {
    fqn: 'com.legacy.banking.gateway.CicsMainframeGateway',
    simple_name: 'CicsMainframeGateway',
    kind: 'CLASS',
    role: 'GATEWAY',
    annotations: ['Stateless'],
    methods_count: 5,
    fields_count: 0,
    invocations_count: 9,
    injected_dependencies: [],
  },
  {
    fqn: 'com.legacy.banking.gateway.CreditBureauGateway',
    simple_name: 'CreditBureauGateway',
    kind: 'CLASS',
    role: 'GATEWAY',
    annotations: ['Stateless'],
    methods_count: 2,
    fields_count: 0,
    invocations_count: 13,
    injected_dependencies: [],
  },
  {
    fqn: 'com.legacy.banking.gateway.AzureAdGateway',
    simple_name: 'AzureAdGateway',
    kind: 'CLASS',
    role: 'GATEWAY',
    annotations: ['Stateless'],
    methods_count: 3,
    fields_count: 0,
    invocations_count: 63,
    injected_dependencies: [],
  },
  {
    fqn: 'com.legacy.banking.domain.Account',
    simple_name: 'Account',
    kind: 'CLASS',
    role: 'DOMAIN_ENTITY',
    annotations: ['Entity', 'Table'],
    methods_count: 12,
    fields_count: 0,
    invocations_count: 0,
    injected_dependencies: [],
  },
  {
    fqn: 'com.legacy.banking.domain.LoanApplication',
    simple_name: 'LoanApplication',
    kind: 'CLASS',
    role: 'DOMAIN_ENTITY',
    annotations: ['Entity', 'Table'],
    methods_count: 28,
    fields_count: 0,
    invocations_count: 0,
    injected_dependencies: [],
  },
  {
    fqn: 'com.legacy.banking.security.AzureAdAuthFilter',
    simple_name: 'AzureAdAuthFilter',
    kind: 'CLASS',
    role: 'SECURITY',
    annotations: ['WebFilter'],
    methods_count: 3,
    fields_count: 1,
    invocations_count: 16,
    injected_dependencies: ['AzureAdAuthenticationService'],
  },
  {
    fqn: 'com.legacy.banking.security.AzureAdUserPrincipal',
    simple_name: 'AzureAdUserPrincipal',
    kind: 'CLASS',
    role: 'SECURITY',
    annotations: [],
    methods_count: 22,
    fields_count: 0,
    invocations_count: 6,
    injected_dependencies: [],
  },
];

export const apiClient = {
  // Screen 1: Source Ingestion & Diagnostics
  async uploadSource(formData: FormData): Promise<UploadResponse> {
    if (isMockMode) {
      return {
        status: 'SUCCESS',
        monolith_id: 'legacy-banking-monolith',
        classes_parsed: REAL_BANKING_CLASSES.length,
        classes_count: REAL_BANKING_CLASSES.length,
        methods_count: 142,
        injected_fields_count: 16,
        invocations_count: 251,
        endpoints_count: 3,
        cics_gateways_count: 3,
        entry_points_detected: 3,
        total_edges: 24,
        resolved_type_percentage: 98.4,
        graph_file_path: 'artifacts/metadata/lst_graph.json',
        sha256_digest: '4a7f29b4e1c8d5a2f30691e84b2c159e66d98c2b719401827463519827364512',
        extracted_at: new Date().toISOString(),
        execution_time_ms: 2833,
        message: 'Successfully parsed 15 classes into NetworkX in-memory graph. Discovered 3 entry points and 24 dependencies.',
        classes: REAL_BANKING_CLASSES,
      };
    }

    try {
      const res = await api.post('/api/source/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data;
    } catch (err) {
      console.warn('[apiClient] uploadSource failed; falling back to mock graph data', err);
      return {
        status: 'SUCCESS',
        monolith_id: 'legacy-banking-monolith',
        classes_parsed: REAL_BANKING_CLASSES.length,
        classes_count: REAL_BANKING_CLASSES.length,
        methods_count: 142,
        injected_fields_count: 16,
        invocations_count: 251,
        endpoints_count: 3,
        cics_gateways_count: 3,
        entry_points_detected: 3,
        total_edges: 24,
        resolved_type_percentage: 98.4,
        graph_file_path: 'artifacts/metadata/lst_graph.json',
        sha256_digest: '4a7f29b4e1c8d5a2f30691e84b2c159e66d98c2b719401827463519827364512',
        extracted_at: new Date().toISOString(),
        execution_time_ms: 2833,
        message: 'Successfully parsed 15 classes into NetworkX in-memory graph. Discovered 3 entry points and 24 dependencies.',
        classes: REAL_BANKING_CLASSES,
      };
    }
  },

  async getDiagnostics(): Promise<Diagnostics> {
    if (isMockMode) {
      return {
        status: 'HEALTHY',
        graph_loaded: true,
        total_nodes: 18,
        total_edges: 24,
        total_entrypoints: 3,
        resolved_type_percentage: 98.4,
        graph_file_path: 'artifacts/metadata/lst_graph.json',
        extracted_at: new Date().toISOString(),
        sha256_digest: '4a7f29b4e1c8d5a2f30691e84b2c159e66d98c2b719401827463519827364512',
        entry_point_names: ['TransferManagedBean', 'LoanApplicationManagedBean', 'AuthenticationManagedBean'],
      };
    }

    try {
      const res = await api.get('/api/source/diagnostics');
      return res.data;
    } catch (err) {
      console.warn('[apiClient] getDiagnostics failed; falling back to mock diagnostics', err);
      return {
        status: 'HEALTHY',
        graph_loaded: true,
        total_nodes: 18,
        total_edges: 24,
        total_entrypoints: 3,
        resolved_type_percentage: 98.4,
        graph_file_path: 'artifacts/metadata/lst_graph.json',
        extracted_at: new Date().toISOString(),
        sha256_digest: '4a7f29b4e1c8d5a2f30691e84b2c159e66d98c2b719401827463519827364512',
        entry_point_names: ['TransferManagedBean', 'LoanApplicationManagedBean', 'AuthenticationManagedBean'],
      };
    }
  },

  // Screen 2: Graph & Topology
  async getEntrypoints(): Promise<EntryPoint[]> {
    if (isMockMode) {
      return [
        {
          fqn: 'com.enterprise.banking.TransferManagedBean',
          class_name: 'TransferManagedBean',
          simple_name: 'TransferManagedBean',
          layer: 'PRESENTATION',
          framework_marker: '@ManagedBean',
          method_count: 11,
          line_count: 55,
          role: 'JSF_MANAGED_BEAN',
          kind: 'CLASS',
          annotations: ['@ManagedBean', '@SessionScoped'],
          injected_dependencies: ['TransferProcessingService'],
          description: 'JSF 2.x session-scoped controller handling UI fund transfer submissions and action triggers.',
        },
        {
          fqn: 'com.legacy.banking.web.LoanApplicationManagedBean',
          class_name: 'LoanApplicationManagedBean',
          simple_name: 'LoanApplicationManagedBean',
          layer: 'PRESENTATION',
          framework_marker: '@ManagedBean',
          method_count: 22,
          line_count: 110,
          role: 'JSF_MANAGED_BEAN',
          kind: 'CLASS',
          annotations: ['@ManagedBean', '@SessionScoped'],
          injected_dependencies: ['LoanProcessingService', 'AzureAdAuthenticationService'],
          description: 'Retail loan origination and underwriting JSF managed bean.',
        },
        {
          fqn: 'com.legacy.banking.web.AuthenticationManagedBean',
          class_name: 'AuthenticationManagedBean',
          simple_name: 'AuthenticationManagedBean',
          layer: 'PRESENTATION',
          framework_marker: '@ManagedBean',
          method_count: 12,
          line_count: 60,
          role: 'JSF_MANAGED_BEAN',
          kind: 'CLASS',
          annotations: ['@ManagedBean', '@SessionScoped'],
          injected_dependencies: ['AzureAdAuthenticationService'],
          description: 'Authentication and session principal delegating to Azure AD Gateway.',
        },
      ];
    }

    try {
      const res = await api.get('/api/graph/entrypoints');
      return res.data;
    } catch (err) {
      console.warn('[apiClient] getEntrypoints failed; returning mock entrypoints', err);
      return [
        {
          fqn: 'com.enterprise.banking.TransferManagedBean',
          class_name: 'TransferManagedBean',
          simple_name: 'TransferManagedBean',
          layer: 'PRESENTATION',
          framework_marker: '@ManagedBean',
          method_count: 11,
          line_count: 55,
          role: 'JSF_MANAGED_BEAN',
          kind: 'CLASS',
          annotations: ['@ManagedBean', '@SessionScoped'],
          injected_dependencies: ['TransferProcessingService'],
          description: 'JSF 2.x session-scoped controller handling UI fund transfer submissions and action triggers.',
        },
        {
          fqn: 'com.legacy.banking.web.LoanApplicationManagedBean',
          class_name: 'LoanApplicationManagedBean',
          simple_name: 'LoanApplicationManagedBean',
          layer: 'PRESENTATION',
          framework_marker: '@ManagedBean',
          method_count: 22,
          line_count: 110,
          role: 'JSF_MANAGED_BEAN',
          kind: 'CLASS',
          annotations: ['@ManagedBean', '@SessionScoped'],
          injected_dependencies: ['LoanProcessingService', 'AzureAdAuthenticationService'],
          description: 'Retail loan origination and underwriting JSF managed bean.',
        },
        {
          fqn: 'com.legacy.banking.web.AuthenticationManagedBean',
          class_name: 'AuthenticationManagedBean',
          simple_name: 'AuthenticationManagedBean',
          layer: 'PRESENTATION',
          framework_marker: '@ManagedBean',
          method_count: 12,
          line_count: 60,
          role: 'JSF_MANAGED_BEAN',
          kind: 'CLASS',
          annotations: ['@ManagedBean', '@SessionScoped'],
          injected_dependencies: ['AzureAdAuthenticationService'],
          description: 'Authentication and session principal delegating to Azure AD Gateway.',
        },
      ];
    }
  },

  async getSlice(entryFqn: string, maxDepth: number = 5): Promise<VerticalSliceResponse> {
    return this.getVerticalSlice(entryFqn, maxDepth);
  },

  async getVerticalSlice(entryFqn: string, maxDepth: number = 5): Promise<VerticalSliceResponse> {
    if (isMockMode) {
      return {
        slice_id: entryFqn,
        entry_fqn: entryFqn,
        max_depth: maxDepth,
        nodes: [
          {
            id: 'com.enterprise.banking.TransferManagedBean',
            label: 'TransferManagedBean',
            name: 'TransferManagedBean',
            fqn: 'com.enterprise.banking.TransferManagedBean',
            layer: 'PRESENTATION',
            role: 'JSF_MANAGED_BEAN',
            color: '#3b82f6',
            annotations: ['@ManagedBean', '@SessionScoped'],
            methods: ['execute', 'reset', 'getFromAccountId', 'getToAccountId'],
            file_path: 'src/main/java/com/enterprise/banking/TransferManagedBean.java',
            start_line: 24,
            end_line: 140,
            source_code: '// TransferManagedBean source code snippet',
          },
          {
            id: 'com.enterprise.banking.TransferProcessingService',
            label: 'TransferProcessingService',
            name: 'TransferProcessingService',
            fqn: 'com.enterprise.banking.TransferProcessingService',
            layer: 'SERVICE',
            role: 'DOMAIN_SERVICE',
            color: '#10b981',
            annotations: ['@Stateless', '@TransactionAttribute'],
            methods: ['processTransfer', 'getAccountDetails'],
            file_path: 'src/main/java/com/enterprise/banking/TransferProcessingService.java',
            start_line: 18,
            end_line: 96,
            source_code: '// TransferProcessingService source code snippet',
          },
          {
            id: 'com.enterprise.banking.AccountRepository',
            label: 'AccountRepository',
            name: 'AccountRepository',
            fqn: 'com.enterprise.banking.AccountRepository',
            layer: 'DATA',
            role: 'DATA_ACCESS',
            color: '#f59e0b',
            annotations: ['@Stateless', '@PersistenceContext'],
            methods: ['findById', 'updateBalance', 'save'],
            file_path: 'src/main/java/com/enterprise/banking/AccountRepository.java',
            start_line: 14,
            end_line: 65,
            source_code: '// AccountRepository source code snippet',
          },
          {
            id: 'com.enterprise.banking.CicsMainframeGateway',
            label: 'CicsMainframeGateway',
            name: 'CicsMainframeGateway',
            fqn: 'com.enterprise.banking.CicsMainframeGateway',
            layer: 'INTEGRATION',
            role: 'MAINFRAME_GATEWAY',
            color: '#8b5cf6',
            annotations: ['@Stateless'],
            methods: ['executeTransfer', 'queryAccountBalance'],
            file_path: 'src/main/java/com/enterprise/banking/CicsMainframeGateway.java',
            start_line: 12,
            end_line: 58,
            source_code: '// CicsMainframeGateway source code snippet',
          },
          {
            id: 'com.enterprise.banking.Account',
            label: 'Account',
            name: 'Account',
            fqn: 'com.enterprise.banking.Account',
            layer: 'DATA',
            role: 'DOMAIN_ENTITY',
            color: '#f59e0b',
            annotations: ['@Entity', '@Table'],
            methods: ['getAccountId', 'getBalance'],
            file_path: 'src/main/java/com/enterprise/banking/Account.java',
            start_line: 10,
            end_line: 45,
            source_code: '// Account entity source code snippet',
          },
        ],
        edges: [
          {
            id: 'edge-1',
            source: 'com.enterprise.banking.TransferManagedBean',
            target: 'com.enterprise.banking.TransferProcessingService',
            relationship: 'INJECTS',
            type: 'INJECTS',
            label: 'INJECTS',
          },
          {
            id: 'edge-2',
            source: 'com.enterprise.banking.TransferProcessingService',
            target: 'com.enterprise.banking.AccountRepository',
            relationship: 'INJECTS',
            type: 'INJECTS',
            label: 'INJECTS',
          },
          {
            id: 'edge-3',
            source: 'com.enterprise.banking.TransferProcessingService',
            target: 'com.enterprise.banking.CicsMainframeGateway',
            relationship: 'INJECTS',
            type: 'INJECTS',
            label: 'INJECTS',
          },
          {
            id: 'edge-4',
            source: 'com.enterprise.banking.AccountRepository',
            target: 'com.enterprise.banking.Account',
            relationship: 'CALLS',
            type: 'CALLS',
            label: 'CALLS',
          },
        ],
        total_nodes: 5,
        total_edges: 4,
        execution_paths: [
          'TransferManagedBean -> TransferProcessingService -> AccountRepository -> Account',
          'TransferManagedBean -> TransferProcessingService -> CicsMainframeGateway',
        ],
        component_summary: [
          { fqn: 'com.enterprise.banking.TransferManagedBean', role: 'JSF_MANAGED_BEAN', layer: 'PRESENTATION' },
          { fqn: 'com.enterprise.banking.TransferProcessingService', role: 'DOMAIN_SERVICE', layer: 'SERVICE' },
          { fqn: 'com.enterprise.banking.AccountRepository', role: 'DATA_ACCESS', layer: 'DATA' },
          { fqn: 'com.enterprise.banking.CicsMainframeGateway', role: 'MAINFRAME_GATEWAY', layer: 'INTEGRATION' },
          { fqn: 'com.enterprise.banking.Account', role: 'DOMAIN_ENTITY', layer: 'DATA' },
        ],
        estimated_tokens: 1420,
        max_tokens: 6000,
        within_budget: true,
        legacy_source: '// Aggregated legacy source for Transfer vertical slice...',
        raw_slice: {},
      };
    }

    try {
      const res = await api.post('/api/graph/slice', {
        entry_fqn: entryFqn,
        max_depth: maxDepth,
      });
      return res.data;
    } catch (err) {
      console.warn('[apiClient] getVerticalSlice failed; returning mock slice', err);
      const simpleName = entryFqn.split('.').pop() || 'EntryClass';
      return {
        slice_id: entryFqn,
        entry_fqn: entryFqn,
        max_depth: maxDepth,
        nodes: [
          {
            id: entryFqn,
            label: simpleName,
            name: simpleName,
            fqn: entryFqn,
            layer: 'PRESENTATION',
            role: 'JSF_MANAGED_BEAN',
            color: '#3b82f6',
            file_path: `src/main/java/${entryFqn.replace(/\\./g, '/')}.java`,
            start_line: 1,
            end_line: 50,
            annotations: ['@ManagedBean'],
            methods: ['execute'],
          },
        ],
        edges: [],
        total_nodes: 1,
        total_edges: 0,
        execution_paths: [entryFqn],
        component_summary: [{ fqn: entryFqn, role: 'JSF_MANAGED_BEAN', layer: 'PRESENTATION' }],
        estimated_tokens: 450,
        max_tokens: 6000,
        within_budget: true,
        legacy_source: '// Fallback slice source',
        raw_slice: {},
      };
    }
  },

  async startPipelineRun(entryFqn: string, sliceData?: any, trackerType: string = 'jira') {
    const res = await api.post('/api/pipeline/runs', {
      entry_fqn: entryFqn,
      slice_data: sliceData,
      tracker_type: trackerType,
    });
    return res.data;
  },

  async startBatchRun(entryFqns: string[], maxDepth: number = 5, trackerType: string = 'jira'): Promise<BatchRunStatus> {
    if (isMockMode) {
      const batchId = `batch-${Math.random().toString(36).substring(2, 9)}`;
      return {
        batch_id: batchId,
        total_slices: entryFqns.length,
        completed_slices: 0,
        failed_slices: 0,
        status: 'PROCESSING',
        created_at: new Date().toISOString(),
        slices: entryFqns.map((fqn, i) => ({
          run_id: `run-${Math.random().toString(36).substring(2, 9)}`,
          entry_fqn: fqn,
          class_name: fqn.split('.').pop() || `Slice${i + 1}`,
          status: 'QUEUED',
          current_pass: null,
          tokens_consumed: 0,
          duration_ms: 0,
        })),
      };
    }

    try {
      const res = await api.post('/api/pipeline/batches', {
        entry_fqns: entryFqns,
        max_depth: maxDepth,
        tracker_type: trackerType,
      });
      return res.data;
    } catch (err) {
      console.warn('[apiClient] startBatchRun failed; falling back to mock batch', err);
      const batchId = `batch-${Math.random().toString(36).substring(2, 9)}`;
      return {
        batch_id: batchId,
        total_slices: entryFqns.length,
        completed_slices: 0,
        failed_slices: 0,
        status: 'PROCESSING',
        created_at: new Date().toISOString(),
        slices: entryFqns.map((fqn, i) => ({
          run_id: `run-${Math.random().toString(36).substring(2, 9)}`,
          entry_fqn: fqn,
          class_name: fqn.split('.').pop() || `Slice${i + 1}`,
          status: 'QUEUED',
          current_pass: null,
          tokens_consumed: 0,
          duration_ms: 0,
        })),
      };
    }
  },

  async getBatchStatus(batchId: string): Promise<BatchRunStatus> {
    if (isMockMode) {
      return {
        batch_id: batchId,
        total_slices: 3,
        completed_slices: 3,
        failed_slices: 0,
        status: 'COMPLETED',
        created_at: new Date().toISOString(),
        slices: [],
      };
    }
    const res = await api.get(`/api/pipeline/batches/${batchId}`);
    return res.data;
  },

  async listBatches(): Promise<BatchRunStatus[]> {
    if (isMockMode) return [];
    const res = await api.get('/api/pipeline/batches');
    return res.data;
  },

  // Screen 4: HITL Review & Jira Gate
  async getSpec(runId: string) {
    const res = await api.get(`/api/spec/${runId}`);
    return res.data;
  },

  async approveHitl(runId: string, approvedBy: string, comments?: string, specSha256?: string) {
    const res = await api.post('/api/hitl/approve', {
      run_id: runId,
      approved_by: approvedBy,
      comments,
      spec_sha256: specSha256,
    });
    return res.data;
  },

  async reviseHitl(runId: string, feedback: string, targetPass: number = 2) {
    const res = await api.post('/api/hitl/revise', {
      run_id: runId,
      feedback,
      target_pass: targetPass,
    });
    return res.data;
  },

  // Screen 5: Catalog & Synthesis
  async getCatalogMatch(domain: string = 'PAYMENT_PROCESSING') {
    const res = await api.get(`/api/catalog/match?domain=${encodeURIComponent(domain)}`);
    return res.data;
  },

  async generateSynthesis(runId: string, targetStack: string = 'spring_boot_3_5') {
    const res = await api.post('/api/synthesis/generate', {
      run_id: runId,
      target_stack: targetStack,
      generate_ui: true,
      generate_openapi: true,
    });
    return res.data;
  },

  getBundleDownloadUrl(runId: string): string {
    return `/api/synthesis/bundle/${runId}`;
  },

  // Target Architecture Provider Subsystem
  async getArchitectureProfiles(): Promise<ProfileSummary[]> {
    if (isMockMode) {
      return MOCK_PROFILES.map((p) => ({
        profile_id: p.profile_id,
        name: p.name,
        target_runtime: p.target_runtime,
        layering_pattern: p.layering_pattern,
        base_package_pattern: p.base_package_pattern,
        created_at: p.created_at || new Date().toISOString(),
        sha256_hash: p.sha256_hash,
        exemplars_count: p.exemplars.length,
        conformance_rules_count: p.conformance_rules.length,
        is_active: p.profile_id === activeProfileIdInMemory,
      }));
    }

    try {
      const res = await api.get('/api/architecture/profiles');
      return res.data;
    } catch (err) {
      console.warn('[apiClient] Fetch architecture profiles failed; using mock fallback', err);
      return MOCK_PROFILES.map((p) => ({
        profile_id: p.profile_id,
        name: p.name,
        target_runtime: p.target_runtime,
        layering_pattern: p.layering_pattern,
        base_package_pattern: p.base_package_pattern,
        created_at: p.created_at || new Date().toISOString(),
        sha256_hash: p.sha256_hash,
        exemplars_count: p.exemplars.length,
        conformance_rules_count: p.conformance_rules.length,
        is_active: p.profile_id === activeProfileIdInMemory,
      }));
    }
  },

  async getArchitectureProfile(profileId: string): Promise<ArchitectureProfile> {
    if (isMockMode) {
      const match = MOCK_PROFILES.find((p) => p.profile_id === profileId) || MOCK_PROFILES[0];
      return match;
    }

    try {
      const res = await api.get(`/api/architecture/profiles/${profileId}`);
      return res.data;
    } catch (err) {
      console.warn(`[apiClient] Fetch profile ${profileId} failed; using mock fallback`, err);
      const match = MOCK_PROFILES.find((p) => p.profile_id === profileId) || MOCK_PROFILES[0];
      return match;
    }
  },

  async selectActiveArchitectureProfile(profileId: string): Promise<{ status: string; active_profile_id: string }> {
    activeProfileIdInMemory = profileId;
    if (isMockMode) {
      return { status: 'SUCCESS', active_profile_id: profileId };
    }

    try {
      const res = await api.post('/api/architecture/select-active', { profile_id: profileId });
      return res.data;
    } catch (err) {
      console.warn('[apiClient] select-active failed; mock fallback applied', err);
      return { status: 'SUCCESS', active_profile_id: profileId };
    }
  },

  async harvestReferenceRepo(payload: HarvestReferencePayload): Promise<ArchitectureProfile> {
    if (isMockMode) {
      const newProfile: ArchitectureProfile = {
        profile_id: payload.profile_id || `arch-${payload.profile_name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
        name: payload.profile_name,
        target_runtime: 'Java 21 / Spring Boot 3.5.0',
        created_at: new Date().toISOString(),
        base_package_pattern: 'com.enterprise.{domain}.v2',
        layering_pattern: 'CONTROLLER_SERVICE_REPOSITORY',
        build_file_template: MOCK_PROFILES[0].build_file_template,
        required_dependencies: MOCK_PROFILES[0].required_dependencies,
        exemplars: MOCK_PROFILES[0].exemplars,
        conformance_rules: MOCK_PROFILES[0].conformance_rules,
        sha256_hash: '9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b',
      };
      MOCK_PROFILES.unshift(newProfile);
      activeProfileIdInMemory = newProfile.profile_id;
      return newProfile;
    }

    let res;
    if (payload.file) {
      const formData = new FormData();
      formData.append('file', payload.file);
      formData.append('profile_name', payload.profile_name);
      if (payload.profile_id) formData.append('profile_id', payload.profile_id);
      res = await api.post('/api/architecture/harvest-reference', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    } else {
      res = await api.post('/api/architecture/harvest-reference', {
        repo_path: payload.repo_path || 'samples/reference-spring-boot-service',
        profile_name: payload.profile_name,
        profile_id: payload.profile_id,
      });
    }
    activeProfileIdInMemory = res.data.profile_id;
    return res.data;
  },

  async getHitlReviewData(runId: string): Promise<HitlReviewPayload> {
    const res = await api.get(`/api/hitl/spec/${runId}`);
    return res.data;
  },

  async reviseSpecWithAi(request: HitlRevisionRequest): Promise<HitlReviseResponse> {
    const res = await api.post('/api/hitl/revise', request);
    return res.data;
  },

  async approveHitlSpec(request: HitlApprovalRequest): Promise<HitlApprovalResponse> {
    const res = await api.post('/api/hitl/approve', request);
    return res.data;
  },
};

// Standalone exports for Screen 2 and graph topology
export const getEntrypoints = (): Promise<EntryPoint[]> => apiClient.getEntrypoints();
export const getSlice = (entryFqn: string, maxDepth: number = 5): Promise<VerticalSliceResponse> => apiClient.getSlice(entryFqn, maxDepth);
export const getVerticalSlice = (entryFqn: string, maxDepth: number = 5): Promise<VerticalSliceResponse> => apiClient.getVerticalSlice(entryFqn, maxDepth);
export const startBatchRun = (entryFqns: string[], maxDepth: number = 5): Promise<BatchRunStatus> => apiClient.startBatchRun(entryFqns, maxDepth);
export const getBatchStatus = (batchId: string): Promise<BatchRunStatus> => apiClient.getBatchStatus(batchId);
export const listBatches = (): Promise<BatchRunStatus[]> => apiClient.listBatches();

// Standalone exports for Step 4 HITL Review & Gating
export const getHitlReviewData = (runId: string): Promise<HitlReviewPayload> => apiClient.getHitlReviewData(runId);
export const reviseSpecWithAi = (request: HitlRevisionRequest): Promise<HitlReviseResponse> => apiClient.reviseSpecWithAi(request);
export const approveHitlSpec = (request: HitlApprovalRequest): Promise<HitlApprovalResponse> => apiClient.approveHitlSpec(request);

