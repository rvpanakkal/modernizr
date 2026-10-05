package com.enterprise.modernization.rewrite;

import com.enterprise.modernization.rewrite.model.ClassRecord;
import com.enterprise.modernization.rewrite.model.InvocationRecord;
import com.enterprise.modernization.rewrite.model.MethodRecord;
import com.enterprise.modernization.rewrite.model.FieldRecord;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.openrewrite.InMemoryExecutionContext;
import org.openrewrite.java.JavaParser;
import org.openrewrite.java.tree.J;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/**
 * JUnit 5 tests verifying LegacyMetadataExtractor against a representative
 * Java EE 6 code snippet modelled on the TransferManagedBean → TransferProcessingService chain.
 */
class LegacyMetadataExtractorTest {

    private static final String MANAGED_BEAN_SOURCE = """
        package com.legacy.banking.web;

        import com.legacy.banking.service.TransferProcessingService;
        import javax.faces.bean.ManagedBean;
        import javax.faces.bean.SessionScoped;
        import javax.ejb.EJB;
        import java.math.BigDecimal;

        @ManagedBean
        @SessionScoped
        public class TransferManagedBean {

            @EJB
            private TransferProcessingService transferService;

            private String fromAccountId;
            private BigDecimal amount;

            public String execute() {
                return transferService.processTransfer(fromAccountId, fromAccountId, amount);
            }

            public void reset() {
                fromAccountId = null;
                amount = null;
            }

            public String getFromAccountId() { return fromAccountId; }
            public void setFromAccountId(String id) { this.fromAccountId = id; }
        }
        """;

    private static final String STATELESS_SERVICE_SOURCE = """
        package com.legacy.banking.service;

        import javax.ejb.Stateless;
        import javax.inject.Inject;
        import java.math.BigDecimal;

        @Stateless
        public class TransferProcessingService {

            @Inject
            private AccountRepository accountRepository;

            public String processTransfer(String fromId, String toId, BigDecimal amount) {
                if (amount == null) throw new IllegalArgumentException("Amount required");
                accountRepository.findById(fromId);
                return "OK";
            }
        }
        """;

    // =========================================================================

    @Test
    @DisplayName("Should extract class FQN, kind, and class-level annotations")
    void testClassDeclarationExtraction() {
        List<ClassRecord> records = runExtractor(MANAGED_BEAN_SOURCE);

        assertFalse(records.isEmpty(), "Expected at least one ClassRecord");

        ClassRecord managed = findBySimpleName(records, "TransferManagedBean");
        assertNotNull(managed, "TransferManagedBean must be extracted");
        assertEquals("CLASS", managed.getKind());
        assertTrue(managed.getAnnotations().contains("ManagedBean"),
            "Should contain @ManagedBean annotation");
        assertTrue(managed.getAnnotations().contains("SessionScoped"),
            "Should contain @SessionScoped annotation");
    }

    @Test
    @DisplayName("Should extract @EJB and @Inject field injection metadata")
    void testFieldInjectionExtraction() {
        List<ClassRecord> records = runExtractor(MANAGED_BEAN_SOURCE, STATELESS_SERVICE_SOURCE);

        ClassRecord managed = findBySimpleName(records, "TransferManagedBean");
        assertNotNull(managed);
        assertEquals(1, managed.getFields().size(), "Should have exactly 1 injected field");

        FieldRecord field = managed.getFields().get(0);
        assertEquals("transferService", field.getName());
        assertEquals("EJB", field.getAnnotation());
        assertNotNull(field.getType(), "Type name must not be null");

        ClassRecord service = findBySimpleName(records, "TransferProcessingService");
        assertNotNull(service);
        assertEquals(1, service.getFields().size());
        assertEquals("Inject", service.getFields().get(0).getAnnotation());
    }

    @Test
    @DisplayName("Should extract method declarations with return types and annotations")
    void testMethodDeclarationExtraction() {
        List<ClassRecord> records = runExtractor(MANAGED_BEAN_SOURCE);

        ClassRecord managed = findBySimpleName(records, "TransferManagedBean");
        assertNotNull(managed);

        Optional<MethodRecord> executeMethod = managed.getMethods().stream()
            .filter(m -> "execute".equals(m.getName()))
            .findFirst();
        assertTrue(executeMethod.isPresent(), "execute() method must be extracted");
        assertEquals("execute", executeMethod.get().getName());
        assertNotNull(executeMethod.get().getSignature(), "Method signature must not be null");

        Optional<MethodRecord> resetMethod = managed.getMethods().stream()
            .filter(m -> "reset".equals(m.getName()))
            .findFirst();
        assertTrue(resetMethod.isPresent(), "reset() method must be extracted");
    }

    @Test
    @DisplayName("Should not throw on unresolvable Java EE types (graceful degradation)")
    void testGracefulDegradationOnUnresolvedTypes() {
        // @ManagedBean and @EJB are not on the classpath — this must not throw
        assertDoesNotThrow(() -> runExtractor(MANAGED_BEAN_SOURCE),
            "Extraction must not throw even when Java EE types are unresolvable");
    }

    @Test
    @DisplayName("Method signature should follow pattern 'fqn.methodName(paramTypes)'")
    void testMethodSignatureFormat() {
        List<ClassRecord> records = runExtractor(MANAGED_BEAN_SOURCE);
        ClassRecord managed = findBySimpleName(records, "TransferManagedBean");
        assertNotNull(managed);

        managed.getMethods().forEach(m -> {
            assertNotNull(m.getSignature(), "Signature must not be null for " + m.getName());
            assertTrue(m.getSignature().contains(m.getName()),
                "Signature must contain method name: " + m.getSignature());
        });
    }

    @Test
    @DisplayName("Should extract bodySource, thrownExceptions, and branchCount for non-trivial methods")
    void testMethodBodyAndExceptionExtraction() {
        List<ClassRecord> records = runExtractor(MANAGED_BEAN_SOURCE, STATELESS_SERVICE_SOURCE);
        ClassRecord service = findBySimpleName(records, "TransferProcessingService");
        assertNotNull(service);

        Optional<MethodRecord> processMethod = service.getMethods().stream()
            .filter(m -> "processTransfer".equals(m.getName()))
            .findFirst();
        assertTrue(processMethod.isPresent());

        MethodRecord method = processMethod.get();
        // Check thrown exception extraction
        assertTrue(method.getThrownExceptions().contains("IllegalArgumentException"),
            "Expected IllegalArgumentException in thrownExceptions, got: " + method.getThrownExceptions());

        // Check branch count (contains an 'if')
        assertTrue(method.getBranchCount() >= 1,
            "Expected branchCount >= 1, got: " + method.getBranchCount());

        // Check bodySource
        assertNotNull(method.getBodySource(), "bodySource must not be null for processTransfer");
        assertTrue(method.getBodySource().contains("throw new IllegalArgumentException"),
            "bodySource should contain exception statement");

        // Check that trivial getter does NOT have bodySource to save tokens
        ClassRecord managed = findBySimpleName(records, "TransferManagedBean");
        Optional<MethodRecord> getter = managed.getMethods().stream()
            .filter(m -> "getFromAccountId".equals(m.getName()))
            .findFirst();
        assertTrue(getter.isPresent());
        assertNull(getter.get().getBodySource(), "Trivial getter should have null bodySource");
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private List<ClassRecord> runExtractor(String... sources) {
        InMemoryExecutionContext ctx = new InMemoryExecutionContext(t -> {
            // suppress type resolution warnings in tests
        });
        JavaParser parser = JavaParser.fromJavaVersion().build();
        LegacyMetadataExtractor extractor = new LegacyMetadataExtractor();

        parser.parse(sources)
            .forEach(cu -> extractor.getVisitor().visit(cu, ctx));

        return extractor.getClassRecords();
    }

    private ClassRecord findBySimpleName(List<ClassRecord> records, String simpleName) {
        return records.stream()
            .filter(r -> simpleName.equals(r.getSimpleName()))
            .findFirst()
            .orElse(null);
    }
}
